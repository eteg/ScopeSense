"""`analisar`: as mesmas funções puras dos nós, sem pausa de aprovação e sem notificar.

É o que o eval chama.
"""

from collections.abc import Sequence

from radar.core.models import Acao, Alerta, Registro
from radar.nos.buscar import buscar_clausulas
from radar.nos.classificar import classificar_registro, deve_seguir
from radar.nos.conferir_documentos import conferir
from radar.nos.rotear import rotear_alerta


def analisar(registro: Registro, contexto: Sequence[Registro] = ()) -> Alerta | None:
    """Devolve o `Alerta` com `responsavel` preenchido, ou `None` (nenhum desvio ou descartado)."""
    clausulas = buscar_clausulas(registro, contexto)
    alerta = classificar_registro(registro, clausulas, contexto)
    if not deve_seguir(alerta):
        return None
    alerta = conferir(alerta, registro)
    if alerta is None:  # documentos em dia: nada a avisar
        return None
    alerta, acao = rotear_alerta(alerta)
    return None if acao == Acao.descartar else alerta
