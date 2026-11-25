import base64
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from mcp.types import Tool, ToolAnnotations
from pydantic import ValidationError

from radar.api.app import app
from radar.api.deps import get_registry
from radar.config_errors import describe_validation_error
from radar.core.errors import EscritaBloqueada, FonteNaoConfigurada, ForaDoEscopo
from radar.core.models import Consulta, Origem
from radar.fontes.gmail import GmailFonte, GmailSettings
from radar.fontes.gmail.config import GmailAuthSettings
from radar.fontes.gmail.mcp import GMAIL_POLICY, project_scope_enforcer
from radar.fontes.gmail.readonly import GoogleTokenProvider, ReadOnlyGmailClient
from radar.fontes.registry import FonteRegistry

CLIENTE = "contato@smartfit.com.br"
GESTOR = "gestor@eteg.com.br"
DEV = "dev@eteg.com.br"


def settings(**overrides: Any) -> GmailSettings:
    values: dict[str, Any] = {
        "client_contacts": CLIENTE.upper(),
        "client_domains": "@SmartFit.com.br",
        "participants": f"{GESTOR},{DEV}",
        "project_terms": "SmartFit",
        "token_file": "/nao/existe.json",
    }
    values.update(overrides)
    return GmailSettings(_env_file=None, **values)  # type: ignore[call-arg]


def b64(text: str) -> str:
    return base64.urlsafe_b64encode(text.encode()).decode().rstrip("=")


def message(
    msg_id: str, ts: int, sender: str, to: str, subject: str, body: str, labels=None
) -> dict:
    return {
        "id": msg_id,
        "threadId": "t1",
        "internalDate": str(ts * 1000),
        "labelIds": labels or ["INBOX"],
        "payload": {
            "mimeType": "multipart/mixed",
            "headers": [
                {"name": "From", "value": sender},
                {"name": "To", "value": to},
                {"name": "Subject", "value": subject},
            ],
            "parts": [
                {"mimeType": "text/plain", "body": {"data": b64(body)}},
                {"mimeType": "text/html", "body": {"data": b64(f"<p>{body}</p>")}},
                {"mimeType": "application/pdf", "filename": "ASO.pdf", "body": {}},
            ],
        },
    }


T0 = 1795600000  # 2026-11-25
MESSAGES = {
    # Cliente escrevendo sobre outro assunto, sem citar o projeto: entra.
    "m1": message("m1", T0 + 300, f"Cliente <{CLIENTE}>", GESTOR, "Vídeos dos exercícios",
                  "Precisamos cadastrar vídeos curtos na máquina."),
    # Equipe interna citando o projeto: entra.
    "m2": message("m2", T0 + 100, f"Ana <{GESTOR}>", DEV, "Re: SmartFit prazo", "Vamos ver."),
    # Ninguém do projeto: a segunda checagem descarta.
    "m3": message("m3", T0 + 400, "spam@x.com", "outro@x.com", "Oferta", "promo"),
    # Outra pessoa do domínio do cliente: entra.
    "m4": message("m4", T0 + 200, "Diretor <diretor@smartfit.com.br>", GESTOR, "Contrato",
                  "Segue minuta."),
}  # fmt: skip
INTERNO_SEM_TERMO = message("x1", T0, f"Ana <{GESTOR}>", DEV, "Férias", "ok")


class FakeGmail(ReadOnlyGmailClient):
    def __init__(self, thread_messages: list[dict] | None = None) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []
        self.thread_messages = thread_messages
        self.extra = {"x1": INTERNO_SEM_TERMO}

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        self.calls.append((path, params))
        if path == "profile":
            return {"emailAddress": GESTOR}
        if path == "messages":
            return {"messages": [{"id": i} for i in MESSAGES]}
        if path.startswith("messages/"):
            msg_id = path.split("/")[1]
            return MESSAGES.get(msg_id) or self.extra[msg_id]
        if path.startswith("threads/"):
            return {"messages": self.thread_messages or []}
        if path == "labels":
            return {"labels": [{"id": "Label_7", "name": "projeto-smartfit"}]}
        raise AssertionError(path)

    def token_info(self) -> dict[str, Any]:
        return {"scope": "https://mail.google.com/ openid", "expires_in": "3500"}


def make(fake: FakeGmail | None = None, **overrides: Any) -> tuple[GmailFonte, FakeGmail]:
    fake = fake or FakeGmail()
    return GmailFonte(settings(**overrides), client=fake), fake


# --- trava de só leitura e configuração ------------------------------------------


@pytest.mark.parametrize(
    "path", ["messages/send", "messages/abc/modify", "messages/abc/trash", "drafts", "settings"]
)
def test_cliente_bloqueia_endpoints_de_escrita(path: str) -> None:
    class SemToken:
        def token(self) -> str:
            raise AssertionError("não deveria chegar a pedir token")

    with pytest.raises(EscritaBloqueada):
        ReadOnlyGmailClient(SemToken()).get(path)


def test_configuracao_normaliza_e_exige_um_filtro() -> None:
    s = settings()
    assert s.client_contacts == [CLIENTE] and s.client_domains == ["smartfit.com.br"]
    # Só cliente já basta.
    assert settings(participants="", project_terms="").has_client
    # Só equipe interna sem termo/marcador não basta (pegaria outros projetos).
    with pytest.raises(ValueError, match="GMAIL_CLIENT_CONTACTS"):
        settings(client_contacts="", client_domains="", project_terms="")


def test_sem_credencial_vira_fonte_nao_configurada() -> None:
    with pytest.raises(FonteNaoConfigurada):
        GoogleTokenProvider(settings())


def test_erro_de_configuracao_nao_mostra_valores() -> None:
    with pytest.raises(ValidationError) as info:
        GmailSettings(_env_file=None, access_token="ya29.SEGREDO")  # type: ignore[call-arg]
    mensagem = describe_validation_error(info.value, "GMAIL_")
    assert "GMAIL_CLIENT_CONTACTS" in mensagem
    assert "SEGREDO" not in mensagem


def test_autorizacao_so_precisa_da_credencial() -> None:
    assert GmailAuthSettings(_env_file=None).token_file.name == "gmail_token.json"  # type: ignore[call-arg]


# --- regra do projeto -------------------------------------------------------------


def test_busca_combina_cliente_e_equipe_com_termo() -> None:
    gmail, _ = make(label="projeto smartfit")
    query = gmail.build_query(desde=datetime(2026, 11, 25, tzinfo=UTC))
    cliente, _, equipe = query.partition(" OR ")
    assert f"from:{CLIENTE}" in cliente and "cc:smartfit.com.br" in cliente
    assert '"SmartFit"' not in cliente  # cliente entra em qualquer assunto
    assert f"to:{DEV}" in equipe and '"SmartFit"' in equipe and "label:projeto-smartfit" in equipe
    assert query.endswith("-in:spam -in:trash after:1795564800")


def test_busca_so_com_cliente() -> None:
    gmail, _ = make(participants="", project_terms="")
    query = gmail.build_query()
    assert " OR " not in query and query.startswith("{from:")


def test_fetch_inclui_cliente_em_qualquer_assunto_e_descarta_quem_nao_e_do_projeto() -> None:
    gmail, fake = make()
    registros = gmail.fetch(Consulta(limite=10))
    assert [r.id for r in registros] == ["email:m2", "email:m4", "email:m1"]
    assert registros[-1].texto.startswith("Assunto: Vídeos dos exercícios")
    assert registros[-1].metadados["anexos"] == ["ASO.pdf"]
    busca = next(p for path, p in fake.calls if path == "messages")
    assert busca["q"] == gmail.build_query()


def test_thread_do_cliente_entra_e_interna_sem_termo_nao() -> None:
    gmail, _ = make(FakeGmail(thread_messages=[MESSAGES["m1"], MESSAGES["m3"]]))
    assert [r.id for r in gmail.thread("t1")] == ["email:m1"]

    gmail, _ = make(FakeGmail(thread_messages=[INTERNO_SEM_TERMO]))
    with pytest.raises(ForaDoEscopo):
        gmail.thread("t9")


def test_thread_interna_aceita_pelo_marcador() -> None:
    marcada = message("x2", T0, f"Ana <{GESTOR}>", DEV, "Reunião", "pauta", labels=["Label_7"])
    gmail, _ = make(FakeGmail(thread_messages=[marcada]), label="projeto-smartfit")
    assert [r.id for r in gmail.thread("t2")] == ["email:x2"]


def test_status_mostra_regra_e_aponta_escopo_alem_de_leitura() -> None:
    gmail, _ = make()
    status = gmail.status()
    assert status["conta"] == GESTOR
    assert status["cliente"]["dominios"] == ["smartfit.com.br"]
    assert status["escopos_alem_de_leitura"] == ["https://mail.google.com/"]
    assert status["aviso"]


# --- MCP ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "read_only", "expected"),
    [  # nomes e anotações reais do servidor MCP do Gmail
        ("search_threads", True, True),
        ("get_thread", True, True),
        ("get_message", True, True),
        ("list_labels", True, True),  # liberada na política, mas recusada no escopo
        ("list_drafts", True, False),
        ("get_draft", True, False),
        ("create_draft", False, False),
        ("trash_thread", False, False),
        ("update_message_labels", False, False),
    ],
)
def test_politica_mcp_do_gmail(name: str, read_only: bool, expected: bool) -> None:
    tool = Tool(name=name, input_schema={"type": "object"},
                annotations=ToolAnnotations(read_only_hint=read_only))  # fmt: skip
    assert GMAIL_POLICY.evaluate(tool)[0] is expected


def test_mcp_impoe_o_escopo_do_projeto() -> None:
    gmail, _ = make(FakeGmail(thread_messages=[INTERNO_SEM_TERMO]))
    enforce = project_scope_enforcer(gmail)

    # A busca de quem chama fica sempre dentro do filtro do projeto.
    args = enforce("search_threads", {"query": "from:qualquer@x.com OR is:unread", "pageSize": 5})
    assert args["query"] == f"{gmail.build_query()} (from:qualquer@x.com OR is:unread)"
    assert args["pageSize"] == 5
    assert enforce("search_threads", {})["query"] == gmail.build_query()

    # Leitura por ID é conferida pela Gmail API antes.
    assert enforce("get_message", {"messageId": "m1"}) == {"messageId": "m1"}
    with pytest.raises(ForaDoEscopo):
        enforce("get_message", {"messageId": "x1"})
    with pytest.raises(ForaDoEscopo):
        enforce("get_thread", {"threadId": "t9"})
    with pytest.raises(ForaDoEscopo):
        enforce("list_labels", {})


# --- API ----------------------------------------------------------------------------


def test_rota_generica_do_gmail() -> None:
    gmail, _ = make()
    app.dependency_overrides[get_registry] = lambda: FonteRegistry({Origem.email: lambda: gmail})
    try:
        client = TestClient(app)
        response = client.get("/fontes/email/registros")
        assert [r["id"] for r in response.json()] == ["email:m2", "email:m4", "email:m1"]
        assert client.get("/gmail/query").json()["busca"] == gmail.build_query()
    finally:
        app.dependency_overrides.clear()


def test_contato_com_email_publico_funciona_mas_dominio_publico_nao() -> None:
    contato_gmail = "cliente.smartfit@gmail.com"
    gmail, _ = make(client_contacts=contato_gmail, client_domains="")
    msg = message("g1", T0, f"Cliente <{contato_gmail}>", GESTOR, "Qualquer assunto", "oi")
    assert gmail.belongs_to_project(msg)
    outro = message("g2", T0, "Outro <alguem@gmail.com>", GESTOR, "Qualquer assunto", "oi")
    assert not gmail.belongs_to_project(outro)

    with pytest.raises(ValueError, match="domínio de e-mail público"):
        settings(client_domains="gmail.com")
    with pytest.raises(ValueError, match="domínio da equipe"):
        settings(client_domains="eteg.com.br")
