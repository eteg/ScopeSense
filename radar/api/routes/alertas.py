"""Fila de alertas da tela web: os alertas do pipeline e a decisão humana sobre cada um.

Decidir aqui grava no mesmo SQLite que o nó `registrar` e os botões do Slack usam
(`db.registrar_decisao`). Só "Notificar por Slack" posta: uma mensagem por alerta
no canal do projeto, marcando o responsável (radar/relatorio/slack_saida.py).
"""

import re
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
from radar.relatorio import slack_saida

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


def mensagem_slack(a: painel.AlertaTela, marcacao: str, quem: str) -> str:
    """Texto (mrkdwn) do alerta no canal: quem age, o que foi combinado, onde apareceu."""
    onde = "Registro " + a.id
    if a.evidencia:
        origem = a.evidencia.origem.value.replace("email", "e-mail").capitalize()
        quando = a.evidencia.data.astimezone(FUSO).strftime("%d/%m %H:%M")
        onde = f"{origem}, {a.evidencia.autor}, {quando}"
        if a.evidencia.link:
            onde += f" · <{a.evidencia.link}|abrir>"
    papel = _PAPEL.get(a.responsavel.value if a.responsavel else "", "")
    grav = _GRAVIDADE[a.gravidade.value].lower()
    contrato = re.sub(r"\*\*(.+?)\*\*", r"*\1*", a.trecho_contrato)  # Markdown -> Slack
    return (
        f"{marcacao} {_EMOJI[a.gravidade.value]} *Divergência {grav}"
        f" · {a.categoria}*{f' · {papel}' if papel else ''}\n"
        f"*{a.titulo}*\n\n"
        f"*O que o contrato diz* (cláusula {a.clausula}):\n> {contrato}\n\n"
        f"*Onde apareceu* ({onde}):\n> {a.trecho_evidencia}\n\n"
        f"_Enviado pelo Radar de Desvios por {quem}. Usem esta thread para discutir._"
    )


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
