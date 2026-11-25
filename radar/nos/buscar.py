"""Nó `buscar`: devolve as cláusulas do contrato mais próximas do registro (RAG)."""

from collections.abc import Sequence

from radar.core.models import Registro


def buscar_clausulas(registro: Registro, contexto: Sequence[Registro] = ()) -> list[dict]:
    """Função pura. Formato igual ao de `contrato.buscar`: numero, texto, tipo, distancia."""
    # TODO(G-05/R-03): trocar por `radar.contrato.buscar(texto, k=config.K_CLAUSULAS)` (ChromaDB).
    return [
        {
            "numero": "2.2",
            "texto": "Fora do escopo: módulo de relatórios e treinamento presencial.",
            "tipo": "escopo",
            "distancia": 0.1,
        }
    ]


def buscar(estado: dict) -> dict:
    """Wrapper fino do nó."""
    clausulas = buscar_clausulas(estado["registro"], estado.get("contexto", ()))
    return {"clausulas": clausulas}
