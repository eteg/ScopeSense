"""Cliente genérico para servidores MCP remotos (Streamable HTTP + Bearer token)."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.types import PaginatedRequestParams, Tool

from radar.core.errors import EscritaBloqueada, FalhaNaFonte
from radar.mcp.policy import ReadOnlyPolicy

# Recebe (nome da ferramenta, argumentos) e levanta ForaDoEscopo se sair do projeto.
ArgumentValidator = Callable[[str, dict[str, Any]], None]


class ReadOnlyMcpClient:
    def __init__(self, url: str, token: str, policy: ReadOnlyPolicy) -> None:
        self._url = url
        self._token = token
        self._policy = policy

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        http_client = create_mcp_http_client(headers={"Authorization": f"Bearer {self._token}"})
        async with (
            http_client,
            streamable_http_client(self._url, http_client=http_client) as (read, write),
            ClientSession(read, write) as session,
        ):
            await session.initialize()
            yield session

    @staticmethod
    async def _all_tools(session: ClientSession) -> list[Tool]:
        result = await session.list_tools()
        tools = list(result.tools)
        while result.next_cursor:
            result = await session.list_tools(
                params=PaginatedRequestParams(cursor=result.next_cursor)
            )
            tools.extend(result.tools)
        return tools

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            async with self._session() as session:
                tools = await self._all_tools(session)
        except Exception as exc:
            raise FalhaNaFonte(f"Servidor MCP {self._url}: {exc}") from exc
        described = []
        for tool in tools:
            allowed, reason = self._policy.evaluate(tool)
            described.append(
                {
                    "nome": tool.name,
                    "descricao": tool.description,
                    "liberada": allowed,
                    "motivo": reason,
                    "parametros": tool.input_schema,
                }
            )
        return described

    async def call_read_tool(
        self, name: str, arguments: dict[str, Any], validate: ArgumentValidator
    ) -> dict[str, Any]:
        validate(name, arguments)  # escopo do projeto, antes de abrir conexão
        try:
            async with self._session() as session:
                tool = next((t for t in await self._all_tools(session) if t.name == name), None)
                if tool is None:
                    raise EscritaBloqueada(f"Ferramenta '{name}' não existe no servidor MCP.")
                allowed, reason = self._policy.evaluate(tool)
                if not allowed:
                    raise EscritaBloqueada(f"Ferramenta '{name}' bloqueada: {reason}.")
                result = await session.call_tool(name, arguments)
        except EscritaBloqueada:
            raise
        except Exception as exc:
            raise FalhaNaFonte(f"Servidor MCP {self._url}: {exc}") from exc
        return result.model_dump(mode="json", exclude_none=True)
