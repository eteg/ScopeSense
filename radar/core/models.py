from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class Origem(StrEnum):
    slack = "slack"
    email = "email"
    agenda = "agenda"
    reuniao = "reuniao"
    documento = "documento"


class Registro(BaseModel):
    """Evidência normalizada, igual para todas as fontes (schema S-03 do plano)."""

    id: str
    origem: Origem
    data: datetime
    autor: str
    texto: str
    link: str | None = None
    metadados: dict[str, Any] = Field(default_factory=dict)


class Consulta(BaseModel):
    """O que pedir a uma fonte. Cada fonte interpreta `escopo` do seu jeito
    (Slack: um canal do projeto; Gmail: um marcador; etc.)."""

    desde: datetime | None = None
    ate: datetime | None = None
    limite: int = Field(default=100, ge=1, le=1000)
    escopo: str | None = None
