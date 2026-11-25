"""Tela de Configurações: canais do Slack, pessoas por papel e arquivos do projeto."""

from typing import Annotated

from fastapi import APIRouter, Query, Request

from radar.api.deps import (
    ProjetoStoreDep,
    RegistryDep,
    SettingsDep,
    aplicar_canais,
    config_atual,
)
from radar.core.errors import EntradaInvalida, RadarError
from radar.core.models import Origem
from radar.projeto.models import Arquivo, ConfigPedido, Projeto, SlackConexao
from radar.projeto.service import aplicar_pedido, montar_projeto
from radar.projeto.store import MAX_BYTES

router = APIRouter(prefix="/projeto", tags=["projeto"])


@router.get("")
def projeto(settings: SettingsDep, store: ProjetoStoreDep, registry: RegistryDep) -> Projeto:
    """Nome, cliente, canais, pessoas por papel e valor da hora."""
    return montar_projeto(settings, config_atual(settings, store, registry))


@router.put("/config")
def salvar_config(
    pedido: ConfigPedido, settings: SettingsDep, store: ProjetoStoreDep, registry: RegistryDep
) -> Projeto:
    """Salva canais e pessoas. Canal novo é conferido no Slack (422 se não existir)."""
    atual = config_atual(settings, store, registry)

    def resolver():
        return registry.get(Origem.slack).resolver_canais  # type: ignore[attr-defined]

    nova = aplicar_pedido(atual, pedido, resolver)
    store.salvar_config(settings.projeto, nova)
    aplicar_canais(registry, nova)
    return montar_projeto(settings, nova)


@router.get("/slack")
def slack_conexao(registry: RegistryDep) -> SlackConexao:
    """O token do Slack funciona? (selo "Slack conectado")."""
    try:
        status = registry.get(Origem.slack).status()
    except RadarError as exc:
        return SlackConexao(conectado=False, motivo=str(exc))
    return SlackConexao(conectado=True, workspace=status.get("team"))


@router.get("/arquivos")
def listar_arquivos(settings: SettingsDep, store: ProjetoStoreDep) -> list[Arquivo]:
    return store.arquivos(settings.projeto)


@router.post("/arquivos", status_code=201)
async def enviar_arquivo(
    request: Request,
    settings: SettingsDep,
    store: ProjetoStoreDep,
    nome: Annotated[str, Query(min_length=1, max_length=255)],
) -> Arquivo:
    """Envia um PDF (corpo da requisição = bytes do arquivo). Até 20 MB."""
    tamanho = int(request.headers.get("content-length") or 0)
    if tamanho > MAX_BYTES:
        raise EntradaInvalida("Arquivo maior que 20 MB.")
    return store.adicionar_arquivo(settings.projeto, nome, await request.body())


@router.delete("/arquivos/{arquivo_id}", status_code=204)
def remover_arquivo(arquivo_id: str, settings: SettingsDep, store: ProjetoStoreDep) -> None:
    store.remover_arquivo(settings.projeto, arquivo_id)
