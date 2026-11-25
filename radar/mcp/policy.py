"""Política de só leitura para ferramentas MCP, reutilizada por todos os canais."""

import re
from dataclasses import dataclass

from mcp.types import Tool

WRITE_VERBS = (
    "send", "post", "create", "update", "upload", "add", "schedule", "delete", "remove",
    "write", "edit", "set", "invite", "archive", "complete", "draft", "join", "leave",
    "modify", "trash", "move", "share", "label", "reply", "forward", "accept", "decline",
)  # fmt: skip


@dataclass(frozen=True)
class ReadOnlyPolicy:
    """Uma ferramenta só é liberada se:

    1. o servidor a anota como somente leitura (``read_only_hint``);
    2. o nome tem um verbo de leitura e nenhum verbo de escrita;
    3. o nome não tem nenhum termo bloqueado pelo canal (ex.: busca no Slack).
    """

    read_verbs: tuple[str, ...] = ("read", "list", "get", "search")
    blocked_terms: dict[str, str] | None = None  # termo -> motivo

    def evaluate(self, tool: Tool) -> tuple[bool, str]:
        words = tool_words(tool.name)
        hint = tool.annotations.read_only_hint if tool.annotations else None
        if hint is not True:
            return False, "servidor não marca como somente leitura"
        if words & set(WRITE_VERBS):
            return False, "nome indica escrita"
        for term, reason in (self.blocked_terms or {}).items():
            if term in words:
                return False, reason
        if not words & set(self.read_verbs):
            return False, "nome não indica leitura"
        return True, "leitura"


def tool_words(name: str) -> set[str]:
    """'slack_read_thread' -> {'slack', 'read', 'thread'}; 'getMessage' -> {'get', 'message'}."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return {w for w in re.split(r"[\s_\-.:/]+", spaced.lower()) if w}
