"""Servidor MCP oficial do Slack (https://mcp.slack.com/mcp), só leitura.

O Slack não publica o nome de todas as ferramentas; elas são descobertas em
tempo de execução e filtradas pela política abaixo. A busca fica bloqueada
porque cobre o workspace inteiro, não só os canais do projeto.
"""

import re
from typing import Any

from radar.core.errors import ForaDoEscopo
from radar.fontes.slack.config import SlackSettings
from radar.mcp.client import ReadOnlyMcpClient
from radar.mcp.policy import ReadOnlyPolicy, tool_words

SLACK_POLICY = ReadOnlyPolicy(
    read_verbs=("read", "list"),
    blocked_terms={"search": "busca no workspace inteiro (fora do escopo do projeto)"},
    # Ferramentas de leitura que não recebem canal: alcançariam dados de fora do projeto.
    blocked_tools={
        "slack_read_file": "lê arquivo pelo ID, sem garantia de ser de um canal do projeto",
        "slack_list_user_channels": "lista todos os canais do usuário, não só os do projeto",
    },
)
CHANNEL_ID = re.compile(r"^[CG][A-Z0-9]{8,}$")


def _strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        return [s for v in value.values() for s in _strings(v)]
    if isinstance(value, list):
        return [s for v in value for s in _strings(v)]
    return []


def channel_validator(allowed: set[str]):
    """Valida que a ferramenta só recebe canais do projeto."""

    def validate(tool_name: str, arguments: dict[str, Any]) -> None:
        channel_ids = [s for s in _strings(arguments) if CHANNEL_ID.match(s)]
        blocked = [c for c in channel_ids if c not in allowed]
        if blocked:
            raise ForaDoEscopo(f"Canal fora do projeto: {', '.join(blocked)}.")
        if tool_words(tool_name) & {"channel", "thread"} and not channel_ids:
            raise ForaDoEscopo("Informe um canal do projeto (SLACK_CHANNEL_IDS) nos argumentos.")

    return validate


class SlackMcp:
    def __init__(self, settings: SlackSettings) -> None:
        self._client = ReadOnlyMcpClient(settings.mcp_url, settings.user_token, SLACK_POLICY)
        self._validate = channel_validator(set(settings.channel_ids))

    async def list_tools(self) -> list[dict[str, Any]]:
        return await self._client.list_tools()

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._client.call_read_tool(tool_name, arguments, self._validate)
