"""Nó `conferir_documentos`: confere em código os documentos exigidos do terceiro."""

from radar.core.models import Alerta, Registro


def conferir(alerta: Alerta, registro: Registro) -> Alerta:
    """Função pura. Por enquanto devolve o alerta como veio."""
    # TODO(R-05): para `terceiro_sem_documento`, cruzar com `radar.documentos` (ASO vencido,
    # guia de FGTS ausente) e ajustar a confiança/justificativa em código.
    return alerta


def conferir_documentos(estado: dict) -> dict:
    """Wrapper fino do nó."""
    return {"alerta": conferir(estado["alerta"], estado["registro"])}
