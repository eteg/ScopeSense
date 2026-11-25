"""Observabilidade com Langfuse (R-06): traço por alerta, custo, tokens e latência por chamada.

Sem as chaves no ambiente tudo aqui vira *no-op*: nada quebra e o fluxo roda igual.

API verificada contra o SDK instalado, **langfuse 5.2.0** (o plano foi escrito para o v3):
- `from langfuse import observe, get_client, propagate_attributes` existe; `observe` aceita
  `name=`, `as_type=`, `capture_input=` e `capture_output=`.
- Não existe `start_as_current_generation` nem `update_current_trace` no cliente. Uma generation
  nasce de `cliente.start_observation(as_type="generation", name=, model=, input=, output=,
  usage_details={"input": n, "output": n}, cost_details=, metadata=)` e termina com
  `generation.end(end_time=<ns>)`.
- `start_observation` não aceita horário de início: como o observador é chamado DEPOIS da
  chamada ao modelo, o fim é fixado em `início do span + segundos`, e a latência real também
  vai no metadado `segundos`.
- Tags e metadata do traço (`propagate_attributes`) são um *context manager*. Para marcar o traço
  já em andamento, `marcar_traco` grava direto no span atual os mesmos atributos OpenTelemetry
  que o SDK usa (`LangfuseOtelSpanAttributes.TRACE_TAGS` e `TRACE_METADATA`).
- `cliente.get_trace_url()` faz uma chamada de rede (busca o projeto) e pode levantar erro:
  `url_do_traco` engole a falha e devolve `None`.
- `flush()` e `shutdown()` existem no cliente. Chame `flush()` no fim de scripts curtos.
- Custo: o Langfuse calcula o custo pelo NOME do modelo. Se o painel mostrar zero, cadastre o
  preço de `claude-sonnet-5-5` e `claude-haiku-5-5` em *Models* (veja docs/issues/ricardo.md).

O servidor real não foi exercitado (sem chaves); os testes usam um exportador em memória.
"""

import functools
import json
import logging
import os
from collections.abc import Callable
from typing import Any, TypeVar

from radar import llm

log = logging.getLogger("radar.observabilidade")

F = TypeVar("F", bound=Callable[..., Any])

VARIAVEIS = ("LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY", "LANGFUSE_HOST")

_cliente_atual: Any = None  # o cliente Langfuse, ou None enquanto desligado


def _valor_valido(valor: str | None) -> bool:
    """Vazio ou exemplo (`pk-lf-...`, `<sua chave>`, `xxx`) não conta como configurado."""
    v = (valor or "").strip()
    return bool(v) and "..." not in v and not v.startswith("<") and not set(v) <= {"x", "X"}


def variaveis_faltando() -> list[str]:
    """NOMES das variáveis ausentes, vazias ou de exemplo (nunca os valores)."""
    return [nome for nome in VARIAVEIS if not _valor_valido(os.environ.get(nome))]


def ativo() -> bool:
    return _cliente_atual is not None


def _criar_cliente() -> Any:
    from langfuse import Langfuse, get_client

    public_key = os.environ["LANGFUSE_PUBLIC_KEY"].strip()
    Langfuse(
        public_key=public_key,
        secret_key=os.environ["LANGFUSE_SECRET_KEY"].strip(),
        host=os.environ["LANGFUSE_HOST"].strip(),
    )
    return get_client(public_key=public_key)


def _ativar_com(cliente: Any) -> None:
    global _cliente_atual
    _cliente_atual = cliente
    llm.registrar_observador(_observador_llm)


def ativar_langfuse() -> bool:
    """Liga o Langfuse se as chaves existirem. Idempotente. Sem chaves: False e nada quebra."""
    if _cliente_atual is not None:
        return True
    faltando = variaveis_faltando()
    if faltando:
        log.warning(
            "Langfuse desligado (modo no-op). Variáveis ausentes, vazias ou de exemplo: %s",
            ", ".join(faltando),
        )
        return False
    try:
        cliente = _criar_cliente()
    except Exception as erro:  # noqa: BLE001 - observabilidade nunca derruba o fluxo
        log.warning("Langfuse desligado: falha ao iniciar o cliente (%s)", type(erro).__name__)
        return False
    _ativar_com(cliente)
    log.info("Langfuse ligado.")
    return True


def _resetar() -> None:
    """Volta ao estado desligado sem encerrar o cliente (uso nos testes)."""
    global _cliente_atual
    _cliente_atual = None
    llm._observador = None


def _serializar(saida: Any) -> Any:
    if hasattr(saida, "model_dump"):
        return saida.model_dump(mode="json")
    return saida


def _tokens(usage: Any) -> dict[str, int] | None:
    """Aceita objeto (`input_tokens`/`output_tokens`) ou dict; tolera `usage` ausente."""
    if usage is None:
        return None
    if isinstance(usage, dict):
        entrada, saida = usage.get("input_tokens"), usage.get("output_tokens")
    else:
        entrada, saida = getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None)
    detalhes: dict[str, int] = {}
    if isinstance(entrada, int):
        detalhes["input"] = entrada
    if isinstance(saida, int):
        detalhes["output"] = saida
    return detalhes or None


def _observador_llm(info: dict[str, Any]) -> None:
    """Converte o dict de `radar.llm` numa generation (chamada vinda do cache = sem custo)."""
    cliente = _cliente_atual
    if cliente is None:
        return
    cache = bool(info.get("cache"))
    metadata: dict[str, Any] = {"cache": cache}
    if info.get("tentativa") is not None:
        metadata["tentativa"] = info["tentativa"]
    segundos = info.get("segundos")
    if segundos is not None:
        metadata["segundos"] = round(float(segundos), 4)
    args: dict[str, Any] = {
        "name": info.get("schema") or "chamada_llm",
        "as_type": "generation",
        "model": info.get("modelo"),
        "input": {"system": info.get("system"), "user": info.get("user")},
        "output": _serializar(info.get("saida")),
        "metadata": metadata,
    }
    if cache:
        args["cost_details"] = {"input": 0.0, "output": 0.0, "total": 0.0}
    else:
        usage = _tokens(info.get("usage"))
        if usage:
            args["usage_details"] = usage
    geracao = cliente.start_observation(**args)
    fim = None
    inicio = getattr(getattr(geracao, "_otel_span", None), "start_time", None)
    if segundos is not None and isinstance(inicio, int):
        fim = inicio + int(float(segundos) * 1e9)
    geracao.end(end_time=fim)


def observar(nome: str | None = None) -> Callable[[F], F]:
    """Decorador: usa o `observe` do Langfuse se ativo NA CHAMADA; senão chama a função direta."""

    def decorador(fn: F) -> F:
        cache: dict[str, Any] = {"cliente": None, "fn": None}

        @functools.wraps(fn)
        def embrulho(*args: Any, **kwargs: Any) -> Any:
            cliente = _cliente_atual
            if cliente is None:
                return fn(*args, **kwargs)
            if cache["cliente"] is not cliente:
                from langfuse import observe

                cache["cliente"], cache["fn"] = cliente, observe(name=nome or fn.__name__)(fn)
            return cache["fn"](*args, **kwargs)

        return embrulho  # type: ignore[return-value]

    return decorador


def _texto(valor: Any) -> str:
    valor = getattr(valor, "value", valor)
    return valor if isinstance(valor, str) else json.dumps(valor, default=str, ensure_ascii=False)


def marcar_traco(tipo_desvio: Any = None, **metadata: Any) -> None:
    """Põe tag e metadata no traço atual (ex.: o tipo do desvio). No-op sem Langfuse."""
    if _cliente_atual is None:
        return
    try:
        from langfuse import LangfuseOtelSpanAttributes as A
        from opentelemetry import trace

        span = trace.get_current_span()
        if not span.is_recording():
            return
        if tipo_desvio is not None:
            metadata = {"tipo_desvio": tipo_desvio, **metadata}
            antigas = list((getattr(span, "attributes", None) or {}).get(A.TRACE_TAGS, ()))
            tag = f"desvio:{_texto(tipo_desvio)}"
            span.set_attribute(A.TRACE_TAGS, antigas + [tag] if tag not in antigas else antigas)
        for chave, valor in metadata.items():
            span.set_attribute(f"{A.TRACE_METADATA}.{chave}", _texto(valor)[:200])
    except Exception:  # noqa: BLE001
        log.debug("marcar_traco falhou", exc_info=True)


def url_do_traco() -> str | None:
    """URL do traço atual, ou None (sem Langfuse, fora de um traço ou se o servidor falhar)."""
    if _cliente_atual is None:
        return None
    try:
        return _cliente_atual.get_trace_url()
    except Exception:  # noqa: BLE001 - a URL faz uma chamada de rede e pode falhar
        return None


def flush() -> None:
    """Envia o que estiver pendente. Obrigatório no fim de scripts curtos (eval, ping)."""
    if _cliente_atual is not None:
        try:
            _cliente_atual.flush()
        except Exception:  # noqa: BLE001
            log.debug("flush falhou", exc_info=True)


def desligar() -> None:
    """Envia o pendente e encerra o cliente. No-op sem Langfuse."""
    cliente = _cliente_atual
    if cliente is None:
        return
    try:
        cliente.shutdown()
    except Exception:  # noqa: BLE001
        log.debug("shutdown falhou", exc_info=True)
    _resetar()
