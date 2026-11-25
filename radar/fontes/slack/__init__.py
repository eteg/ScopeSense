"""Adaptador do Slack: Web API (leitura determinística) e servidor MCP oficial."""

from pydantic import ValidationError

from radar.config_errors import describe_validation_error
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
        problems = describe_validation_error(exc, "SLACK_")
        raise FonteNaoConfigurada(f"Slack sem configuração no .env: {problems}.") from exc
    return SlackFonte(settings)
