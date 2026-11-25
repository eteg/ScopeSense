"""Nó `rotear`: define o responsável (regra em código) e avisa o notificador injetado."""

from collections.abc import Callable

from radar import config
from radar.core.models import Acao, Alerta, Papel, Registro, TipoDesvio

Notificador = Callable[[Alerta, Registro], None]

# TODO(R-05): trocar por `radar.roteamento.PAPEL_POR_TIPO` e `decidir_acao(alerta)`.
_PAPEL_POR_TIPO: dict[TipoDesvio, Papel] = {
    TipoDesvio.escopo_extra: Papel.gestor,
    TipoDesvio.prazo_sla: Papel.comercial,
    TipoDesvio.terceiro_sem_documento: Papel.administrativo_contratos,
    TipoDesvio.promessa_fora_do_contrato: Papel.administrativo_contratos,
}


def notificador_padrao(alerta: Alerta, registro: Registro) -> None:
    """Padrão até o Slack (G-07) injetar o dele: só imprime uma linha."""
    print(f"[alerta simulado] {alerta.tipo} -> {alerta.responsavel} ({registro.id})")


_notificador: Notificador = notificador_padrao


def definir_notificador(notificador: Notificador) -> None:
    """Guarda o notificador usado pelo nó. Quem expõe isso ao time é `grafo.configurar`."""
    global _notificador
    _notificador = notificador


def rotear_alerta(alerta: Alerta) -> tuple[Alerta, Acao]:
    """Função pura: preenche `responsavel` e decide a ação. Sem efeito colateral."""
    # TODO(R-05): `decidir_acao` oficial. Aqui: >= LIMIAR_POSTAR posta, abaixo vira resumo.
    responsavel = _PAPEL_POR_TIPO.get(alerta.tipo)
    alerta = alerta.model_copy(update={"responsavel": responsavel})
    acao = Acao.postar if alerta.confianca >= config.LIMIAR_POSTAR else Acao.resumo
    return alerta, acao


def rotear(estado: dict) -> dict:
    """Wrapper fino do nó. O efeito colateral (aviso) fica aqui, nunca antes do `interrupt`."""
    alerta, acao = rotear_alerta(estado["alerta"])
    if acao == Acao.postar:
        _notificador(alerta, estado["registro"])
    return {"alerta": alerta, "acao": acao.value}
