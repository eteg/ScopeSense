from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from mcp.types import Tool, ToolAnnotations

from radar.api.app import app
from radar.api.deps import get_registry
from radar.core.errors import AcessoNegado, EscritaBloqueada, ForaDoEscopo
from radar.core.models import Consulta, Origem
from radar.fontes.registry import FonteRegistry
from radar.fontes.slack.mcp import SLACK_POLICY, channel_validator
from radar.fontes.slack.readonly import ReadOnlySlackClient
from radar.mcp.policy import ReadOnlyPolicy
from tests.conftest import CANAL, OUTRO_CANAL

# --- trava de só leitura -------------------------------------------------------


@pytest.mark.parametrize(
    "method", ["chat.postMessage", "chat.delete", "reactions.add", "conversations.join"]
)
def test_cliente_bloqueia_metodos_de_escrita(method: str) -> None:
    client = ReadOnlySlackClient(token="xoxp-fake")
    with pytest.raises(EscritaBloqueada):
        client.call(method, channel=CANAL)


def _tool(name: str, read_only: bool | None) -> Tool:
    annotations = ToolAnnotations(read_only_hint=read_only) if read_only is not None else None
    return Tool(name=name, input_schema={"type": "object"}, annotations=annotations)


@pytest.mark.parametrize(
    ("name", "read_only", "expected"),
    [
        ("slack_read_channel", True, True),
        ("slack_read_thread", True, True),
        ("slack_send_message", True, False),  # nome de escrita, mesmo com anotação errada
        ("slack_read_channel", None, False),  # sem anotação de leitura
        ("slack_read_channel", False, False),
        ("slack_search_public", True, False),  # busca bloqueada no Slack
        ("slack_get_file_upload_url", True, False),
        ("slack_thread_summary", True, False),  # 'thread' não é verbo de leitura
    ],
)
def test_politica_mcp_do_slack(name: str, read_only: bool | None, expected: bool) -> None:
    assert SLACK_POLICY.evaluate(_tool(name, read_only))[0] is expected


def test_politica_generica_libera_busca_e_entende_camel_case() -> None:
    policy = ReadOnlyPolicy()  # padrão para Gmail/Calendar/Drive
    assert policy.evaluate(_tool("search_threads", True))[0] is True
    assert policy.evaluate(_tool("getMessage", True))[0] is True
    assert policy.evaluate(_tool("get_email_address", True))[0] is True  # 'address' != 'add'
    assert policy.evaluate(_tool("modifyLabels", True))[0] is False


def test_mcp_recusa_canal_fora_do_projeto() -> None:
    validate = channel_validator({CANAL})
    with pytest.raises(ForaDoEscopo):
        validate("slack_read_channel", {"channel_id": OUTRO_CANAL})
    with pytest.raises(ForaDoEscopo):
        validate("slack_read_channel", {})
    validate("slack_read_channel", {"channel_id": CANAL})


# --- adaptador ------------------------------------------------------------------


def test_mensagens_em_ordem_cronologica_sem_mensagens_de_sistema(make_slack) -> None:
    slack, _ = make_slack()
    registros = slack.channel_messages(CANAL)
    assert [r.texto for r in registros] == ["Bom dia", "a gente faz"]
    assert registros[0].autor == "Ana Gestora"
    assert registros[0].id == f"slack:{CANAL}:1700000000.000100"
    assert registros[0].link == f"https://teste.slack.com/archives/{CANAL}/p1700000000000100"


def test_fetch_inclui_threads_e_respeita_desde(make_slack) -> None:
    slack, fake = make_slack()
    todos = slack.fetch(Consulta())
    assert [r.texto for r in todos] == ["Bom dia", "a gente faz", "resposta"]
    assert all(r.origem is Origem.slack for r in todos)

    desde = datetime.fromtimestamp(1700000001, tz=UTC)
    recentes = slack.fetch(Consulta(desde=desde))
    assert [r.texto for r in recentes] == ["a gente faz", "resposta"]
    history = [p for m, p in fake.calls if m == "conversations.history"][-1]
    assert history["oldest"] == str(desde.timestamp())


def test_canal_fora_do_projeto_e_recusado_sem_chamar_o_slack(make_slack) -> None:
    slack, fake = make_slack()
    with pytest.raises(ForaDoEscopo):
        slack.fetch(Consulta(escopo=OUTRO_CANAL))
    assert fake.calls == []


def test_token_de_outro_workspace_e_recusado(make_slack) -> None:
    slack, _ = make_slack(**{"auth.test": {"ok": True, "team_id": "T_OUTRO"}})
    with pytest.raises(AcessoNegado):
        slack.channel_messages(CANAL)


# --- API ------------------------------------------------------------------------


def test_endpoints_do_slack(make_slack) -> None:
    slack, _ = make_slack()
    app.dependency_overrides[get_registry] = lambda: FonteRegistry({Origem.slack: lambda: slack})
    try:
        client = TestClient(app)
        ok = client.get(f"/slack/channels/{CANAL}/messages", params={"limit": 10})
        assert ok.status_code == 200
        assert ok.json()[0]["origem"] == "slack"
        assert client.get(f"/slack/channels/{OUTRO_CANAL}/messages").status_code == 403
        generica = client.get("/fontes/slack/registros", params={"escopo": CANAL})
        assert [r["texto"] for r in generica.json()] == ["Bom dia", "a gente faz", "resposta"]
        assert client.get("/fontes/slack/status").json()["team_id"] == "T123456789"
    finally:
        app.dependency_overrides.clear()


def test_status_aponta_escopos_de_escrita(make_slack) -> None:
    auth = {"ok": True, "team_id": "T123456789", "scopes": ["channels:history", "chat:write"]}
    slack, _ = make_slack(**{"auth.test": auth})
    status = slack.status()
    assert status["escopos_de_escrita"] == ["chat:write"]
    assert status["aviso"]

    slack, _ = make_slack(**{"auth.test": {**auth, "scopes": ["channels:history"]}})
    assert slack.status()["aviso"] is None
