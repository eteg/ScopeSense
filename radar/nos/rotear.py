"""Nó `rotear`: define o responsável (regra em código) e avisa o notificador injetado."""

from collections.abc import Callable

from radar.core.models import Acao, Alerta, Registro
from radar.roteamento import rotear_alerta  # R-05: regra oficial (papel por tipo, ação por confiança)

__all__ = ["Notificador", "definir_notificador", "notificador_padrao", "rotear", "rotear_alerta"]

Notificador = Callable[[Alerta, Registro], None]


def notificador_padrao(alerta: Alerta, registro: Registro) -> None:
    """Padrão até o Slack (G-07) injetar o dele: só imprime uma linha."""
    print(f"[alerta simulado] {alerta.tipo} -> {alerta.responsavel} ({registro.id})")


_notificador: Notificador = notificador_padrao


def definir_notificador(notificador: Notificador) -> None:
    """Guarda o notificador usado pelo nó. Quem expõe isso ao time é `grafo.configurar`."""
    global _notificador
    _notificador = notificador


def rotear(estado: dict) -> dict:
    """Wrapper fino do nó. O efeito colateral (aviso) fica aqui, nunca antes do `interrupt`."""
    alerta, acao = rotear_alerta(estado["alerta"])
    if acao == Acao.postar:
        _notificador(alerta, estado["registro"])
    return {"alerta": alerta, "acao": acao.value}
