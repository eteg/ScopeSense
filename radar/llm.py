"""Chamada estruturada ao modelo: o modelo só devolve JSON validado por Pydantic."""

import hashlib
import os
import time
from collections.abc import Callable
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from radar import config
from radar.core.errors import SaidaInvalida

T = TypeVar("T", bound=BaseModel)

MAX_TOKENS = 4096

# Vira a métrica "100% das saídas válidas; N precisaram de nova tentativa" do eval.
CONTADORES = {"chamadas": 0, "invalidas": 0, "retentativas": 0}

_client: Any = None
_cache_get: Callable[[str], str | None] | None = None
_cache_set: Callable[[str, str], None] | None = None
_observador: Callable[[dict[str, Any]], None] | None = None


def registrar_cache(get: Callable[[str], str | None], set: Callable[[str, str], None]) -> None:  # noqa: A002
    """Liga o cache (G-12 pluga o SQLite). Guarda o JSON da saída, por chave `chave_cache`."""
    global _cache_get, _cache_set
    _cache_get, _cache_set = get, set


def registrar_observador(fn: Callable[[dict[str, Any]], None]) -> None:
    """Liga um observador (R-06 pluga o Langfuse). Recebe um dict por chamada ao modelo."""
    global _observador
    _observador = fn


def chave_cache(modelo: str, system: str, user: str, schema: type[BaseModel]) -> str:
    bruto = "\x00".join([modelo, system, user, schema.__name__])
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()


def _get_client() -> Any:
    global _client
    if _client is None:
        import anthropic  # preguiçoso: os testes e o resto do código não exigem o SDK

        # Lê ANTHROPIC_API_KEY do ambiente. Chave de organização (sem workspace) exige o
        # cabeçalho anthropic-workspace-id: vem de ANTHROPIC_WORKSPACE_ID, se houver.
        workspace = os.environ.get("ANTHROPIC_WORKSPACE_ID", "").strip()
        cabecalhos = {"anthropic-workspace-id": workspace} if workspace else None
        _client = anthropic.Anthropic(default_headers=cabecalhos)
    return _client


def _notificar(info: dict[str, Any]) -> None:
    if _observador is None:
        return
    try:
        _observador(info)
    except Exception:  # noqa: BLE001 - observabilidade nunca derruba o fluxo
        pass


def chamar_estruturado(
    modelo: str, system: str, user: str, schema: type[T], temperatura: float = 0.0
) -> T:
    """Chama o modelo e devolve uma instância de `schema`.

    Saída inválida: tenta de novo até `config.TENTATIVAS_SCHEMA` vezes (além da primeira) e só
    então levanta `SaidaInvalida`. Erros da API (rede, chave, limite) não são tratados aqui.
    """
    chave = chave_cache(modelo, system, user, schema)

    if config.MODO_DEMO and _cache_get is not None:
        guardado = _cache_get(chave)
        if guardado is not None:
            try:
                resultado = schema.model_validate_json(guardado)
            except ValidationError:
                pass  # cache corrompido: segue para o modelo
            else:
                _notificar({"modelo": modelo, "schema": schema.__name__, "cache": True,
                            "system": system, "user": user, "saida": resultado})  # fmt: skip
                return resultado

    ultimo_erro: Exception | None = None
    for tentativa in range(config.TENTATIVAS_SCHEMA + 1):
        if tentativa:
            CONTADORES["retentativas"] += 1
        CONTADORES["chamadas"] += 1
        inicio = time.perf_counter()
        try:
            # Verificado contra o SDK instalado (anthropic 2.14): `messages.parse` aceita
            # model, max_tokens, system, messages e output_format, e devolve `parsed_output`.
            # Ele NÃO aceita `temperature`, por isso o argumento `temperatura` desta função é
            # mantido só por compatibilidade com quem já chama e não é enviado.
            resposta = _get_client().messages.parse(
                model=modelo,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
            )
            resultado = resposta.parsed_output
            if resultado is None:
                raise ValueError("o modelo não devolveu saída estruturada")
        except (ValidationError, ValueError) as erro:  # ValidationError também é ValueError
            CONTADORES["invalidas"] += 1
            ultimo_erro = erro
            continue
        _notificar({
            "modelo": modelo, "schema": schema.__name__, "cache": False,
            "system": system, "user": user, "saida": resultado,
            "usage": getattr(resposta, "usage", None),
            "segundos": time.perf_counter() - inicio,
            "tentativa": tentativa + 1,
        })  # fmt: skip
        if _cache_set is not None:
            _cache_set(chave, resultado.model_dump_json())
        return resultado

    raise SaidaInvalida(
        f"{schema.__name__}: saída inválida após {config.TENTATIVAS_SCHEMA + 1} tentativas"
    ) from ultimo_erro
