"""Dependências da API (injeção via FastAPI `Depends`)."""

import os
from functools import lru_cache
from typing import Annotated, cast

from fastapi import Depends

from radar import config
from radar.core.errors import FonteNaoConfigurada
from radar.core.models import Origem
from radar.fontes.gmail import GmailFonte, GmailMcp
from radar.fontes.registry import FonteRegistry
from radar.fontes.slack import SlackFonte, SlackMcp
from radar.projeto.models import ProjetoConfig
from radar.projeto.service import config_inicial, ler_projeto_json
from radar.projeto.store import ProjetoStore


def get_projeto_json() -> dict:
    """`data/projeto_alfa.json` (ou PROJETO_PATH): nome, cliente, canais e pessoas.

    PROJETO_NOME e PROJETO_CLIENTE no .env trocam o nome e o cliente (ex.: SmartFit).
    """
    dados = ler_projeto_json(config.PROJETO_PATH)
    nome = os.environ.get("PROJETO_NOME")
    if nome and nome != (dados.get("projeto") or {}).get("nome"):
        # Outro projeto: pessoas e canais do JSON de exemplo não valem; o setup começa limpo.
        return {"projeto": {"nome": nome, "cliente": os.environ.get("PROJETO_CLIENTE")}}
    return dados


@lru_cache
def get_projeto_store() -> ProjetoStore:
    return ProjetoStore(config.DATABASE_PATH, config.UPLOADS_DIR)


def nome_do_projeto(projeto_json: dict) -> str:
    return (projeto_json.get("projeto") or {}).get("nome") or "Projeto"


def aplicar_canais(registry: FonteRegistry, cfg: ProjetoConfig | None) -> None:
    """Os canais salvos na tela de Configurações passam a ser os únicos lidos."""
    if not cfg or not cfg.canais_slack:
        return
    try:
        slack = cast(SlackFonte, registry.get(Origem.slack))
    except FonteNaoConfigurada:
        return
    ids = [c.id for c in cfg.canais_slack if c.id]
    if ids:
        slack.set_allowed(ids)


@lru_cache
def get_registry() -> FonteRegistry:
    registry = FonteRegistry()
    aplicar_canais(registry, get_projeto_store().config(nome_do_projeto(get_projeto_json())))
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


ProjetoJsonDep = Annotated[dict, Depends(get_projeto_json)]


ProjetoStoreDep = Annotated[ProjetoStore, Depends(get_projeto_store)]


def config_atual(projeto_json: dict, store: ProjetoStore, registry: FonteRegistry) -> ProjetoConfig:
    """Configuração salva; antes da primeira gravação, a do JSON do projeto."""
    salva = store.config(nome_do_projeto(projeto_json))
    if salva is not None:
        return salva
    try:
        canais_env = cast(SlackFonte, registry.get(Origem.slack)).settings.channel_ids
    except FonteNaoConfigurada:
        canais_env = []
    return config_inicial(projeto_json, canais_env)
