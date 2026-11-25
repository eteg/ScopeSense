"""Botão "Gerar relatório": lê Slack + e-mail do período, o modelo escreve, a tela publica.

Gerar não publica nada: guarda o texto para a pessoa revisar. Só "Publicar" posta
no Slack (radar/relatorio/slack_saida.py, token de usuário).
"""

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
from radar.core.errors import Conflito, EntradaInvalida, FonteNaoConfigurada, NaoEncontrado
from radar.core.models import Origem
from radar.fontes.slack import SlackFonte
from radar.relatorio import gerar, slack_saida

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


class Relatorio(BaseModel):
    id: int
    criado_em: str
    desde: str
    ate: str
    mensagens: list[str]  # a principal e as respostas da thread
    canal_id: str | None
    canal_nome: str | None
    fontes: dict
    pessoas: list[PessoaMarcada]
    avisos: list[str]
    publicado_em: str | None
    publicado_por: str | None
    slack_link: str | None


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
        mensagens=gerar.separar(dados["texto"]),
        canal_id=dados["canal"],
        canal_nome=fontes.get("canal_nome"),
        fontes=fontes.get("contagem", {}),
        pessoas=[PessoaMarcada(**p) for p in fontes.get("pessoas", [])],
        avisos=fontes.get("avisos", []),
        publicado_em=dados["publicado_em"],
        publicado_por=dados["publicado_por"],
        slack_link=dados["slack_link"],
    )


@router.post("")
def gerar_relatorio(
    pedido: GerarPedido,
    registry: RegistryDep,
    projeto_json: ProjetoJsonDep,
    store: ProjetoStoreDep,
) -> Relatorio:
    """Lê o período, chama o modelo e guarda o rascunho (leva de 30 s a 1 min)."""
    projeto = nome_do_projeto(projeto_json)
    cfg = config_atual(projeto_json, store, registry)
    canal = next((c for c in cfg.canais_slack if c.id), None)
    if canal is None:
        raise EntradaInvalida("Cadastre o canal do Slack do projeto nas Configurações.")
    try:
        slack = cast(SlackFonte, registry.get(Origem.slack))
    except FonteNaoConfigurada as exc:
        raise FonteNaoConfigurada(f"Slack não configurado: {exc}") from exc

    nomes = [p.nome for p in cfg.pessoas]
    ids = slack.ids_por_nome(nomes) if nomes else {}
    pessoas = [gerar.Pessoa(p.nome, p.papel, ids.get(p.nome)) for p in cfg.pessoas]
    canal_nome = canal.nome or next(
        (c["nome"] for c in slack.list_channels() if c["id"] == canal.id), canal.id
    )

    ate = datetime.now(FUSO)
    desde = ate - timedelta(days=pedido.dias)
    coleta = gerar.coletar(registry, desde, ate, store.textos_dos_arquivos(projeto))
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
    texto = gerar.limpar_saida(gerar.chamar_modelo(system, user), pessoas)
    fontes = {
        "contagem": coleta.contagem(),
        "avisos": coleta.avisos,
        "canal_nome": canal_nome,
        "pessoas": [
            {"nome": p.nome, "papel": p.papel.value, "slack_id": p.slack_id} for p in pessoas
        ],
    }
    caminho = _caminho()
    relatorio_id = db.salvar_relatorio(desde, ate, texto, fontes, canal.id, caminho=caminho)
    return _montar(db.obter_relatorio(relatorio_id, caminho=caminho))


@router.get("/{relatorio_id}")
def obter(relatorio_id: int) -> Relatorio:
    dados = db.obter_relatorio(relatorio_id, caminho=_caminho())
    if dados is None:
        raise NaoEncontrado(f"Relatório {relatorio_id} não existe.")
    return _montar(dados)


@router.post("/{relatorio_id}/publicar")
def publicar(relatorio_id: int, pedido: PublicarPedido) -> Relatorio:
    """Posta no canal do projeto (principal + respostas na thread). Uma vez só."""
    caminho = _caminho()
    dados = db.obter_relatorio(relatorio_id, caminho=caminho)
    if dados is None:
        raise NaoEncontrado(f"Relatório {relatorio_id} não existe.")
    if dados["publicado_em"]:
        raise Conflito(f"Relatório {relatorio_id} já foi publicado por {dados['publicado_por']}.")
    if not dados["canal"]:
        raise EntradaInvalida("Relatório sem canal do Slack.")
    ts, link = slack_saida.publicar(dados["canal"], gerar.separar(dados["texto"]))
    db.marcar_relatorio_publicado(relatorio_id, pedido.quem, ts, link, caminho=caminho)
    return _montar(db.obter_relatorio(relatorio_id, caminho=caminho))
