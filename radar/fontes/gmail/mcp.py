"""Servidor MCP oficial do Gmail (gmailmcp.googleapis.com), só leitura.

Escopo do projeto imposto pelo Radar, não pedido a quem chama:
- buscas (`search_threads`): a consulta é sempre embrulhada no filtro do projeto
  montado no código (cliente em qualquer assunto, ou equipe com termo/marcador);
- leitura por ID (`get_thread`, `get_message`): antes de chamar o MCP, a conversa
  ou mensagem é conferida pela Gmail API (REST) com a mesma regra da Fonte;
- rascunhos e ferramentas sem filtro (ex.: `list_labels`) ficam fora.
"""

from typing import Any

from radar.core.errors import ForaDoEscopo
from radar.fontes.gmail.config import GmailSettings
from radar.fontes.gmail.fonte import GmailFonte
from radar.fontes.gmail.readonly import GoogleTokenProvider
from radar.mcp.client import ReadOnlyMcpClient
from radar.mcp.policy import ReadOnlyPolicy, tool_words

GMAIL_POLICY = ReadOnlyPolicy(
    blocked_terms={
        "draft": "rascunhos não são evidência do projeto",
        "drafts": "rascunhos não são evidência do projeto",
    },
)
QUERY_KEYS = ("query", "q")


def project_scope_enforcer(fonte: GmailFonte):
    """Devolve os argumentos com o escopo do projeto imposto (ou recusa a chamada)."""

    def enforce(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        words = tool_words(tool_name)
        if "search" in words:
            key = next((k for k in QUERY_KEYS if k in arguments), "query")
            user_query = str(arguments.get(key) or "").strip()
            scope = fonte.build_query()
            return {**arguments, key: f"{scope} ({user_query})" if user_query else scope}
        if "thread" in words and arguments.get("threadId"):
            fonte.thread(str(arguments["threadId"]))  # ForaDoEscopo se não for do projeto
            return arguments
        if "message" in words and arguments.get("messageId"):
            if not fonte.message_belongs(str(arguments["messageId"])):
                raise ForaDoEscopo(
                    f"A mensagem {arguments['messageId']} não pertence ao projeto monitorado."
                )
            return arguments
        raise ForaDoEscopo(
            f"A ferramenta '{tool_name}' não tem como ser limitada ao projeto monitorado."
        )

    return enforce


class GmailMcp:
    def __init__(self, settings: GmailSettings, fonte: GmailFonte | None = None) -> None:
        self._settings = settings
        self._tokens = GoogleTokenProvider(settings)
        self._enforce = project_scope_enforcer(fonte or GmailFonte(settings))

    def _client(self) -> ReadOnlyMcpClient:
        return ReadOnlyMcpClient(self._settings.mcp_url, self._tokens.token(), GMAIL_POLICY)

    async def list_tools(self) -> list[dict[str, Any]]:
        return await self._client().list_tools()

    async def call(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return await self._client().call_read_tool(tool_name, arguments, self._enforce)
