from datetime import date, datetime
from enum import StrEnum
from typing import Any, Literal

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

    @property
    def canal(self) -> str | None:
        """Canal (Slack) ou arquivo de origem, guardado em `metadados["canal"]`."""
        return self.metadados.get("canal")

    @property
    def thread_id(self) -> str | None:
        """`thread_ts` do Slack, para contexto, guardado em `metadados["thread_id"]`."""
        return self.metadados.get("thread_id")


class Consulta(BaseModel):
    """O que pedir a uma fonte. Cada fonte interpreta `escopo` do seu jeito
    (Slack: um canal do projeto; Gmail: um marcador; etc.)."""

    desde: datetime | None = None
    ate: datetime | None = None
    limite: int = Field(default=100, ge=1, le=1000)
    escopo: str | None = None

# --- Alerta, decisão e extração (R-01) -------------------------------------------------


class TipoDesvio(StrEnum):
    escopo_extra = "escopo_extra"
    prazo_sla = "prazo_sla"
    terceiro_sem_documento = "terceiro_sem_documento"
    promessa_fora_do_contrato = "promessa_fora_do_contrato"
    nenhum = "nenhum"


class Papel(StrEnum):
    gestor = "gestor"
    comercial = "comercial"
    administrativo_contratos = "administrativo_contratos"


class Acao(StrEnum):
    """O que fazer com a classificação. O alerta é postado no grupo do projeto (não há DM)."""

    postar = "postar"
    resumo = "resumo"
    descartar = "descartar"


class SaidaClassificacao(BaseModel):
    """O que o MODELO devolve. Não tem `responsavel`: quem roteia é o código."""

    tipo: TipoDesvio
    confianca: float = Field(ge=0, le=1)
    clausula: str  # ex.: "2.2"
    trecho_contrato: str
    trecho_evidencia: str
    justificativa: str = Field(max_length=300)


class Alerta(SaidaClassificacao):
    """O que o sistema usa."""

    registro_id: str
    # SÓ as regras em código preenchem; o modelo nunca.
    responsavel: Papel | None = None


class Obrigacao(BaseModel):
    clausula: str
    texto: str
    tipo: str  # escopo | prazo | terceiro | outro
    prazo: date | None = None
    documento_exigido: str | None = None


class ListaObrigacoes(BaseModel):
    """Formato de saída da extração de obrigações do contrato."""

    obrigacoes: list[Obrigacao]


class Decisao(BaseModel):
    alerta_id: str  # = registro_id
    acao: Literal["aprovar", "descartar", "nao_e_desvio"]
    quem: str
    quando: datetime


class DocumentoExtraido(BaseModel):
    """Saída da leitura de PDFs do terceiro."""

    tipo: str  # aso | fgts | certidao_negativa | nda | treinamento
    pessoa: str | None = None
    empresa: str | None = None
    validade: date | None = None  # sempre ISO (AAAA-MM-DD), evita trocar mês e dia
    arquivo: str
