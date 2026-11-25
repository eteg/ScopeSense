"""O que a tela da Fila (web/) mostra, montado a partir dos alertas do pipeline.

Funções puras sobre `radar.db` (alertas, decisões e registros). A gravidade sai do
tipo do desvio, como na seção "Categorias" do design: crítico quando há risco legal
ou trabalhista ou entrega fora do contrato; médio para prazo e promessa.
"""

from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel

from radar import db
from radar.core.models import Acao, Decisao, Origem, Papel, TipoDesvio
from radar.ui import textos


class Gravidade(StrEnum):
    critico = "critico"
    medio = "medio"
    baixo = "baixo"


GRAVIDADE_POR_TIPO: dict[TipoDesvio, Gravidade] = {
    TipoDesvio.escopo_extra: Gravidade.critico,
    TipoDesvio.terceiro_sem_documento: Gravidade.critico,
    TipoDesvio.prazo_sla: Gravidade.medio,
    TipoDesvio.promessa_fora_do_contrato: Gravidade.medio,
}
_ORDEM = {Gravidade.critico: 0, Gravidade.medio: 1, Gravidade.baixo: 2}

_CHAVE_TITULO = {
    TipoDesvio.escopo_extra: "escopo",
    TipoDesvio.prazo_sla: "prazo",
    TipoDesvio.terceiro_sem_documento: "documento",
    TipoDesvio.promessa_fora_do_contrato: "promessa",
}


class Evidencia(BaseModel):
    origem: Origem
    autor: str
    data: datetime
    link: str | None = None
    canal: str | None = None


class AlertaTela(BaseModel):
    id: str  # = registro_id
    tipo: TipoDesvio
    titulo: str
    gravidade: Gravidade
    confianca: float
    acao: Acao  # postar (>= 0,8) ou resumo (0,5 a 0,8)
    clausula: str
    trecho_contrato: str
    trecho_evidencia: str
    justificativa: str
    responsavel: Papel | None
    evidencia: Evidencia | None  # None se o registro de origem não foi guardado
    status: str  # pendente | em_resumo | aprovado | descartado | nao_e_desvio
    decisao: Decisao | None
    criado_em: str | None
    trace_url: str | None


class Resumo(BaseModel):
    registros_lidos: dict[str, int]
    ultimo_alerta_em: str | None


def titulo(tipo: TipoDesvio) -> str:
    chave = _CHAVE_TITULO.get(tipo)
    return textos.TITULO_DESVIO.get(chave, textos.TITULO_DESVIO_GENERICO) if chave else tipo


def listar(*, caminho: str | Path | None = None) -> list[AlertaTela]:
    """Alertas para a Fila: sem os descartados pelo roteamento, crítico primeiro."""
    saida = []
    for a in db.listar_alertas(caminho=caminho):
        if a.acao == Acao.descartar or a.tipo == TipoDesvio.nenhum:
            continue
        registro = db.obter_registro(a.registro_id, caminho=caminho)
        evidencia = (
            Evidencia(
                origem=registro.origem,
                autor=registro.autor,
                data=registro.data,
                link=registro.link,
                canal=registro.canal,
            )
            if registro
            else None
        )
        saida.append(
            AlertaTela(
                id=a.registro_id,
                tipo=a.tipo,
                titulo=titulo(a.tipo),
                gravidade=GRAVIDADE_POR_TIPO.get(a.tipo, Gravidade.baixo),
                confianca=a.confianca,
                acao=a.acao,
                clausula=a.clausula,
                trecho_contrato=a.trecho_contrato,
                trecho_evidencia=a.trecho_evidencia,
                justificativa=a.justificativa,
                responsavel=a.responsavel,
                evidencia=evidencia,
                status=a.status,
                decisao=a.decisao,
                criado_em=a.criado_em,
                trace_url=a.trace_url,
            )
        )
    saida.sort(key=lambda x: (_ORDEM[x.gravidade], x.criado_em or "", x.id))
    return saida


def resumo(*, caminho: str | Path | None = None) -> Resumo:
    alertas = db.listar_alertas(caminho=caminho)
    ultimo = max((a.criado_em for a in alertas if a.criado_em), default=None)
    return Resumo(registros_lidos=db.contar_registros(caminho=caminho), ultimo_alerta_em=ultimo)
