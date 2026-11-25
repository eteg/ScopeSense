"""Roteamento em código: o tipo define o papel, a confiança define a ação.

Funções puras (sem banco, sem Slack). O modelo nunca escolhe o responsável nem a ação.
"""

from radar import config
from radar.core.models import Acao, Alerta, Papel, TipoDesvio

# `TipoDesvio.nenhum` não tem papel: não vira alerta.
PAPEL_POR_TIPO: dict[TipoDesvio, Papel] = {
    TipoDesvio.escopo_extra: Papel.gestor,
    TipoDesvio.prazo_sla: Papel.comercial,
    TipoDesvio.terceiro_sem_documento: Papel.administrativo_contratos,
    TipoDesvio.promessa_fora_do_contrato: Papel.administrativo_contratos,
}


def decidir_acao(alerta: Alerta) -> Acao:
    """`nenhum` ou confiança < LIMIAR_RESUMO descarta; >= LIMIAR_POSTAR posta; senão resumo."""
    if alerta.tipo == TipoDesvio.nenhum or alerta.confianca < config.LIMIAR_RESUMO:
        return Acao.descartar  # fica só no traço do Langfuse
    if alerta.confianca >= config.LIMIAR_POSTAR:
        return Acao.postar
    return Acao.resumo


def rotear_alerta(alerta: Alerta) -> tuple[Alerta, Acao]:
    """Devolve uma cópia do alerta com `responsavel` preenchido pelo tipo, e a ação.

    O original não é alterado. É o único lugar que preenche `responsavel`.
    """
    papel = PAPEL_POR_TIPO.get(alerta.tipo)  # None para `nenhum`
    roteado = alerta.model_copy(update={"responsavel": papel})
    return roteado, decidir_acao(alerta)
