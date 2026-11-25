"""Observabilidade (R-06): no-op sem chaves, observador com cliente falso e SDK real em memória.

Sem rede e sem chaves: o SDK real do Langfuse exporta para um `InMemorySpanExporter`.
"""

import inspect
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from radar import grafo, llm, pipeline
from radar import observabilidade as obs


@pytest.fixture(autouse=True)
def limpo(monkeypatch):
    for nome in obs.VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)
    obs._resetar()
    yield
    obs._resetar()


class Saida(BaseModel):
    tipo: str
    confianca: float


class FalsaGeracao:
    def __init__(self, inicio):
        self._otel_span = SimpleNamespace(start_time=inicio)
        self.fim = "nao terminou"

    def end(self, end_time=None):
        self.fim = end_time


class FalsoCliente:
    def __init__(self, inicio=1_000):
        self.chamadas: list[dict] = []
        self.geracoes: list[FalsaGeracao] = []
        self.inicio = inicio

    def start_observation(self, **kwargs):
        self.chamadas.append(kwargs)
        geracao = FalsaGeracao(self.inicio)
        self.geracoes.append(geracao)
        return geracao


def _info(**extra):
    base = {
        "modelo": "claude-haiku-5-5", "schema": "Saida", "cache": False,
        "system": "sistema", "user": "usuario", "saida": Saida(tipo="x", confianca=0.9),
    }  # fmt: skip
    return {**base, **extra}


# --- ativar_langfuse -----------------------------------------------------------------------


def test_sem_variaveis_devolve_false_e_nao_registra(caplog):
    assert obs.ativar_langfuse() is False
    assert llm._observador is None
    assert not obs.ativo()
    assert "LANGFUSE_PUBLIC_KEY" in caplog.text


def test_variaveis_de_exemplo_tambem_ficam_desligadas(monkeypatch, caplog):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-...")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-...")
    monkeypatch.setenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
    assert obs.ativar_langfuse() is False
    assert llm._observador is None
    assert obs.variaveis_faltando() == ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    assert "pk-lf-" not in caplog.text  # só nomes, nunca valores


def test_sem_host_fica_desligado(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1234")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-5678")
    assert obs.ativar_langfuse() is False
    assert obs.variaveis_faltando() == ["LANGFUSE_HOST"]


def test_com_chaves_registra_observador_e_e_idempotente(monkeypatch):
    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-1234")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-5678")
    monkeypatch.setenv("LANGFUSE_HOST", "http://127.0.0.1:9")
    falso = FalsoCliente()
    criados = []
    monkeypatch.setattr(obs, "_criar_cliente", lambda: criados.append(1) or falso)
    assert obs.ativar_langfuse() is True
    assert obs.ativar_langfuse() is True
    assert criados == [1]
    assert llm._observador is obs._observador_llm


def test_falha_ao_criar_cliente_nao_quebra(monkeypatch):
    for nome in obs.VARIAVEIS:
        monkeypatch.setenv(nome, "valor-real")

    def estoura():
        raise RuntimeError("segredo")

    monkeypatch.setattr(obs, "_criar_cliente", estoura)
    assert obs.ativar_langfuse() is False
    assert llm._observador is None


# --- modo no-op ------------------------------------------------------------------------------


def test_noop_sem_langfuse():
    obs.marcar_traco("escopo_extra", x=1)
    obs.flush()
    obs.desligar()
    assert obs.url_do_traco() is None
    obs._observador_llm(_info())  # sem cliente: não faz nada


def test_decorador_sem_langfuse_preserva_comportamento_nome_e_excecao():
    @obs.observar("soma")
    def soma(a: int, b: int = 2) -> int:
        """Soma."""
        return a + b

    @obs.observar()
    def falha() -> None:
        raise ValueError("boom")

    assert soma(1) == 3
    assert soma(1, b=5) == 6
    assert soma.__name__ == "soma"
    assert soma.__doc__ == "Soma."
    assert str(inspect.signature(soma)) == "(a: int, b: int = 2) -> int"
    with pytest.raises(ValueError, match="boom"):
        falha()


def test_processar_e_analisar_decorados_mantem_nome_e_assinatura():
    for funcao, nome in ((grafo.processar, "processar"), (pipeline.analisar, "analisar")):
        assert funcao.__name__ == nome
        assert hasattr(funcao, "__wrapped__")
        assert list(inspect.signature(funcao).parameters) == ["registro", "contexto"]


# --- _observador_llm com cliente falso -------------------------------------------------------


def test_observador_monta_generation_com_usage_objeto():
    cliente = FalsoCliente(inicio=1_000)
    obs._ativar_com(cliente)
    usage = SimpleNamespace(input_tokens=120, output_tokens=30)
    obs._observador_llm(_info(usage=usage, segundos=1.5, tentativa=2))
    chamada = cliente.chamadas[0]
    assert chamada["name"] == "Saida"
    assert chamada["as_type"] == "generation"
    assert chamada["model"] == "claude-haiku-5-5"
    assert chamada["input"] == {"system": "sistema", "user": "usuario"}
    assert chamada["output"] == {"tipo": "x", "confianca": 0.9}
    assert chamada["usage_details"] == {"input": 120, "output": 30}
    assert "cost_details" not in chamada
    assert chamada["metadata"] == {"cache": False, "tentativa": 2, "segundos": 1.5}
    assert cliente.geracoes[0].fim == 1_000 + 1_500_000_000


def test_observador_aceita_usage_dict():
    cliente = FalsoCliente()
    obs._ativar_com(cliente)
    obs._observador_llm(_info(usage={"input_tokens": 7, "output_tokens": 3}, segundos=0.2))
    assert cliente.chamadas[0]["usage_details"] == {"input": 7, "output": 3}


def test_observador_tolera_usage_ausente():
    cliente = FalsoCliente()
    obs._ativar_com(cliente)
    obs._observador_llm(_info(usage=None))
    obs._observador_llm(_info())
    obs._observador_llm(_info(usage={}))
    assert len(cliente.chamadas) == 3
    for chamada in cliente.chamadas:
        assert "usage_details" not in chamada
    assert cliente.geracoes[0].fim is None  # sem segundos: o SDK usa o horário atual


def test_observador_cache_marca_metadata_e_zera_custo():
    cliente = FalsoCliente()
    obs._ativar_com(cliente)
    usage = SimpleNamespace(input_tokens=999, output_tokens=999)
    obs._observador_llm(_info(cache=True, usage=usage))
    chamada = cliente.chamadas[0]
    assert chamada["metadata"] == {"cache": True}
    assert "usage_details" not in chamada
    assert chamada["cost_details"] == {"input": 0.0, "output": 0.0, "total": 0.0}


# --- SDK real, exportador em memória ---------------------------------------------------------


@pytest.fixture
def sdk_real():
    from langfuse import Langfuse
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exportador = InMemorySpanExporter()
    Langfuse(
        public_key="pk-lf-teste-local",
        secret_key="sk-lf-teste-local",
        host="http://127.0.0.1:9",  # nada é enviado: o exportador é em memória
        span_exporter=exportador,
        flush_at=1,
    )
    from langfuse import get_client

    cliente = get_client(public_key="pk-lf-teste-local")
    obs._ativar_com(cliente)
    yield cliente, exportador
    cliente.flush()


def test_sdk_real_traco_com_generation_tags_e_metadata(sdk_real):
    cliente, exportador = sdk_real

    @obs.observar("processar")
    def processar_falso(x: int) -> int:
        obs.marcar_traco("escopo_extra", fonte="teste")
        obs._observador_llm(
            _info(usage={"input_tokens": 10, "output_tokens": 5}, segundos=2.0, tentativa=1)
        )
        obs._observador_llm(_info(cache=True))
        return x * 2

    assert processar_falso(4) == 8
    cliente.flush()
    spans = {s.name: s for s in exportador.get_finished_spans()}
    raiz = spans["processar"]
    assert raiz.attributes["langfuse.trace.tags"] == ("desvio:escopo_extra",)
    assert raiz.attributes["langfuse.trace.metadata.tipo_desvio"] == "escopo_extra"
    assert raiz.attributes["langfuse.trace.metadata.fonte"] == "teste"
    geracoes = [s for s in exportador.get_finished_spans() if s.name == "Saida"]
    assert len(geracoes) == 2
    paga, em_cache = sorted(geracoes, key=lambda s: s.start_time)
    assert paga.parent.span_id == raiz.context.span_id
    assert paga.attributes["langfuse.observation.type"] == "generation"
    assert paga.attributes["langfuse.observation.model.name"] == "claude-haiku-5-5"
    assert '"input": 10' in paga.attributes["langfuse.observation.usage_details"]
    assert paga.end_time - paga.start_time == 2_000_000_000
    assert paga.attributes["langfuse.observation.metadata.cache"] == "false"
    assert em_cache.attributes["langfuse.observation.metadata.cache"] == "true"
    assert "langfuse.observation.usage_details" not in em_cache.attributes


def test_decorador_ativo_propaga_excecao(sdk_real):
    @obs.observar()
    def falha() -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        falha()


def test_url_do_traco_devolve_url_ou_engole_erro_de_rede():
    class Cliente:
        def get_trace_url(self):
            return "https://langfuse.exemplo/trace/1"

    obs._ativar_com(Cliente())
    assert obs.url_do_traco() == "https://langfuse.exemplo/trace/1"

    class Quebrado:
        def get_trace_url(self):
            raise ConnectionError("sem rede")

    obs._ativar_com(Quebrado())
    assert obs.url_do_traco() is None
