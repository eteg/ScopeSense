"""Achados do Radar e a decisão humana sobre cada um (human-in-the-loop).

Decidir aqui só grava no banco do próprio Radar. Nada é enviado ao Slack:
publicar o achado aprovado será um passo separado, com token de bot próprio.
"""

from typing import Annotated

from fastapi import APIRouter, Query

from radar.achados.models import Achado, Analise, Categoria, DecisaoPedido, Status
from radar.api.deps import SettingsDep, StoreDep

router = APIRouter(prefix="/achados", tags=["achados"])
analises_router = APIRouter(tags=["achados"])


@analises_router.get("/analises/ultima")
def ultima_analise(store: StoreDep, settings: SettingsDep) -> Analise:
    """Última execução do Radar (resumo do dia e o que foi lido). 404 se nunca rodou."""
    return store.ultima_analise(settings.projeto)


@router.get("")
def listar_achados(
    store: StoreDep,
    status: Annotated[Status | None, Query()] = None,
    categoria: Annotated[Categoria | None, Query()] = None,
    projeto: Annotated[str | None, Query()] = None,
) -> list[Achado]:
    """Achados ordenados como no relatório: crítico primeiro; no empate, o mais antigo."""
    return store.listar(projeto=projeto, status=status, categoria=categoria)


@router.get("/{achado_id}")
def obter_achado(achado_id: int, store: StoreDep) -> Achado:
    return store.obter(achado_id)


@router.post("/{achado_id}/decisao")
def decidir_achado(achado_id: int, pedido: DecisaoPedido, store: StoreDep) -> Achado:
    """Aprovar, descartar ou marcar como "não é desvio". 409 se já foi decidido."""
    return store.decidir(achado_id, pedido)


@router.delete("/{achado_id}/decisao")
def desfazer_decisao(
    achado_id: int,
    store: StoreDep,
    por: Annotated[str, Query(min_length=1, max_length=120)],
) -> Achado:
    """Desfaz a decisão (botão "Desfazer"): o achado volta para pendente."""
    return store.desfazer(achado_id, por)
