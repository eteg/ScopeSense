"""Nó `classificar`: decide se a evidência contradiz alguma cláusula."""

from collections.abc import Sequence

from radar import config
from radar.core.models import Alerta, Registro, TipoDesvio


def classificar_registro(
    registro: Registro, clausulas: Sequence[dict], contexto: Sequence[Registro] = ()
) -> Alerta:
    """Função pura. Devolve sempre um `Alerta` (tipo `nenhum` quando não há desvio)."""
    # TODO(R-03): trocar por `radar.llm.chamar_estruturado(...)` com SaidaClassificacao e
    # conferência das citações em código. O modelo NUNCA preenche `responsavel`.
    if "relatórios" in registro.texto.lower():
        return Alerta(
            tipo=TipoDesvio.escopo_extra,
            confianca=0.9,
            clausula="2.2",
            trecho_contrato="módulo de relatórios",
            trecho_evidencia="relatórios",
            justificativa="Valor de teste: a conversa trata de um módulo que a cláusula exclui.",
            registro_id=registro.id,
        )
    return Alerta(
        tipo=TipoDesvio.nenhum,
        confianca=0.9,
        clausula="",
        trecho_contrato="",
        trecho_evidencia="",
        justificativa="Valor de teste: nada contradiz o contrato.",
        registro_id=registro.id,
    )


def deve_seguir(alerta: Alerta | None) -> bool:
    """Aresta condicional: só segue quando há desvio com confiança de pelo menos o limiar."""
    return (
        alerta is not None
        and alerta.tipo != TipoDesvio.nenhum
        and alerta.confianca >= config.LIMIAR_RESUMO
    )


def classificar(estado: dict) -> dict:
    """Wrapper fino do nó."""
    alerta = classificar_registro(
        estado["registro"], estado.get("clausulas", ()), estado.get("contexto", ())
    )
    return {"alerta": alerta}
