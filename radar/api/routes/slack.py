"""Rotas específicas do Slack (detalhe de canal, thread e servidor MCP)."""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Query

from radar.api.deps import SlackDep, SlackMcpDep
from radar.core.models import Registro

router = APIRouter(prefix="/slack", tags=["slack"])


@router.get("/channels")
def slack_channels(slack: SlackDep) -> list[dict[str, Any]]:
    """Canais do projeto configurados em SLACK_CHANNEL_IDS."""
    return slack.list_channels()


@router.get("/channels/{channel_id}/messages")
def slack_channel_messages(
    channel_id: str,
    slack: SlackDep,
    oldest: Annotated[str | None, Query(description="Timestamp Slack/Unix inicial")] = None,
    latest: Annotated[str | None, Query(description="Timestamp Slack/Unix final")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    include_threads: Annotated[bool, Query(description="Inclui respostas das threads")] = False,
) -> list[Registro]:
    """Mensagens do canal como Registros, da mais antiga para a mais nova."""
    return slack.channel_messages(
        channel_id, oldest=oldest, latest=latest, limit=limit, include_threads=include_threads
    )


@router.get("/channels/{channel_id}/threads/{thread_ts}")
def slack_thread(channel_id: str, thread_ts: str, slack: SlackDep) -> list[Registro]:
    """Mensagem raiz e respostas de uma thread."""
    return slack.thread_replies(channel_id, thread_ts)


@router.get("/mcp/tools", tags=["mcp"])
async def slack_mcp_tools(mcp: SlackMcpDep) -> list[dict[str, Any]]:
    """Ferramentas do servidor MCP do Slack e quais estão liberadas (só leitura)."""
    return await mcp.list_tools()


@router.post("/mcp/tools/{tool_name}", tags=["mcp"])
async def slack_mcp_call(
    tool_name: str,
    mcp: SlackMcpDep,
    arguments: Annotated[dict[str, Any], Body(default_factory=dict)],
) -> dict[str, Any]:
    """Executa uma ferramenta MCP de LEITURA. Ferramentas de escrita são recusadas (403)."""
    return await mcp.call(tool_name, arguments)
