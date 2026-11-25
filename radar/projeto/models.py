from datetime import datetime

from pydantic import BaseModel, Field

from radar.achados.models import Papel


class CanalSlack(BaseModel):
    id: str = Field(min_length=1)
    nome: str | None = None


class Pessoa(BaseModel):
    nome: str = Field(min_length=1, max_length=120, description="Nome como aparece no Slack")
    papel: Papel


class ProjetoConfig(BaseModel):
    """O que a tela de Configurações grava."""

    canais_slack: list[CanalSlack] = Field(default_factory=list)
    pessoas: list[Pessoa] = Field(default_factory=list)


class ConfigPedido(BaseModel):
    canais_slack: list[str] = Field(
        default_factory=list, description='Nomes ("#alfa-projeto") ou IDs ("C0123...")'
    )
    pessoas: list[Pessoa] = Field(default_factory=list)


class Projeto(BaseModel):
    """Dados do projeto que as telas mostram."""

    nome: str
    cliente: str | None
    canal_slack: str | None = Field(description="Canal que recebe o relatório aprovado")
    valor_hora: float
    canais_slack: list[CanalSlack]
    envolvidos: list[Pessoa]
    pessoas: dict[Papel, str | None] = Field(description="Primeira pessoa de cada papel")


class Arquivo(BaseModel):
    id: str
    nome: str
    tipo: str = Field(description="Contrato, Terceiro, Reunião, E-mail ou Documento")
    origem: str = "PDF"
    tamanho: int
    enviado_em: datetime


class SlackConexao(BaseModel):
    conectado: bool
    workspace: str | None = None
    motivo: str | None = None
