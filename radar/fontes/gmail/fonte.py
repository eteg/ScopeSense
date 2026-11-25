"""Adaptador do Gmail para a porta `Fonte`.

Só lê e-mails do projeto. A busca é montada no código (envolvidos + termos ou
marcador do projeto + período), e cada mensagem passa por uma segunda checagem
antes de virar Registro.
"""

import base64
import html
import re
from datetime import UTC, datetime
from email.utils import getaddresses
from typing import Any

from radar.core.errors import ForaDoEscopo
from radar.core.models import Consulta, Origem, Registro
from radar.fontes.gmail.config import GmailSettings
from radar.fontes.gmail.readonly import GoogleTokenProvider, ReadOnlyGmailClient

PAGE_SIZE = 100
READ_SCOPES = {
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.metadata",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "openid",
    "email",
    "profile",
}


class GmailFonte:
    origem = Origem.email

    def __init__(self, settings: GmailSettings, client: ReadOnlyGmailClient | None = None) -> None:
        self.settings = settings
        self._client = client or ReadOnlyGmailClient(GoogleTokenProvider(settings))
        self._internal = set(settings.participants)
        self._contacts = set(settings.client_contacts)
        self._domains = set(settings.client_domains)
        self._terms = [t.casefold() for t in settings.project_terms]
        self._label_id: str | None = None
        self._account: str | None = None

    # --- filtro do projeto --------------------------------------------------
    #
    # Regra: um e-mail é do projeto se
    #   (a) envolve o cliente (contato ou domínio em from/to/cc), qualquer assunto; ou
    #   (b) envolve a equipe interna E cita um termo do projeto ou tem o marcador.

    def build_query(self, desde: datetime | None = None, ate: datetime | None = None) -> str:
        groups = []
        if self.settings.has_client:
            client = sorted(self._contacts) + sorted(self._domains)
            groups.append("{" + " ".join(_any_field(client)) + "}")
        if self._internal and self.settings.has_markers:
            people = "{" + " ".join(_any_field(sorted(self._internal))) + "}"
            markers = [f'"{term}"' for term in self.settings.project_terms]
            if self.settings.label:
                markers.append(f"label:{self.settings.label.replace(' ', '-')}")
            groups.append(f"({people} {{{' '.join(markers)}}})")
        scope = groups[0] if len(groups) == 1 else f"({' OR '.join(groups)})"
        parts = [scope, "-in:spam", "-in:trash"]
        if desde:
            parts.append(f"after:{int(desde.timestamp())}")
        if ate:
            parts.append(f"before:{int(ate.timestamp())}")
        return " ".join(parts)

    # --- porta Fonte ------------------------------------------------------

    def status(self) -> dict[str, Any]:
        info = self._client.token_info()
        scopes = sorted((info.get("scope") or "").split())
        extra = [s for s in scopes if s not in READ_SCOPES]
        return {
            "conta": self._account_email(),
            "escopos": scopes,
            "escopos_alem_de_leitura": extra,
            "expira_em_segundos": int(info["expires_in"]) if info.get("expires_in") else None,
            "cliente": {"contatos": sorted(self._contacts), "dominios": sorted(self._domains)},
            "equipe_interna": sorted(self._internal),
            "termos_do_projeto": self.settings.project_terms,
            "marcador": self.settings.label,
            "busca": self.build_query(),
            "aviso": (
                "O token tem escopos além de leitura. O Radar não os usa, mas o recomendado é "
                "gerar outro só com gmail.readonly."
                if extra
                else None
            ),
        }

    def fetch(self, consulta: Consulta) -> list[Registro]:
        """E-mails do projeto em ordem cronológica. `escopo` = ID de uma thread (opcional)."""
        if consulta.escopo:
            registros = self.thread(consulta.escopo)
        else:
            query = self.build_query(consulta.desde, consulta.ate)
            ids: list[str] = []
            page_token: str | None = None
            while len(ids) < consulta.limite:
                params: dict[str, Any] = {
                    "q": query,
                    "maxResults": min(PAGE_SIZE, consulta.limite - len(ids)),
                }
                if page_token:
                    params["pageToken"] = page_token
                data = self._client.get("messages", **params)
                ids.extend(m["id"] for m in data.get("messages", []))
                page_token = data.get("nextPageToken")
                if not page_token:
                    break
            messages = [self._client.get(f"messages/{i}", format="full") for i in ids]
            # Segunda checagem: a busca já filtrou; aqui garantimos que há cliente ou equipe.
            registros = [self._to_registro(m) for m in messages if self._involves_someone(m)]
        registros.sort(key=lambda r: r.data)
        return registros[-consulta.limite :]

    # --- leitura específica do Gmail ----------------------------------------

    def thread(self, thread_id: str) -> list[Registro]:
        """Uma conversa, desde que pertença ao projeto (regra completa em ao menos uma mensagem)."""
        data = self._client.get(f"threads/{thread_id}", format="full")
        messages = data.get("messages", [])
        if not any(self.belongs_to_project(m) for m in messages):
            raise ForaDoEscopo(f"A conversa {thread_id} não pertence ao projeto monitorado.")
        return [self._to_registro(m) for m in messages if self._involves_someone(m)]

    # --- checagens ---------------------------------------------------------

    def message_belongs(self, message_id: str) -> bool:
        """Confere uma mensagem pelo ID (usado para limitar o MCP ao projeto)."""
        return self.belongs_to_project(self._client.get(f"messages/{message_id}", format="full"))

    def belongs_to_project(self, message: dict[str, Any]) -> bool:
        """Regra completa: cliente em qualquer assunto, ou equipe com termo/marcador."""
        addresses = _addresses(message)
        if self._involves_client(addresses):
            return True
        return bool(addresses & self._internal) and self._has_marker(message)

    def _involves_client(self, addresses: set[str]) -> bool:
        if addresses & self._contacts:
            return True
        return any(
            addr.rsplit("@", 1)[-1] == domain or addr.endswith("." + domain)
            for addr in addresses
            for domain in self._domains
        )

    def _involves_someone(self, message: dict[str, Any]) -> bool:
        addresses = _addresses(message)
        return self._involves_client(addresses) or bool(addresses & self._internal)

    def _has_marker(self, message: dict[str, Any]) -> bool:
        if self.settings.label and self._project_label_id() in message.get("labelIds", []):
            return True
        haystack = f"{_headers(message).get('subject', '')}\n{_body(message)}".casefold()
        return any(term in haystack for term in self._terms)

    def _project_label_id(self) -> str | None:
        if self._label_id is None and self.settings.label:
            wanted = self.settings.label.casefold()
            for label in self._client.get("labels").get("labels", []):
                if label.get("name", "").casefold() == wanted:
                    self._label_id = label["id"]
        return self._label_id

    def _account_email(self) -> str:
        if self._account is None:
            self._account = self._client.get("profile").get("emailAddress", "")
        return self._account

    # --- conversão --------------------------------------------------------

    def _to_registro(self, message: dict[str, Any]) -> Registro:
        headers = _headers(message)
        subject = headers.get("subject", "(sem assunto)")
        account = self._account_email()
        return Registro(
            id=f"email:{message['id']}",
            origem=Origem.email,
            data=datetime.fromtimestamp(int(message["internalDate"]) / 1000, tz=UTC),
            autor=headers.get("from", "desconhecido"),
            texto=f"Assunto: {subject}\n\n{_body(message)}".strip(),
            link=f"https://mail.google.com/mail/?authuser={account}#all/{message['id']}",
            metadados={
                "thread_id": message.get("threadId"),
                "assunto": subject,
                "para": headers.get("to"),
                "cc": headers.get("cc"),
                "message_id": headers.get("message-id"),
                "marcadores": message.get("labelIds", []),
                "anexos": _attachments(message),
            },
        )


# --- helpers -----------------------------------------------------------------


def _any_field(addresses: list[str]) -> list[str]:
    """'a@x.com' -> from:a@x.com to:a@x.com cc:a@x.com (domínio funciona igual)."""
    return [f"{field}:{addr}" for addr in addresses for field in ("from", "to", "cc")]


def _addresses(message: dict[str, Any]) -> set[str]:
    headers = _headers(message)
    # Um cabeçalho por vez: no Python 3.12+, getaddresses devolve vazio se
    # qualquer item da lista for vazio (ex.: Cc ausente).
    return {
        addr.lower()
        for h in ("from", "to", "cc", "bcc")
        if headers.get(h)
        for _, addr in getaddresses([headers[h]])
        if addr
    }


def _headers(message: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for header in (message.get("payload") or {}).get("headers", []):
        result.setdefault(header["name"].lower(), header["value"])
    return result


def _parts(part: dict[str, Any]):
    yield part
    for child in part.get("parts", []) or []:
        yield from _parts(child)


def _decode(data: str) -> str:
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")


def _body(message: dict[str, Any]) -> str:
    payload = message.get("payload") or {}
    plain, rich = [], []
    for part in _parts(payload):
        data = (part.get("body") or {}).get("data")
        if not data or part.get("filename"):
            continue
        if part.get("mimeType") == "text/plain":
            plain.append(_decode(data))
        elif part.get("mimeType") == "text/html":
            rich.append(_decode(data))
    if plain:
        return "\n".join(plain).strip()
    if rich:
        text = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", "\n".join(rich), flags=re.S | re.I)
        text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.I)
        return html.unescape(re.sub(r"<[^>]+>", " ", text)).strip()
    return message.get("snippet", "")


def _attachments(message: dict[str, Any]) -> list[str]:
    return [p["filename"] for p in _parts(message.get("payload") or {}) if p.get("filename")]
