"""llm.chamar_estruturado com um cliente falso: sem rede e sem ANTHROPIC_API_KEY."""

from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError

from radar import config, llm
from radar.core.errors import SaidaInvalida
from radar.core.models import ListaObrigacoes, SaidaClassificacao

SAIDA = SaidaClassificacao(
    tipo="prazo_sla",
    confianca=0.85,
    clausula="4.1",
    trecho_contrato="30 dias",
    trecho_evidencia="entrega em 10 dias",
    justificativa="Prazo diferente do contrato.",
)


def _invalida() -> ValidationError:
    try:
        SaidaClassificacao.model_validate({})
    except ValidationError as erro:
        return erro
    raise AssertionError("não deveria validar")


class ClienteFalso:
    """Devolve, em ordem, os itens de `respostas`; uma exceção é levantada, não devolvida."""

    def __init__(self, respostas: list[Any]) -> None:
        self.respostas = list(respostas)
        self.chamadas: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs: Any) -> Any:
        self.chamadas.append(kwargs)
        item = self.respostas.pop(0)
        if isinstance(item, Exception):
            raise item
        return SimpleNamespace(parsed_output=item, usage=SimpleNamespace(input_tokens=1))


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    """Zera contadores, ganchos e cliente a cada teste."""
    monkeypatch.setattr(llm, "CONTADORES", {"chamadas": 0, "invalidas": 0, "retentativas": 0})
    monkeypatch.setattr(llm, "_client", None)
    monkeypatch.setattr(llm, "_cache_get", None)
    monkeypatch.setattr(llm, "_cache_set", None)
    monkeypatch.setattr(llm, "_observador", None)
    monkeypatch.setattr(config, "MODO_DEMO", False)


def chamar() -> SaidaClassificacao:
    return llm.chamar_estruturado("modelo-x", "sistema", "usuario", SaidaClassificacao)


def test_chamada_simples(monkeypatch):
    falso = ClienteFalso([SAIDA])
    monkeypatch.setattr(llm, "_client", falso)
    assert chamar() == SAIDA
    assert llm.CONTADORES == {"chamadas": 1, "invalidas": 0, "retentativas": 0}
    enviado = falso.chamadas[0]
    assert enviado["model"] == "modelo-x"
    assert enviado["output_format"] is SaidaClassificacao
    assert "temperature" not in enviado  # o SDK atual não aceita esse parâmetro


def test_argumentos_existem_no_sdk_real(monkeypatch):
    """Contrato com o SDK instalado: tudo o que enviamos a `messages.parse` precisa existir."""
    import inspect

    anthropic = pytest.importorskip("anthropic")
    falso = ClienteFalso([SAIDA])
    monkeypatch.setattr(llm, "_client", falso)
    chamar()
    aceitos = set(inspect.signature(anthropic.resources.messages.Messages.parse).parameters)
    assert set(falso.chamadas[0]) <= aceitos


def test_retenta_ao_receber_saida_invalida(monkeypatch):
    falso = ClienteFalso([_invalida(), None, SAIDA])
    monkeypatch.setattr(llm, "_client", falso)
    assert chamar() == SAIDA
    assert llm.CONTADORES == {"chamadas": 3, "invalidas": 2, "retentativas": 2}


def test_levanta_erro_depois_das_tentativas(monkeypatch):
    falso = ClienteFalso([_invalida()] * (config.TENTATIVAS_SCHEMA + 1))
    monkeypatch.setattr(llm, "_client", falso)
    with pytest.raises(SaidaInvalida):
        chamar()
    assert llm.CONTADORES["chamadas"] == config.TENTATIVAS_SCHEMA + 1
    assert llm.CONTADORES["retentativas"] == config.TENTATIVAS_SCHEMA


def test_erro_da_api_nao_e_retentado(monkeypatch):
    monkeypatch.setattr(llm, "_client", ClienteFalso([RuntimeError("rede caiu")]))
    with pytest.raises(RuntimeError):
        chamar()
    assert llm.CONTADORES["retentativas"] == 0


def test_cache_hit_em_modo_demo_nao_chama_o_modelo(monkeypatch):
    cache: dict[str, str] = {}
    llm.registrar_cache(cache.get, cache.__setitem__)
    monkeypatch.setattr(llm, "_client", ClienteFalso([SAIDA]))
    assert chamar() == SAIDA  # miss: chama o modelo e grava
    assert len(cache) == 1

    monkeypatch.setattr(config, "MODO_DEMO", True)
    falso = ClienteFalso([])  # qualquer chamada estouraria
    monkeypatch.setattr(llm, "_client", falso)
    assert chamar() == SAIDA
    assert falso.chamadas == []
    assert llm.CONTADORES["chamadas"] == 1


def test_sem_modo_demo_ignora_o_cache_na_leitura(monkeypatch):
    cache = {llm.chave_cache("modelo-x", "sistema", "usuario", SaidaClassificacao): "{}"}
    llm.registrar_cache(cache.get, cache.__setitem__)
    monkeypatch.setattr(llm, "_client", ClienteFalso([SAIDA]))
    assert chamar() == SAIDA
    assert llm.CONTADORES["chamadas"] == 1


def test_chave_do_cache_depende_de_modelo_system_user_e_schema():
    base = llm.chave_cache("m", "s", "u", SaidaClassificacao)
    assert base == llm.chave_cache("m", "s", "u", SaidaClassificacao)
    assert len({base, llm.chave_cache("n", "s", "u", SaidaClassificacao),
                llm.chave_cache("m", "t", "u", SaidaClassificacao),
                llm.chave_cache("m", "s", "v", SaidaClassificacao),
                llm.chave_cache("m", "s", "u", ListaObrigacoes)}) == 5  # fmt: skip


def test_observador_recebe_um_evento_por_chamada(monkeypatch):
    eventos: list[dict[str, Any]] = []
    llm.registrar_observador(eventos.append)
    monkeypatch.setattr(llm, "_client", ClienteFalso([SAIDA]))
    chamar()
    assert len(eventos) == 1
    assert eventos[0]["modelo"] == "modelo-x"
    assert eventos[0]["cache"] is False


def test_observador_com_erro_nao_derruba_a_chamada(monkeypatch):
    def quebrado(_: dict[str, Any]) -> None:
        raise RuntimeError("langfuse fora do ar")

    llm.registrar_observador(quebrado)
    monkeypatch.setattr(llm, "_client", ClienteFalso([SAIDA]))
    assert chamar() == SAIDA