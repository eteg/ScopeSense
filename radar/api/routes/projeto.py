"""Tela de Configurações: canais do Slack, pessoas por papel e arquivos do projeto."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from radar.api.deps import (
    ProjetoJsonDep,
    ProjetoStoreDep,
    RegistryDep,
    aplicar_canais,
    config_atual,
    nome_do_projeto,
)
from radar.core.errors import EntradaInvalida, RadarError
from radar.core.models import Origem
from radar.projeto.models import Arquivo, ConfigPedido, Projeto, SlackConexao
from radar.projeto.service import aplicar_pedido, montar_projeto
from radar.projeto.store import MAX_BYTES

router = APIRouter(prefix="/projeto", tags=["projeto"])


@router.get("")
def projeto(projeto_json: ProjetoJsonDep, store: ProjetoStoreDep, registry: RegistryDep) -> Projeto:
    """Nome, cliente, canais e pessoas por papel."""
    return montar_projeto(projeto_json, config_atual(projeto_json, store, registry))


@router.put("/config")
def salvar_config(
    pedido: ConfigPedido,
    projeto_json: ProjetoJsonDep,
    store: ProjetoStoreDep,
    registry: RegistryDep,
) -> Projeto:
    """Salva canais e pessoas. Canal novo é conferido no Slack (422 se não existir)."""
    atual = config_atual(projeto_json, store, registry)

    def resolver():
        return registry.get(Origem.slack).resolver_canais  # type: ignore[attr-defined]

    nova = aplicar_pedido(atual, pedido, resolver)
    store.salvar_config(nome_do_projeto(projeto_json), nova)
    aplicar_canais(registry, nova)
    return montar_projeto(projeto_json, nova)


@router.get("/slack")
def slack_conexao(registry: RegistryDep) -> SlackConexao:
    """O token do Slack funciona? (selo "Slack conectado")."""
    try:
        status = registry.get(Origem.slack).status()
    except RadarError as exc:
        return SlackConexao(conectado=False, motivo=str(exc))
    return SlackConexao(conectado=True, workspace=status.get("team"))


@router.get("/arquivos")
def listar_arquivos(projeto_json: ProjetoJsonDep, store: ProjetoStoreDep) -> list[Arquivo]:
    return store.arquivos(nome_do_projeto(projeto_json))


@router.post("/arquivos", status_code=201)
async def enviar_arquivo(
    request: Request,
    projeto_json: ProjetoJsonDep,
    store: ProjetoStoreDep,
    nome: Annotated[str, Query(min_length=1, max_length=255)],
) -> Arquivo:
    """Envia um PDF (corpo da requisição = bytes do arquivo). Até 20 MB."""
    if int(request.headers.get("content-length") or 0) > MAX_BYTES:
        raise EntradaInvalida("Arquivo maior que 20 MB.")
    return store.adicionar_arquivo(nome_do_projeto(projeto_json), nome, await request.body())


@router.delete("/arquivos/{arquivo_id}", status_code=204)
def remover_arquivo(arquivo_id: str, projeto_json: ProjetoJsonDep, store: ProjetoStoreDep) -> None:
    store.remover_arquivo(nome_do_projeto(projeto_json), arquivo_id)
