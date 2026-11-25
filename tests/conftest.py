import re
from typing import Any

import pytest

from radar.core.errors import EscritaBloqueada
from radar.fontes.slack import SlackFonte, SlackSettings
from radar.fontes.slack.readonly import READ_ONLY_METHODS, ReadOnlySlackClient

TEAM = "T123456789"
CANAL = "C111111111"
OUTRO_CANAL = "C999999999"


class FakeSlack(ReadOnlySlackClient):
    """Responde a partir de um dicionário, mantendo a trava de leitura do cliente real.

    O valor pode ser a resposta, uma função dos parâmetros ou uma exceção a levantar.
    """

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        if method not in READ_ONLY_METHODS:
            raise EscritaBloqueada(method)
        self.calls.append((method, params))
        response = self.responses[method]
        if isinstance(response, Exception):
            raise response
        return response(params) if callable(response) else response


def default_responses() -> dict[str, Any]:
    return {
        "auth.test": {"ok": True, "team_id": TEAM, "url": "https://teste.slack.com/"},
        "users.info": {"user": {"name": "ana", "profile": {"display_name": "Ana Gestora"}}},
        "conversations.history": {
            "messages": [
                {"ts": "1700000002.000200", "user": "U1", "text": "a gente faz", "reply_count": 1},
                {"ts": "1700000001.000100", "subtype": "channel_join", "user": "U1", "text": "x"},
                {"ts": "1700000000.000100", "user": "U1", "text": "Bom dia"},
            ],
            "has_more": False,
        },
        "conversations.replies": {
            "messages": [
                {"ts": "1700000002.000200", "user": "U1", "text": "a gente faz"},
                {"ts": "1700000003.000300", "user": "U1", "text": "resposta",
                 "thread_ts": "1700000002.000200"},
            ],
            "has_more": False,
        },
    }  # fmt: skip


def slack_settings() -> SlackSettings:
    return SlackSettings(
        _env_file=None,  # type: ignore[call-arg]
        team_id=TEAM,
        user_token="xoxp-fake",
        channel_ids=[CANAL],
    )


CLAUSULA_22 = {
    "numero": "2.2",
    "texto": "Fora do escopo: módulo de relatórios e treinamento presencial.",
    "tipo": "escopo",
    "distancia": 0.1,
}
CLAUSULA_61 = {
    "numero": "6.1",
    "texto": "Documentos do subcontratado exigidos antes de iniciar a atuação: ASO válido.",
    "tipo": "terceiro",
    "distancia": 0.2,
}
_TERCEIROS = ("joão", "carla", "nimbus")


def buscador_falso(texto: str) -> list[dict]:
    """Substitui o RAG: a cláusula 2.2 fixa, e a 6.1 quando o texto fala do terceiro."""
    achados = [dict(CLAUSULA_22)]
    if any(nome in texto.lower() for nome in _TERCEIROS):
        achados.append(dict(CLAUSULA_61))
    return achados


def modelo_falso(modelo, system, user, schema, temperatura=0.0):
    """Substitui o modelo com o comportamento do stub antigo do R-02, sem rede.

    "relatórios" => escopo_extra 0,9 (cláusula 2.2); "João" ou "Carla" com "começa" =>
    terceiro_sem_documento 0,7 (cláusula 6.1); o resto => nenhum.
    """
    from radar.core.models import SaidaClassificacao, TipoDesvio

    evidencia = re.search(r"<evidencia[^>]*>(.*?)</evidencia>", user, re.S).group(1)
    baixo = evidencia.lower()
    if "relatórios" in baixo:
        return SaidaClassificacao(
            tipo=TipoDesvio.escopo_extra,
            confianca=0.9,
            clausula="2.2",
            trecho_contrato="módulo de relatórios",
            trecho_evidencia="relatórios",
            justificativa="Valor de teste: a conversa trata de um módulo que a cláusula exclui.",
        )
    nome = re.search(r"João|Carla", evidencia)
    if nome and "começa" in baixo:
        return SaidaClassificacao(
            tipo=TipoDesvio.terceiro_sem_documento,
            confianca=0.7,
            clausula="6.1",
            trecho_contrato="documentos do subcontratado exigidos",
            trecho_evidencia=nome.group(0),
            justificativa="Valor de teste: terceiro vai começar; confira os documentos.",
        )
    return SaidaClassificacao(
        tipo=TipoDesvio.nenhum,
        confianca=0.9,
        clausula="",
        trecho_contrato="",
        trecho_evidencia="",
        justificativa="Valor de teste: nada contradiz o contrato.",
    )


@pytest.fixture(autouse=True)
def sem_rede_nem_chroma(monkeypatch):
    """Nenhum teste chama o modelo nem o ChromaDB sem pedir: os nós usam estes falsos.

    Os testes de `classificar` e de `buscar` passam funções explícitas (`chamar=`,
    `buscador=`) ou guardam a função original no import para exercitar o código real.
    """
    from radar.nos import buscar, classificar

    monkeypatch.setattr(classificar, "chamar_modelo", modelo_falso)
    monkeypatch.setattr(buscar, "buscar_no_indice", buscador_falso)


@pytest.fixture
def make_slack():
    def _make(**overrides: Any) -> tuple[SlackFonte, FakeSlack]:
        fake = FakeSlack({**default_responses(), **overrides})
        return SlackFonte(slack_settings(), client=fake), fake

    return _make
