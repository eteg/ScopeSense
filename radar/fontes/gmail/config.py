from pathlib import Path
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# Único escopo que o Radar pede ao Google para o Gmail.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Domínios de e-mail gratuito: nunca valem como "domínio do cliente".
PUBLIC_EMAIL_DOMAINS = frozenset(
    {"gmail.com", "googlemail.com", "hotmail.com", "outlook.com", "live.com", "msn.com",
     "yahoo.com", "yahoo.com.br", "icloud.com", "me.com", "uol.com.br", "bol.com.br",
     "terra.com.br", "ig.com.br", "proton.me", "protonmail.com", "aol.com"}
)  # fmt: skip


class GmailAuthSettings(BaseSettings):
    """Só a credencial (GMAIL_* do .env). Basta isto para gerar o token."""

    model_config = SettingsConfigDict(
        env_prefix="GMAIL_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Credencial: arquivo com refresh token (gerado por `python -m radar.fontes.gmail.autorizar`)
    token_file: Path = Path(".secrets/gmail_token.json")
    # ...ou um access token temporário (ya29..., expira em ~1h), só para teste rápido.
    access_token: str | None = Field(default=None, repr=False)
    # Cliente OAuth (Desktop) baixado do Google Cloud, usado só pelo script de autorização.
    client_secret_file: Path = Path(".secrets/gmail_client_secret.json")


class GmailSettings(GmailAuthSettings):
    """Credencial + filtro do projeto (veja .env.example)."""

    # Cliente do projeto: QUALQUER e-mail de/para/cc destes contatos ou domínios entra,
    # seja qual for o assunto.
    client_contacts: Annotated[list[str], NoDecode] = Field(default_factory=list)
    client_domains: Annotated[list[str], NoDecode] = Field(default_factory=list)

    # Equipe interna. E-mails só entre a equipe entram apenas com termo ou marcador do
    # projeto (senão entraria conversa interna de outros projetos).
    participants: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Termos que identificam o projeto (assunto ou corpo). Ex.: "SmartFit".
    project_terms: Annotated[list[str], NoDecode] = Field(default_factory=list)
    # Marcador do Gmail aplicado por filtro (alternativa ou complemento aos termos).
    label: str | None = None

    mcp_url: str = "https://gmailmcp.googleapis.com/mcp/v1"

    @field_validator(
        "client_contacts", "client_domains", "participants", "project_terms", mode="before"
    )
    @classmethod
    def _split_csv(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("client_contacts", "participants")
    @classmethod
    def _lower(cls, value: list[str]) -> list[str]:
        return [email.lower() for email in value]

    @field_validator("client_domains")
    @classmethod
    def _normalize_domain(cls, value: list[str]) -> list[str]:
        domains = [domain.lower().lstrip("@") for domain in value]
        public = sorted(set(domains) & PUBLIC_EMAIL_DOMAINS)
        if public:
            raise ValueError(
                f"domínio de e-mail público em GMAIL_CLIENT_DOMAINS ({', '.join(public)}): "
                "cadastre os contatos em GMAIL_CLIENT_CONTACTS"
            )
        return domains

    @property
    def has_client(self) -> bool:
        return bool(self.client_contacts or self.client_domains)

    @property
    def has_markers(self) -> bool:
        return bool(self.project_terms or self.label)

    @model_validator(mode="after")
    def _project_filter_required(self) -> "GmailSettings":
        team_domains = {email.rsplit("@", 1)[-1] for email in self.participants}
        overlap = sorted(set(self.client_domains) & team_domains)
        if overlap:
            raise ValueError(
                f"GMAIL_CLIENT_DOMAINS contém o domínio da equipe ({', '.join(overlap)}): "
                "isso incluiria todos os e-mails internos; use GMAIL_CLIENT_CONTACTS"
            )
        if not self.has_client and not (self.participants and self.has_markers):
            raise ValueError(
                "defina GMAIL_CLIENT_CONTACTS ou GMAIL_CLIENT_DOMAINS, "
                "ou GMAIL_PARTICIPANTS com GMAIL_PROJECT_TERMS/GMAIL_LABEL"
            )
        return self
