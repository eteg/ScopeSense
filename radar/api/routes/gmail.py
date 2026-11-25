"""Rotas específicas do Gmail (filtro aplicado, conversa e servidor MCP)."""

from typing import Annotated, Any

from fastapi import APIRouter, Body

from radar.api.deps import GmailDep, GmailMcpDep
from radar.core.models import Registro

router = APIRouter(prefix="/gmail", tags=["gmail"])


@router.get("/query")
def gmail_query(gmail: GmailDep) -> dict[str, Any]:
    """Busca do Gmail que o Radar aplica: cliente em qualquer assunto, ou equipe com termo."""
    s = gmail.settings
    return {
        "busca": gmail.build_query(),
        "regra": "e-mails com o cliente (qualquer assunto) ou da equipe citando o projeto",
        "cliente": {"contatos": s.client_contacts, "dominios": s.client_domains},
        "equipe_interna": s.participants,
        "termos_do_projeto": s.project_terms,
        "marcador": s.label,
    }


@router.get("/threads/{thread_id}")
def gmail_thread(thread_id: str, gmail: GmailDep) -> list[Registro]:
    """Uma conversa do projeto. Conversas fora do projeto voltam com 403."""
    return gmail.thread(thread_id)


@router.get("/mcp/tools", tags=["mcp"])
async def gmail_mcp_tools(mcp: GmailMcpDep) -> list[dict[str, Any]]:
    """Ferramentas do servidor MCP do Gmail e quais estão liberadas (só leitura)."""
    return await mcp.list_tools()


@router.post("/mcp/tools/{tool_name}", tags=["mcp"])
async def gmail_mcp_call(
    tool_name: str,
    mcp: GmailMcpDep,
    arguments: Annotated[dict[str, Any], Body(default_factory=dict)],
) -> dict[str, Any]:
    """Executa uma ferramenta MCP de LEITURA; buscas precisam do filtro do projeto."""
    return await mcp.call(tool_name, arguments)
