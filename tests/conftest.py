from typing import Any

import pytest

from radar.core.errors import EscritaBloqueada
from radar.fontes.slack import SlackFonte, SlackSettings
from radar.fontes.slack.readonly import READ_ONLY_METHODS, ReadOnlySlackClient

TEAM = "T123456789"
CANAL = "C111111111"
OUTRO_CANAL = "C999999999"


class FakeSlack(ReadOnlySlackClient):
    """Responde a partir de um dicionário, mantendo a trava de leitura do cliente real."""

    def __init__(self, responses: dict[str, Any]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call(self, method: str, **params: Any) -> dict[str, Any]:
        if method not in READ_ONLY_METHODS:
            raise EscritaBloqueada(method)
        self.calls.append((method, params))
        return self.responses[method]


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


@pytest.fixture
def make_slack():
    def _make(**overrides: Any) -> tuple[SlackFonte, FakeSlack]:
        fake = FakeSlack({**default_responses(), **overrides})
        return SlackFonte(slack_settings(), client=fake), fake

    return _make
