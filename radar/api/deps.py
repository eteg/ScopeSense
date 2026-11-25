"""Dependências da API (injeção via FastAPI `Depends`)."""

from functools import lru_cache
from typing import Annotated, cast

from fastapi import Depends

from radar.core.models import Origem
from radar.fontes.registry import FonteRegistry
from radar.fontes.slack import SlackFonte, SlackMcp


@lru_cache
def get_registry() -> FonteRegistry:
    return FonteRegistry()


RegistryDep = Annotated[FonteRegistry, Depends(get_registry)]


def get_slack(registry: RegistryDep) -> SlackFonte:
    return cast(SlackFonte, registry.get(Origem.slack))


SlackDep = Annotated[SlackFonte, Depends(get_slack)]


def get_slack_mcp(slack: SlackDep) -> SlackMcp:
    return SlackMcp(slack.settings)


SlackMcpDep = Annotated[SlackMcp, Depends(get_slack_mcp)]
