"""Adaptador do Gmail: Gmail API (leitura com filtro do projeto) e servidor MCP oficial."""

from pydantic import ValidationError

from radar.config_errors import describe_validation_error
from radar.core.errors import FonteNaoConfigurada
from radar.fontes.gmail.config import GmailSettings
from radar.fontes.gmail.fonte import GmailFonte
from radar.fontes.gmail.mcp import GmailMcp

__all__ = ["GmailFonte", "GmailMcp", "GmailSettings", "create"]


def create() -> GmailFonte:
    """Fábrica usada pelo registro de fontes."""
    try:
        settings = GmailSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        problems = describe_validation_error(exc, "GMAIL_")
        raise FonteNaoConfigurada(f"Gmail sem configuração no .env: {problems}.") from exc
    return GmailFonte(settings)
