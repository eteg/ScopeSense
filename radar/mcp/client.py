"""Cliente genérico para servidores MCP remotos (Streamable HTTP + Bearer token)."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import create_mcp_http_client, streamable_http_client
from mcp.types import PaginatedRequestParams, Tool

from radar.core.errors import EscritaBloqueada, FalhaNaFonte, RadarError
from radar.mcp.policy import ReadOnlyPolicy

# Recebe (nome da ferramenta, argumentos) e levanta ForaDoEscopo se sair do projeto.
# Pode devolver os argumentos ajustados (ex.: busca com o filtro do projeto imposto);
# se devolver None, os argumentos seguem como vieram.
ArgumentValidator = Callable[[str, dict[str, Any]], dict[str, Any] | None]


def _leaf(exc: BaseException) -> BaseException:
    """Abre ExceptionGroup (anyio/TaskGroup) até o erro original."""
    while isinstance(exc, BaseExceptionGroup) and exc.exceptions:
        exc = exc.exceptions[0]
    return exc


def _translate(exc: Exception, url: str) -> RadarError:
    """Erros do próprio Radar (ex.: EscritaBloqueada) saem como estão; o resto vira FalhaNaFonte."""
    leaf = _leaf(exc)
    if isinstance(leaf, RadarError):
        return leaf
    return FalhaNaFonte(f"Servidor MCP {url}: {_root_cause(leaf)}")


def _root_cause(exc: BaseException) -> str:
    """Descrição do erro original, com status HTTP se houver."""
    exc = _leaf(exc)
    response = getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status is not None:
        body = ""
        try:
            body = response.text[:300]  # type: ignore[union-attr]
        except Exception:
            pass
        return f"HTTP {status} {body}".strip()
    return f"{type(exc).__name__}: {exc}"


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
            raise _translate(exc, self._url) from exc
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
        checked = validate(name, arguments)  # escopo do projeto, antes de abrir conexão
        if checked is not None:
            arguments = checked
        try:
            async with self._session() as session:
                tool = next((t for t in await self._all_tools(session) if t.name == name), None)
                if tool is None:
                    raise EscritaBloqueada(f"Ferramenta '{name}' não existe no servidor MCP.")
                allowed, reason = self._policy.evaluate(tool)
                if not allowed:
                    raise EscritaBloqueada(f"Ferramenta '{name}' bloqueada: {reason}.")
                result = await session.call_tool(name, arguments)
        except Exception as exc:
            raise _translate(exc, self._url) from exc
        return result.model_dump(mode="json", exclude_none=True)
