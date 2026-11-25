"""Cliente da Gmail API que só faz leitura.

Travas: o escopo pedido é só `gmail.readonly`; este cliente só tem método GET
e só aceita uma lista fixa de endpoints de leitura.
"""

import re
from typing import Any, Protocol

import httpx
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from radar.core.errors import AcessoNegado, EscritaBloqueada, FalhaNaFonte, FonteNaoConfigurada
from radar.fontes.gmail.config import GMAIL_SCOPES, GmailSettings

API = "https://gmail.googleapis.com/gmail/v1/users/me"
TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"

READ_ONLY_PATHS = (
    re.compile(r"^profile$"),
    re.compile(r"^messages$"),
    re.compile(r"^messages/[A-Za-z0-9_-]+$"),
    # Conteúdo de um anexo (ex.: o contrato em PDF). Leitura, coberta por gmail.readonly.
    re.compile(r"^messages/[A-Za-z0-9_-]+/attachments/[A-Za-z0-9_-]+$"),
    re.compile(r"^threads/[A-Za-z0-9_-]+$"),
    re.compile(r"^labels$"),
)
# Ações da Gmail API que poderiam ser confundidas com um ID no caminho.
WRITE_ACTIONS = frozenset(
    {"send", "import", "insert", "modify", "trash", "untrash", "batchDelete", "batchModify",
     "watch", "stop", "delete"}
)  # fmt: skip


class TokenProvider(Protocol):
    def token(self) -> str: ...


class GoogleTokenProvider:
    """Entrega um access token válido, renovando pelo refresh token quando há."""

    def __init__(self, settings: GmailSettings) -> None:
        if settings.token_file.exists():
            self._creds = Credentials.from_authorized_user_file(
                str(settings.token_file), GMAIL_SCOPES
            )
            self._file = settings.token_file
        elif settings.access_token:
            self._creds = Credentials(token=settings.access_token)  # sem renovação
            self._file = None
        else:
            raise FonteNaoConfigurada(
                "Gmail sem credencial: rode `python -m radar.fontes.gmail.autorizar` "
                "ou defina GMAIL_ACCESS_TOKEN (temporário)."
            )

    def token(self) -> str:
        if not self._creds.valid:
            if not self._creds.refresh_token:
                raise AcessoNegado(
                    "Token do Gmail expirado e sem refresh token. Gere outro ou rode "
                    "`python -m radar.fontes.gmail.autorizar`."
                )
            try:
                self._creds.refresh(Request())
            except Exception as exc:
                raise AcessoNegado(f"Não foi possível renovar o token do Gmail: {exc}") from exc
            if self._file:
                self._file.write_text(self._creds.to_json())
        return self._creds.token  # type: ignore[return-value]


class ReadOnlyGmailClient:
    def __init__(self, tokens: TokenProvider, http: httpx.Client | None = None) -> None:
        self._tokens = tokens
        self._http = http or httpx.Client(timeout=30)

    def get(self, path: str, **params: Any) -> dict[str, Any]:
        reserved = set(path.split("/")) & WRITE_ACTIONS
        if reserved or not any(pattern.match(path) for pattern in READ_ONLY_PATHS):
            raise EscritaBloqueada(f"Endpoint Gmail '{path}' bloqueado: o Radar só faz leitura.")
        headers = {"Authorization": f"Bearer {self._tokens.token()}"}
        return self._request(f"{API}/{path}", params, headers)

    def token_info(self) -> dict[str, Any]:
        """Conta e escopos do token (endpoint público de inspeção do Google)."""
        return self._request(TOKENINFO, {"access_token": self._tokens.token()}, {})

    def _request(self, url: str, params: dict[str, Any], headers: dict[str, str]) -> dict:
        try:
            response = self._http.get(url, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise FalhaNaFonte(f"Falha ao falar com o Google: {exc}") from exc
        if response.status_code in (400, 401, 403) and "tokeninfo" in url:
            raise AcessoNegado("Token do Google inválido ou expirado.")
        if response.status_code in (401, 403):
            raise AcessoNegado(f"Google recusou o acesso ({response.status_code}): {response.text}")
        if response.status_code >= 400:
            raise FalhaNaFonte(f"Gmail respondeu {response.status_code}: {response.text}")
        return response.json()
