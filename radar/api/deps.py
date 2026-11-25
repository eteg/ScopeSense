"""Dependências da API (injeção via FastAPI `Depends`)."""

from functools import lru_cache
from typing import Annotated, cast

from fastapi import Depends

from radar.achados.config import AchadosSettings
from radar.achados.store import AchadoStore
from radar.core.errors import FonteNaoConfigurada
from radar.core.models import Origem
from radar.fontes.gmail import GmailFonte, GmailMcp
from radar.fontes.registry import FonteRegistry
from radar.fontes.slack import SlackFonte, SlackMcp
from radar.projeto.models import ProjetoConfig
from radar.projeto.service import config_inicial
from radar.projeto.store import ProjetoStore


@lru_cache
def get_settings() -> AchadosSettings:
    return AchadosSettings()


@lru_cache
def get_projeto_store() -> ProjetoStore:
    s = get_settings()
    return ProjetoStore(s.db_path, s.arquivos_dir)


def aplicar_canais(registry: FonteRegistry, config: ProjetoConfig | None) -> None:
    """Os canais salvos na tela de Configurações passam a ser os únicos lidos."""
    if not config or not config.canais_slack:
        return
    try:
        slack = cast(SlackFonte, registry.get(Origem.slack))
    except FonteNaoConfigurada:
        return
    slack.set_allowed([c.id for c in config.canais_slack])


@lru_cache
def get_registry() -> FonteRegistry:
    registry = FonteRegistry()
    aplicar_canais(registry, get_projeto_store().config(get_settings().projeto))
    return registry


RegistryDep = Annotated[FonteRegistry, Depends(get_registry)]


def get_slack(registry: RegistryDep) -> SlackFonte:
    return cast(SlackFonte, registry.get(Origem.slack))


SlackDep = Annotated[SlackFonte, Depends(get_slack)]


def get_slack_mcp(slack: SlackDep) -> SlackMcp:
    return SlackMcp(slack.settings)


SlackMcpDep = Annotated[SlackMcp, Depends(get_slack_mcp)]


def get_gmail(registry: RegistryDep) -> GmailFonte:
    return cast(GmailFonte, registry.get(Origem.email))


GmailDep = Annotated[GmailFonte, Depends(get_gmail)]


def get_gmail_mcp(gmail: GmailDep) -> GmailMcp:
    return GmailMcp(gmail.settings, fonte=gmail)


GmailMcpDep = Annotated[GmailMcp, Depends(get_gmail_mcp)]


SettingsDep = Annotated[AchadosSettings, Depends(get_settings)]


@lru_cache
def get_store() -> AchadoStore:
    return AchadoStore(get_settings().db_path)


StoreDep = Annotated[AchadoStore, Depends(get_store)]


ProjetoStoreDep = Annotated[ProjetoStore, Depends(get_projeto_store)]


def config_atual(
    settings: AchadosSettings, store: ProjetoStore, registry: FonteRegistry
) -> ProjetoConfig:
    """Configuração salva; antes da primeira gravação, a do .env."""
    salva = store.config(settings.projeto)
    if salva is not None:
        return salva
    try:
        canais_env = cast(SlackFonte, registry.get(Origem.slack)).settings.channel_ids
    except FonteNaoConfigurada:
        canais_env = []
    return config_inicial(settings, canais_env)
