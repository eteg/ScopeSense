"""Adaptador do Slack: Web API (leitura determinística) e servidor MCP oficial."""

from pydantic import ValidationError

from radar.core.errors import FonteNaoConfigurada
from radar.fontes.slack.config import SlackSettings
from radar.fontes.slack.fonte import SlackFonte
from radar.fontes.slack.mcp import SlackMcp

__all__ = ["SlackFonte", "SlackMcp", "SlackSettings", "create"]


def create() -> SlackFonte:
    """Fábrica usada pelo registro de fontes."""
    try:
        settings = SlackSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = ", ".join(f"SLACK_{str(e['loc'][0]).upper()}" for e in exc.errors())
        raise FonteNaoConfigurada(f"Slack sem configuração no .env: {missing}.") from exc
    return SlackFonte(settings)
