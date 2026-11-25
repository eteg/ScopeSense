"""Botão "Gerar relatório": lê Slack + e-mail do período, o modelo escreve, a tela publica.

Gerar não publica nada: guarda o texto para a pessoa revisar. Só "Publicar" posta
no Slack (radar/relatorio/slack_saida.py, token de usuário).
"""

from collections.abc import Callable
from datetime import datetime, timedelta
from typing import cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter
from pydantic import BaseModel, Field

from radar import config, db
from radar.api.deps import (
    ProjetoJsonDep,
    ProjetoStoreDep,
    RegistryDep,
    config_atual,
    nome_do_projeto,
)
from radar.core.errors import (
    Conflito,
    EntradaInvalida,
    FalhaNaFonte,
    FonteNaoConfigurada,
    NaoEncontrado,
    RadarError,
)
from radar.core.models import Consulta, Origem
from radar.fontes.slack import SlackFonte
from radar.relatorio import estrutura, gerar, slack_saida, tarefas

router = APIRouter(prefix="/relatorios", tags=["relatorios"])
FUSO = ZoneInfo("America/Sao_Paulo")


class GerarPedido(BaseModel):
    dias: int = Field(default=7, ge=1, le=60, description="Período: os últimos N dias")


class PublicarPedido(BaseModel):
    quem: str = Field(min_length=1, max_length=120)


class PessoaMarcada(BaseModel):
    nome: str
    papel: str
    slack_id: str | None


class Mensagem(BaseModel):
    papel: str | None  # None = resumo; todas vão para o canal como mensagens separadas
    para: str | None  # nome da pessoa do papel, se cadastrada
    texto: str


class Tokens(BaseModel):
    entrada: int
    saida: int
    raciocinio: int
    cache_leitura: int
    cache_escrita: int


class Custo(BaseModel):
    modelo: str
    tokens: Tokens
    usd: float | None
    brl: float | None
    cotacao_usd_brl: float
    cotacao_origem: str


def _estruturado(texto: str) -> estrutura.RelatorioEstruturado | None:
    """Relatórios novos são JSON; os antigos, texto do Slack."""
    if not texto.lstrip().startswith("{"):
        return None
    try:
        return estrutura.RelatorioEstruturado.model_validate_json(texto)
    except ValueError:
        return None


def _mensagens_slack(dados: dict) -> list[dict]:
    """Resumo + uma por responsável, em Block Kit (só relatórios estruturados)."""
    fontes = dados["fontes"]
    est = _estruturado(dados["texto"])
    c = fontes.get("contagem", {})
    lidos = [f"{c.get('mensagens_slack', 0)} mensagens do Slack", f"{c.get('emails', 0)} e-mails"]
    if c.get("anexos_gmail") or c.get("arquivos"):
        lidos.insert(0, "o contrato")
    desde = datetime.fromisoformat(dados["desde"]).strftime("%d/%m")
    ate = datetime.fromisoformat(dados["ate"]).strftime("%d/%m")
    return estrutura.mensagens(
        est,
        projeto=fontes.get("projeto") or "Projeto",
        periodo=f"{desde} a {ate}",
        fontes="li " + ", ".join(lidos[:-1]) + " e " + lidos[-1],
        pessoas={p["papel"]: (p["nome"], p["slack_id"]) for p in fontes.get("pessoas", [])},
    )


class Relatorio(BaseModel):
    id: int
    criado_em: str
    desde: str
    ate: str
    mensagens: list[Mensagem]  # o resumo e uma mensagem no canal por responsável
    canal_id: str | None
    canal_nome: str | None
    fontes: dict
    pessoas: list[PessoaMarcada]
    avisos: list[str]
    publicado_em: str | None
    publicado_por: str | None
    slack_link: str | None
    custo: Custo | None = None  # relatórios gerados antes do cálculo não têm
    estrutura: dict | None = None  # relatório em dados (novo)
    slack: list[dict] | None = None  # as mensagens Block Kit exatas: a tela desenha a prévia


def _caminho() -> str:
    db.init_db(config.DATABASE_PATH)
    return config.DATABASE_PATH


def _montar(dados: dict) -> Relatorio:
    fontes = dados["fontes"]
    return Relatorio(
        id=dados["id"],
        criado_em=dados["criado_em"],
        desde=dados["desde"],
        ate=dados["ate"],
        mensagens=[
            Mensagem(
                papel=m["papel"],
                para=next(
                    (p["nome"] for p in fontes.get("pessoas", []) if p["papel"] == m["papel"]),
                    None,
                ),
                texto=m["text"],
            )
            for m in _mensagens_slack(dados)
        ]
        if _estruturado(dados["texto"])
        else [
            Mensagem(
                papel=m.papel.value if m.papel else None,
                para=next(
                    (p["nome"] for p in fontes.get("pessoas", []) if m.papel and p["papel"] == m.papel.value),
                    None,
                ),
                texto=m.texto,
            )
            for m in gerar.separar(dados["texto"])
        ],
        canal_id=dados["canal"],
        canal_nome=fontes.get("canal_nome"),
        fontes=fontes.get("contagem", {}),
        pessoas=[PessoaMarcada(**p) for p in fontes.get("pessoas", [])],
        avisos=fontes.get("avisos", []),
        publicado_em=dados["publicado_em"],
        publicado_por=dados["publicado_por"],
        slack_link=dados["slack_link"],
        custo=fontes.get("custo"),
        estrutura=(e.model_dump() if (e := _estruturado(dados["texto"])) else None),
        slack=_mensagens_slack(dados) if _estruturado(dados["texto"]) else None,
    )


Etapa = Callable[[str, str, str | None], None]  # (chave, status, detalhe)


def _sem_progresso(_chave: str, _status: str, _detalhe: str | None) -> None:
    return None


def _reais(valor: float) -> str:
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _plural(n: int, um: str, varios: str) -> str:
    return f"{n} {um if n == 1 else varios}"


def executar(
    dias: int, registry, projeto_json: dict, store, etapa: Etapa = _sem_progresso
) -> int:
    """Gera o relatório avisando cada etapa: (chave, "andamento"|"ok"|"erro", detalhe).

    Chaves: slack, gmail, contrato, pessoas, analise. Devolve o id do relatório salvo.
    """
    projeto = nome_do_projeto(projeto_json)
    cfg = config_atual(projeto_json, store, registry)
    canal = next((c for c in cfg.canais_slack if c.id), None)
    if canal is None:
        raise EntradaInvalida("Cadastre o canal do Slack do projeto nas Configurações.")
    try:
        slack = cast(SlackFonte, registry.get(Origem.slack))
    except FonteNaoConfigurada as exc:
        raise FonteNaoConfigurada(f"Slack não configurado: {exc}") from exc

    ate = datetime.now(FUSO)
    desde = ate - timedelta(days=dias)
    consulta = Consulta(desde=desde, ate=ate, limite=1000)
    coleta = gerar.Coleta()

    # 1. Slack
    etapa("slack", "andamento", "Conectando ao Slack…")
    canal_nome = canal.nome
    if not canal_nome:  # descobre uma vez e guarda: a próxima geração não consulta de novo
        canal_nome = next(
            (c["nome"] for c in slack.list_channels() if c["id"] == canal.id), canal.id
        )
        canal.nome = canal_nome
        store.salvar_config(projeto, cfg)
    etapa("slack", "andamento", f"Lendo as conversas de #{canal_nome}")
    try:
        coleta.slack = slack.fetch(consulta)
        n = coleta.contagem()
        etapa("slack", "ok", f"{_plural(n['mensagens_slack'], 'mensagem', 'mensagens')} em "
              f"{_plural(n['threads_slack'], 'conversa', 'conversas')} de #{canal_nome}")  # fmt: skip
    except RadarError as exc:
        # Sem o Slack, o relatório sairia incompleto (e o modelo seria pago à toa): para aqui.
        etapa("slack", "erro", "A conexão com o Slack caiu várias vezes seguidas")
        raise FalhaNaFonte(
            "Não consegui ler o Slack: a conexão caiu no meio das respostas, mesmo depois de "
            f"várias tentativas. Tente gerar de novo em instantes. ({exc})"
        ) from exc

    # 2. Gmail
    etapa("gmail", "andamento", "Lendo os e-mails do projeto")
    try:
        coleta.emails = registry.get(Origem.email).fetch(consulta)
        com_anexo = sum(1 for r in coleta.emails if r.metadados.get("anexos"))
        detalhe = _plural(len(coleta.emails), "e-mail do projeto", "e-mails do projeto")
        etapa("gmail", "ok", detalhe + (f" ({com_anexo} com anexo)" if com_anexo else ""))
    except RadarError as exc:
        coleta.avisos.append(f"Gmail não foi lido: {exc}")
        etapa("gmail", "erro", str(exc))

    # 3. Contrato: PDFs anexados aos e-mails + enviados nas Configurações
    etapa("contrato", "andamento", "Procurando o contrato nos anexos dos e-mails")
    anexos, avisos_anexos = gerar.anexos_do_gmail(registry)
    enviados = store.textos_dos_arquivos(projeto)
    coleta.arquivos = enviados + anexos
    coleta.anexos_gmail = len(anexos)
    coleta.avisos.extend(avisos_anexos)
    contratos = [nome.split(" (anexo")[0] for nome, tipo, _ in coleta.arquivos if tipo == "Contrato"]
    if coleta.arquivos:
        partes = []
        if contratos:
            partes.append(_plural(len(contratos), "contrato", "contratos") + f" ({', '.join(contratos)})")
        outros = len(coleta.arquivos) - len(contratos)
        if outros:
            partes.append(_plural(outros, "outro documento", "outros documentos"))
        etapa("contrato", "ok", " e ".join(partes))
    else:
        etapa("contrato", "erro", "Nenhum contrato encontrado: o relatório vai pedir o documento")

    # 4. Responsáveis
    etapa("pessoas", "andamento", "Encontrando os responsáveis no Slack")
    nomes = [p.nome for p in cfg.pessoas]
    try:
        ids = slack.ids_por_nome(nomes) if nomes else {}
        falha = None
    except RadarError as exc:  # segue sem marcar: os nomes saem em negrito
        ids, falha = {}, str(exc)
        coleta.avisos.append(f"Não consegui buscar as pessoas no Slack: {exc}")
    pessoas = [gerar.Pessoa(p.nome, p.papel, ids.get(p.nome)) for p in cfg.pessoas]
    achados = [p.nome for p in pessoas if p.slack_id]
    if falha:
        etapa("pessoas", "erro", "O Slack não respondeu a tempo: o relatório sai sem marcar ninguém")
    elif pessoas:
        etapa("pessoas", "ok", ", ".join(achados) if achados else "Ninguém encontrado no Slack")
    else:
        etapa("pessoas", "erro", "Ninguém cadastrado nas Configurações")

    # 5. Análise com o modelo
    try:
        gmail = registry.get(Origem.email).settings  # type: ignore[attr-defined]
        dominios = ", ".join(gmail.client_contacts + gmail.client_domains)
    except FonteNaoConfigurada:
        dominios = ""
    system, user = gerar.montar_prompt(
        projeto=projeto,
        cliente=(projeto_json.get("projeto") or {}).get("cliente"),
        canal_nome=canal_nome,
        canal_id=canal.id,
        dominios_email=dominios,
        pessoas=pessoas,
        desde=desde,
        ate=ate,
        coleta=coleta,
    )
    etapa("analise", "andamento", "Cruzando o contrato com as conversas e escrevendo o relatório")
    estruturado, gasto = gerar.chamar_modelo(system, user)
    texto = estruturado.model_dump_json()
    n = estrutura.contagem(estruturado)
    pontos = [f"{estrutura.EMOJI[s]} {n[s]}" for s in ("critico", "medio", "baixo") if n[s]]
    preco = f" · custou {_reais(gasto['brl'])}" if gasto.get("brl") is not None else ""
    etapa("analise", "ok", "Relatório pronto" + (f": {' · '.join(pontos)}" if pontos else "") + preco)

    fontes = {
        "contagem": coleta.contagem(),
        "avisos": coleta.avisos,
        "canal_nome": canal_nome,
        "projeto": projeto,
        "custo": gasto,
        "pessoas": [
            {"nome": p.nome, "papel": p.papel.value, "slack_id": p.slack_id} for p in pessoas
        ],
    }
    return db.salvar_relatorio(desde, ate, texto, fontes, canal.id, caminho=_caminho())


@router.post("")
def gerar_relatorio(
    pedido: GerarPedido,
    registry: RegistryDep,
    projeto_json: ProjetoJsonDep,
    store: ProjetoStoreDep,
) -> Relatorio:
    """Gera e só responde no fim (1 a 2 min). A tela usa /relatorios/tarefas."""
    relatorio_id = executar(pedido.dias, registry, projeto_json, store)
    return _montar(db.obter_relatorio(relatorio_id, caminho=_caminho()))


class ResumoRelatorio(BaseModel):
    id: int
    criado_em: str
    desde: str
    ate: str
    publicado_em: str | None
    publicado_por: str | None
    custo: Custo | None


class ListaRelatorios(BaseModel):
    relatorios: list[ResumoRelatorio]
    total_usd: float
    total_brl: float
    sem_custo: int  # gerados antes do cálculo de custo


@router.get("")
def listar() -> ListaRelatorios:
    """Relatórios gerados, do mais novo ao mais antigo, com o custo de cada um e o total."""
    itens = [
        ResumoRelatorio(**{k: r[k] for k in ResumoRelatorio.model_fields if k != "custo"},
                        custo=r["fontes"].get("custo"))  # fmt: skip
        for r in db.listar_relatorios(caminho=_caminho())
    ]
    com_custo = [i.custo for i in itens if i.custo and i.custo.usd is not None]
    return ListaRelatorios(
        relatorios=itens,
        total_usd=round(sum(c.usd for c in com_custo), 6),
        total_brl=round(sum(c.brl or 0 for c in com_custo), 4),
        sem_custo=len(itens) - len(com_custo),
    )


class EtapaTela(BaseModel):
    chave: str
    titulo: str
    status: str  # pendente | andamento | ok | erro
    detalhe: str | None


class TarefaTela(BaseModel):
    id: str
    etapas: list[EtapaTela]
    concluida: bool
    erro: str | None
    relatorio: Relatorio | None = None


@router.post("/tarefas")
def iniciar_geracao(
    pedido: GerarPedido,
    registry: RegistryDep,
    projeto_json: ProjetoJsonDep,
    store: ProjetoStoreDep,
) -> TarefaTela:
    """Começa a gerar em segundo plano. A tela acompanha por GET /relatorios/tarefas/{id}."""
    tarefa = tarefas.iniciar(
        lambda etapa: executar(pedido.dias, registry, projeto_json, store, etapa)
    )
    return TarefaTela(**tarefa.para_dict())


@router.get("/tarefas/{tarefa_id}")
def acompanhar_geracao(tarefa_id: str) -> TarefaTela:
    """Etapas (o que está sendo lido e o que foi achado) e, no fim, o relatório."""
    tarefa = tarefas.obter(tarefa_id)
    if tarefa is None:
        raise NaoEncontrado("Essa geração não existe mais (a API reiniciou?). Gere de novo.")
    dados = tarefa.para_dict()
    if tarefa.relatorio_id is not None:
        dados["relatorio"] = _montar(db.obter_relatorio(tarefa.relatorio_id, caminho=_caminho()))
    return TarefaTela(**dados)


@router.get("/{relatorio_id}")
def obter(relatorio_id: int) -> Relatorio:
    dados = db.obter_relatorio(relatorio_id, caminho=_caminho())
    if dados is None:
        raise NaoEncontrado(f"Relatório {relatorio_id} não existe.")
    return _montar(dados)


@router.post("/{relatorio_id}/publicar")
def publicar(relatorio_id: int, pedido: PublicarPedido) -> Relatorio:
    """Posta no canal do projeto: o resumo e uma mensagem por responsável. Uma vez só."""
    caminho = _caminho()
    dados = db.obter_relatorio(relatorio_id, caminho=caminho)
    if dados is None:
        raise NaoEncontrado(f"Relatório {relatorio_id} não existe.")
    if dados["publicado_em"]:
        raise Conflito(f"Relatório {relatorio_id} já foi publicado por {dados['publicado_por']}.")
    if not dados["canal"]:
        raise EntradaInvalida("Relatório sem canal do Slack.")
    if _estruturado(dados["texto"]):
        mensagens = _mensagens_slack(dados)  # Block Kit: barra de cor e "Ver evidência"
    else:
        mensagens = [m.texto for m in gerar.separar(dados["texto"])]
    ts, link = slack_saida.publicar(dados["canal"], mensagens)
    db.marcar_relatorio_publicado(relatorio_id, pedido.quem, ts, link, caminho=caminho)
    return _montar(db.obter_relatorio(relatorio_id, caminho=caminho))
