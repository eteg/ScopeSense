"""Nó `aprovar`: pausa para a decisão humana (aprovar, descartar ou não é desvio)."""


def aprovar(estado: dict) -> dict:
    """Passagem direta por enquanto: não pausa e não altera o estado.

    TODO(R-04): chamar `interrupt(...)` aqui e deixar a decisão chegar por `grafo.retomar`.
    Cuidado: na retomada este nó roda de novo, então nenhum efeito colateral antes do interrupt.
    """
    return {}
