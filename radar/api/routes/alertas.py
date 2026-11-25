"""Fila de alertas da tela web: os alertas do pipeline e a decisão humana sobre cada um.

Decidir aqui grava no mesmo SQLite que o nó `registrar` e os botões do Slack usam
(`db.registrar_decisao`). Só "Notificar por Slack" posta: uma mensagem por alerta
no canal do projeto, marcando o responsável (radar/relatorio/slack_saida.py).
"""

from datetime import datetime
from typing import Annotated, Literal, cast
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from radar import config, db, painel
from radar.api.deps import (
    ProjetoJsonDep,
    ProjetoStoreDep,
    RegistryDep,
    config_atual,
)
from radar.core.errors import Conflito, EntradaInvalida, NaoEncontrado, RadarError
from radar.core.models import Decisao, Origem
from radar.fontes.slack import SlackFonte
from radar.relatorio import estrutura, slack_saida

router = APIRouter(prefix="/alertas", tags=["alertas"])
FUSO = ZoneInfo("America/Sao_Paulo")


class DecisaoPedido(BaseModel):
    acao: Literal["aprovar", "descartar", "nao_e_desvio"]
    quem: str = Field(min_length=1, max_length=120)


def _caminho() -> str:
    caminho = config.DATABASE_PATH  # lido na hora (os testes trocam o banco)
    db.init_db(caminho)
    return caminho


def _obter(alerta_id: str, caminho: str) -> painel.AlertaTela:
    for alerta in painel.listar(caminho=caminho):
        if alerta.id == alerta_id:
            return alerta
    raise NaoEncontrado(f"Alerta {alerta_id} não existe.")


@router.get("")
def listar_alertas() -> list[painel.AlertaTela]:
    """Crítico primeiro; no empate, o mais antigo."""
    return painel.listar(caminho=_caminho())


@router.get("/resumo")
def resumo() -> painel.Resumo:
    """Quantos registros o Radar leu, por origem, e quando saiu o último alerta."""
    return painel.resumo(caminho=_caminho())


@router.post("/{alerta_id}/decisao")
def decidir(alerta_id: str, pedido: DecisaoPedido) -> painel.AlertaTela:
    """Aprovar, descartar ou "não é desvio". 409 se já foi decidido (pela tela ou pelo Slack)."""
    caminho = _caminho()
    _obter(alerta_id, caminho)
    decisao = Decisao(
        alerta_id=alerta_id, acao=pedido.acao, quem=pedido.quem, quando=datetime.now(FUSO)
    )
    if not db.registrar_decisao(decisao, caminho=caminho):
        raise Conflito(f"Alerta {alerta_id} já foi decidido.")
    return _obter(alerta_id, caminho)


@router.delete("/{alerta_id}/decisao")
def desfazer(
    alerta_id: str, quem: Annotated[str, Query(min_length=1, max_length=120)]
) -> painel.AlertaTela:
    """Botão "Desfazer": o alerta volta para pendente."""
    caminho = _caminho()
    _obter(alerta_id, caminho)
    if not db.desfazer_decisao(alerta_id, caminho=caminho):
        raise Conflito(f"Alerta {alerta_id} ainda não foi decidido.")
    return _obter(alerta_id, caminho)


class NotificarPedido(BaseModel):
    quem: str = Field(min_length=1, max_length=120)


_EMOJI = {
    "critico": ":red_circle:",
    "medio": ":large_orange_circle:",
    "baixo": ":large_yellow_circle:",
}
_GRAVIDADE = {"critico": "Crítica", "medio": "Média", "baixo": "Baixa"}
_PAPEL = {
    "gestor": "Gestor do projeto",
    "comercial": "Comercial",
    "administrativo_contratos": "Administrativo de contratos",
}


def mensagem_slack(a: painel.AlertaTela, marcacao: str, quem: str) -> dict:
    """Mensagem Block Kit do alerta: marca quem age, barra colorida pela severidade,
    título, categoria/cláusula/fonte e o botão "Ver evidência" (só com link real)."""
    sev = a.gravidade.value
    papel = _PAPEL.get(a.responsavel.value if a.responsavel else "", "")
    fonte = "Registro " + a.id
    if a.evidencia:
        origem = a.evidencia.origem.value.replace("email", "e-mail").capitalize()
        fonte = f"{origem}, {a.evidencia.autor}, {a.evidencia.data.astimezone(FUSO):%d/%m}"
    identificado = a.justificativa.replace("[gabarito]", "").strip()
    identificado = identificado[:1].upper() + identificado[1:]
    secao: dict = {
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*{estrutura.EMOJI[sev]} {estrutura.esc(a.titulo)}*"
                 + ("" if identificado.rstrip(".").startswith(a.titulo) else
                    f"\n{estrutura.esc(identificado)}")},
    }  # fmt: skip
    link = a.evidencia.link if a.evidencia else None
    if link and link.startswith("https://"):
        secao["accessory"] = {
            "type": "button",
            "text": {"type": "plain_text", "text": "Ver evidência"},
            "url": link,
            "action_id": "ver_evidencia",
        }
    detalhe = " · ".join([a.categoria, f"cl. {a.clausula}", fonte])
    return {
        "text": f"{marcacao} Divergência {_GRAVIDADE[sev].lower()}: {a.titulo}",
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text":
                f"{marcacao} *Divergência {_GRAVIDADE[sev].lower()}* para você"
                + (f" ({papel})" if papel else "")}},
        ],  # fmt: skip
        "attachments": [
            {
                "color": estrutura.COR[sev],
                "blocks": [
                    secao,
                    {"type": "context", "elements": [{"type": "mrkdwn", "text":
                        f"{estrutura.esc(detalhe)}\n_Enviado pelo Radar de Desvios por "
                        f"{estrutura.esc(quem)}. Usem a thread para discutir._"}]},
                ],  # fmt: skip
            }
        ],
    }


@router.post("/{alerta_id}/notificar")
def notificar(
    alerta_id: str,
    pedido: NotificarPedido,
    registry: RegistryDep,
    projeto_json: ProjetoJsonDep,
    store: ProjetoStoreDep,
) -> painel.AlertaTela:
    """Posta o alerta no canal do projeto marcando o responsável e grava "aprovar".

    409 se o alerta já foi decidido (nunca posta duas vezes).
    """
    caminho = _caminho()
    alerta = _obter(alerta_id, caminho)
    if alerta.status not in ("pendente", "em_resumo"):
        raise Conflito(f"Alerta {alerta_id} já foi decidido.")

    cfg = config_atual(projeto_json, store, registry)
    canal = next((c for c in cfg.canais_slack if c.id), None)
    if canal is None:
        raise EntradaInvalida("Cadastre o canal do Slack do projeto nas Configurações.")
    pessoas = [p for p in cfg.pessoas if alerta.responsavel and p.papel == alerta.responsavel]
    marcacao = "*Responsável não cadastrado*"
    if pessoas:
        slack = cast(SlackFonte, registry.get(Origem.slack))
        try:
            ids = slack.ids_por_nome([p.nome for p in pessoas])
        except RadarError:
            ids = {}
        marcacao = " ".join(
            f"<@{ids[p.nome]}>" if ids.get(p.nome) else f"*{p.nome}*" for p in pessoas
        )

    ts, _link = slack_saida.publicar(canal.id, [mensagem_slack(alerta, marcacao, pedido.quem)])
    db.atualizar_slack_msg(alerta_id, canal.id, ts, caminho=caminho)
    db.registrar_decisao(
        Decisao(alerta_id=alerta_id, acao="aprovar", quem=pedido.quem, quando=datetime.now(FUSO)),
        caminho=caminho,
    )
    return _obter(alerta_id, caminho)
