"""Grafo LangGraph do Radar: buscar, classificar, conferir documentos, rotear, aprovar, registrar.

Interface para o resto do time: `configurar(notificador)` e `processar(registro, contexto)`.
`retomar` fica para o R-04. O checkpointer é em memória: `processar` e `retomar` precisam rodar
no MESMO processo (TODO(R-04): avaliar o checkpointer SQLite do LangGraph).
"""

from collections.abc import Sequence
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from radar.core.models import Acao, Alerta, Decisao, Registro
from radar.nos.aprovar import aprovar
from radar.nos.buscar import buscar
from radar.nos.classificar import classificar, deve_seguir
from radar.nos.conferir_documentos import conferir_documentos
from radar.nos.registrar import registrar
from radar.nos.rotear import Notificador, definir_notificador, rotear


class Estado(TypedDict, total=False):
    registro: Registro
    contexto: list[Registro]  # mensagens anteriores (thread/canal)
    clausulas: list[dict]  # resultado do RAG
    alerta: Alerta | None
    acao: str  # postar | resumo | descartar
    decisao: Decisao | None


def seguir_ou_fim(estado: Estado) -> str:
    return "seguir" if deve_seguir(estado.get("alerta")) else "fim"


def depois_de_rotear(estado: Estado) -> str:
    return "aprovar" if estado.get("acao") == Acao.postar else "fim"


def montar_grafo() -> StateGraph:
    g = StateGraph(Estado)
    g.add_node("buscar", buscar)
    g.add_node("classificar", classificar)
    g.add_node("conferir_documentos", conferir_documentos)
    g.add_node("rotear", rotear)
    g.add_node("aprovar", aprovar)
    g.add_node("registrar", registrar)
    g.add_edge(START, "buscar")
    g.add_edge("buscar", "classificar")
    g.add_conditional_edges(
        "classificar", seguir_ou_fim, {"seguir": "conferir_documentos", "fim": END}
    )
    g.add_edge("conferir_documentos", "rotear")
    g.add_conditional_edges("rotear", depois_de_rotear, {"aprovar": "aprovar", "fim": END})
    g.add_edge("aprovar", "registrar")
    g.add_edge("registrar", END)
    return g


# A pausa de aprovação (R-04) EXIGE checkpointer.
grafo = montar_grafo().compile(checkpointer=InMemorySaver())


def configurar(notificador: Notificador) -> None:
    """Injeta a função que avisa o responsável (o Slack do G-07 chama isto)."""
    definir_notificador(notificador)


def processar(registro: Registro, contexto: Sequence[Registro] = ()) -> dict:
    """Roda o grafo para um registro. Um `thread_id` por registro evita misturar estados.

    Se parar numa pausa de aprovação, o resultado traz a chave `"__interrupt__"`.
    """
    config = {"configurable": {"thread_id": registro.id}}
    return grafo.invoke({"registro": registro, "contexto": list(contexto)}, config=config)
