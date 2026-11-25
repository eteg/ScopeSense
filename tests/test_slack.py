from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.types import Tool, ToolAnnotations

from radar.api.app import app
from radar.api.deps import get_registry
from radar.core.errors import AcessoNegado, EscritaBloqueada, ForaDoEscopo, NaoEncontrado
from radar.core.models import Consulta, Origem
from radar.fontes.registry import FonteRegistry
from radar.fontes.slack.mcp import SLACK_POLICY, channel_validator
from radar.fontes.slack.readonly import ReadOnlySlackClient
from radar.fontes.slack.texto import limpar_mencoes
from radar.mcp.policy import ReadOnlyPolicy
from tests.conftest import CANAL, OUTRO_CANAL, TEAM

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
        ("slack_read_file", True, False),  # sem canal: poderia ler arquivo de outro canal
        ("slack_list_user_channels", True, False),  # lista canais fora do projeto
        ("slack_list_channel_members", True, True),  # recebe canal, validado nos argumentos
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
    history = [p for m, p in fake.calls if m == "conversations.history"][-2]
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


def test_bloqueio_dentro_da_sessao_mcp_continua_sendo_bloqueio() -> None:
    from radar.core.errors import FalhaNaFonte
    from radar.mcp.client import _translate

    grupo = ExceptionGroup("tg", [EscritaBloqueada("slack_send_message")])
    assert isinstance(_translate(grupo, "https://mcp"), EscritaBloqueada)
    assert isinstance(_translate(ExceptionGroup("tg", [TimeoutError()]), "x"), FalhaNaFonte)


# --- menções, fuso, threads antigas e busca por e-mail ---------------------------


@pytest.mark.parametrize(
    ("cru", "limpo"),
    [
        ("<@U1> consegue até sexta?", "@Ana consegue até sexta?"),
        ("<@U1|ana> ok", "@Ana ok"),
        ("<!channel> atenção", "@channel atenção"),
        ("<!here>", "@here"),
        ("<!subteam^S123|@devs> revisem", "@devs revisem"),
        ("ver <#C111111111|projeto-x>", "ver #projeto-x"),
        ("<!date^1700000000^{date}|14/11/2023>", "14/11/2023"),
        (
            "<https://exemplo.com|doc> e <mailto:a@b.com>",
            "<https://exemplo.com|doc> e <mailto:a@b.com>",
        ),
        ("escreveu &lt;!channel&gt; literal", "escreveu &lt;!channel&gt; literal"),
    ],
)
def test_limpar_mencoes(cru: str, limpo: str) -> None:
    texto, _ = limpar_mencoes(cru, lambda uid: {"U1": "Ana"}.get(uid, uid))
    assert texto == limpo


def test_registro_sem_mencoes_que_notificam_e_ids_nos_metadados(make_slack) -> None:
    history = {
        "messages": [{"ts": "1700000000.000100", "user": "U1", "text": "<@U2> e <@U1>, <!here>"}],
        "has_more": False,
    }
    slack, _ = make_slack(**{"conversations.history": history})
    [registro] = slack.channel_messages(CANAL)
    assert "<" not in registro.texto
    assert registro.texto == "@Ana Gestora e @Ana Gestora, @here"
    assert registro.metadados["mencionados"] == ["U2", "U1"]


def test_datas_no_fuso_do_projeto(make_slack) -> None:
    slack, _ = make_slack()
    registro = slack.channel_messages(CANAL)[0]
    assert registro.data.utcoffset() == timedelta(hours=-3)
    assert registro.data == datetime.fromtimestamp(1700000000.0001, tz=UTC)
    # 1700000000 = 22:13 UTC de 14/11/2023 -> 19:13 em São Paulo
    assert (registro.data.hour, registro.data.minute) == (19, 13)


def test_desde_sem_fuso_e_lido_no_fuso_do_projeto(make_slack) -> None:
    slack, fake = make_slack()
    slack.fetch(Consulta(desde=datetime(2023, 11, 14, 19, 13, 20)))  # sem tzinfo
    history = [p for m, p in fake.calls if m == "conversations.history"][0]
    assert float(history["oldest"]) == 1700000000.0


INICIO = 1700000000.0  # início do período


def _history_com_thread_antiga(params: dict[str, Any]) -> dict[str, Any]:
    if float(params["oldest"]) >= INICIO:  # consulta do período
        return {"messages": [{"ts": "1700000500.000100", "user": "U1", "text": "nova"}]}
    # consulta de threads antigas (antes do período)
    return {
        "messages": [
            {"ts": "1699990000.000100", "user": "U1", "text": "acesso?", "reply_count": 2,
             "latest_reply": "1700000100.000100"},
            {"ts": "1699980000.000100", "user": "U1", "text": "morta", "reply_count": 1,
             "latest_reply": "1699980500.000100"},
        ]
    }  # fmt: skip


def _replies_thread_antiga(params: dict[str, Any]) -> dict[str, Any]:
    assert params["ts"] == "1699990000.000100", "thread sem resposta no período foi lida"
    return {
        "messages": [
            {"ts": "1699990000.000100", "user": "U1", "text": "acesso?"},
            {"ts": "1699995000.000100", "user": "U1", "text": "antes do período",
             "thread_ts": "1699990000.000100"},
            {"ts": "1700000100.000100", "user": "U1", "text": "ainda aguardando",
             "thread_ts": "1699990000.000100"},
        ]
    }  # fmt: skip


def test_respostas_no_periodo_de_thread_aberta_antes(make_slack) -> None:
    slack, fake = make_slack(
        **{
            "conversations.history": _history_com_thread_antiga,
            "conversations.replies": _replies_thread_antiga,
        }
    )
    registros = slack.fetch(Consulta(desde=datetime.fromtimestamp(INICIO, tz=UTC)))
    assert [r.texto for r in registros] == ["ainda aguardando", "nova"]
    assert registros[0].metadados["thread_ts"] == "1699990000.000100"
    janela = [p for m, p in fake.calls if m == "conversations.history"][1]
    assert float(janela["oldest"]) == INICIO - 30 * 86400
    assert janela["latest"] == str(INICIO)


def test_resposta_enviada_ao_canal_nao_duplica(make_slack) -> None:
    history = {
        "messages": [
            {"ts": "1700000003.000300", "user": "U1", "text": "resposta",
             "thread_ts": "1700000002.000200", "subtype": "thread_broadcast"},
            {"ts": "1700000002.000200", "user": "U1", "text": "a gente faz", "reply_count": 1},
        ]
    }  # fmt: skip
    slack, _ = make_slack(**{"conversations.history": history})
    textos = [r.texto for r in slack.channel_messages(CANAL, include_threads=True)]
    assert textos == ["a gente faz", "resposta"]


def test_busca_usuario_por_email(make_slack) -> None:
    user = {
        "user": {
            "id": "U777",
            "name": "gestor",
            "profile": {"display_name": "Gestor", "real_name": "Gestor Silva", "email": "g@x.com"},
        }
    }
    slack, fake = make_slack(**{"users.lookupByEmail": user})
    assert slack.lookup_user("g@x.com")["mencao"] == "<@U777>"
    assert ("users.lookupByEmail", {"email": "g@x.com"}) in fake.calls

    vazio, _ = make_slack(**{"users.lookupByEmail": NaoEncontrado("users_not_found")})
    app.dependency_overrides[get_registry] = lambda: FonteRegistry({Origem.slack: lambda: vazio})
    try:
        resposta = TestClient(app).get("/slack/users/lookup", params={"email": "x@y.com"})
        assert resposta.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_fuso_invalido_e_recusado() -> None:
    from pydantic import ValidationError

    from radar.fontes.slack import SlackSettings

    with pytest.raises(ValidationError):
        SlackSettings(
            _env_file=None,  # type: ignore[call-arg]
            team_id=TEAM,
            user_token="x",
            channel_ids=[CANAL],
            timezone="Lua/Base",
        )
