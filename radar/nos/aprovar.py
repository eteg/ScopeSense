"""Nó `aprovar`: pausa para a decisão humana (aprovar, descartar ou não é desvio)."""

from langgraph.types import interrupt

from radar.core.models import Decisao


def aprovar(estado: dict) -> dict:
    """Pausa o grafo com o alerta e, ao retomar, devolve a `Decisao` recebida.

    Cuidado: na retomada este nó roda de novo desde o começo, então NENHUM efeito colateral
    (gravar, avisar) pode vir antes do `interrupt`. Eles ficam no nó `rotear`.
    """
    recebido = interrupt({"alerta": estado["alerta"].model_dump(mode="json")})
    if isinstance(recebido, Decisao):
        decisao = recebido
    else:
        decisao = Decisao.model_validate(recebido)  # valida `acao` (aprovar|descartar|nao_e_desvio)
    return {"decisao": decisao}
