"""Rotas genéricas: funcionam para qualquer canal registrado, sem código novo."""

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Query

from radar.api.deps import RegistryDep
from radar.core.models import Consulta, Origem, Registro

router = APIRouter(prefix="/fontes", tags=["fontes"])


@router.get("")
def list_fontes(registry: RegistryDep) -> list[dict[str, Any]]:
    """Canais implementados e se estão configurados no .env."""
    return registry.available()


@router.get("/{origem}/status")
def fonte_status(origem: Origem, registry: RegistryDep) -> dict[str, Any]:
    """Confere a conexão com o canal (conta, workspace, escopo)."""
    return registry.get(origem).status()


@router.get("/{origem}/registros")
def fonte_registros(
    origem: Origem,
    registry: RegistryDep,
    desde: Annotated[
        datetime | None, Query(description="ISO 8601, ex.: 2026-11-25T09:00:00-03:00")
    ] = None,
    ate: Annotated[datetime | None, Query(description="ISO 8601")] = None,
    limite: Annotated[int, Query(ge=1, le=1000)] = 100,
    escopo: Annotated[
        str | None, Query(description="Slack: ID do canal. Vazio = todo o projeto")
    ] = None,
) -> list[Registro]:
    """Registros do projeto no formato comum, em ordem cronológica."""
    consulta = Consulta(desde=desde, ate=ate, limite=limite, escopo=escopo)
    return registry.get(origem).fetch(consulta)
