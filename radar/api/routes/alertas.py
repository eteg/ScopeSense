"""Fila de alertas da tela web: os alertas do pipeline e a decisão humana sobre cada um.

Decidir aqui grava no mesmo SQLite que o nó `registrar` e os botões do Slack usam
(`db.registrar_decisao`). Não posta nada no Slack.
"""

from datetime import datetime
from typing import Annotated, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from radar import config, db, painel
from radar.core.errors import Conflito, NaoEncontrado
from radar.core.models import Decisao

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
