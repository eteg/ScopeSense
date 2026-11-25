"""Achados do Radar: desvios do contrato e problemas do projeto.

É a saída validada por schema que o detector (LLM) vai produzir e que a
pessoa responsável aprova, descarta ou marca como "não é desvio" no frontend.
Os campos seguem o system prompt (system-prompt-radar-de-desvios.md).
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field, model_validator

from radar.core.models import Origem


class Categoria(StrEnum):
    desvio = "desvio"  # contraria o combinado em contrato
    problema = "problema"  # atrapalha a execução, sem cláusula envolvida


class Gravidade(StrEnum):
    critico = "critico"
    atencao = "atencao"
    observacao = "observacao"


class Papel(StrEnum):
    """Quem avisar. O papel vem de regra em código, nunca do modelo."""

    gestor = "gestor"
    comercial = "comercial"
    adm_contratos = "adm_contratos"


class Status(StrEnum):
    pendente = "pendente"
    aprovado = "aprovado"
    descartado = "descartado"
    nao_e_desvio = "nao_e_desvio"


class Decisao(StrEnum):
    aprovado = "aprovado"
    descartado = "descartado"
    nao_e_desvio = "nao_e_desvio"


class Citacao(BaseModel):
    """Trecho literal de uma fonte, com o suficiente para conferir."""

    origem: Origem
    trecho: str = Field(min_length=1)
    referencia: str | None = Field(
        default=None, description="Documento e cláusula, canal, assunto do e-mail..."
    )
    autor: str | None = None
    data: datetime | None = None
    link: str | None = None


class AchadoNovo(BaseModel):
    """O que o detector entrega. Sem id, status ou decisão."""

    categoria: Categoria
    tipo: str = Field(min_length=1, description="Ex.: Escopo, Prazo, Bloqueio")
    gravidade: Gravidade
    titulo: str = Field(min_length=1)
    combinado: Citacao | None = Field(
        default=None, description="Obrigatório para desvio: o trecho do contrato"
    )
    execucao: list[Citacao] = Field(min_length=1)
    por_que_importa: str
    o_que_fazer: str
    papeis: list[Papel] = Field(min_length=1)
    recorrente_desde: datetime | None = None
    horas_estimadas: float | None = Field(
        default=None, ge=0, description="Horas de trabalho fora do contrato que o achado evita"
    )

    @model_validator(mode="after")
    def _desvio_cita_o_combinado(self) -> "AchadoNovo":
        # Regra do prompt: se só existe um dos lados, não é desvio.
        if self.categoria is Categoria.desvio and self.combinado is None:
            raise ValueError("desvio precisa citar o combinado (trecho do contrato)")
        return self


class Achado(AchadoNovo):
    id: int
    projeto: str
    criado_em: datetime
    status: Status = Status.pendente
    decidido_por: str | None = None
    decidido_em: datetime | None = None
    comentario: str | None = None


class Analise(BaseModel):
    """Uma execução do Radar: o que foi lido e o resumo do dia."""

    projeto: str
    executada_em: datetime
    duracao_s: float = Field(ge=0)
    resumo: str
    registros_lidos: dict[str, int] = Field(
        default_factory=dict, description='Ex.: {"mensagens": 23, "e-mails": 4, "PDFs": 1}'
    )


class DecisaoPedido(BaseModel):
    decisao: Decisao
    decidido_por: str = Field(min_length=1, max_length=120)
    comentario: str | None = Field(default=None, max_length=2000)
