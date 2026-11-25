"""G-12: cache SQLite das respostas do modelo, com cliente falso e banco temporário."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from radar import cache_llm, config, db, llm
from radar.core.models import SaidaClassificacao

SAIDA = SaidaClassificacao(
    tipo="prazo_sla",
    confianca=0.85,
    clausula="4.1",
    trecho_contrato="30 dias",
    trecho_evidencia="entrega em 10 dias",
    justificativa="Prazo diferente do contrato.",
)


class ClienteFalso:
    def __init__(self) -> None:
        self.chamadas = 0
        self.messages = SimpleNamespace(parse=self._parse)

    def _parse(self, **kwargs):
        self.chamadas += 1
        return SimpleNamespace(parsed_output=SAIDA, usage=None)


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    monkeypatch.setattr(llm, "CONTADORES", {"chamadas": 0, "invalidas": 0, "retentativas": 0})
    monkeypatch.setattr(llm, "_cache_get", None)  # o teardown restaura o original
    monkeypatch.setattr(llm, "_cache_set", None)
    monkeypatch.setattr(llm, "_observador", None)
    monkeypatch.setattr(config, "MODO_DEMO", False)
    falso = ClienteFalso()
    monkeypatch.setattr(llm, "_client", falso)
    return falso


def chamar():
    return llm.chamar_estruturado("modelo-x", "sistema", "usuario", SaidaClassificacao)


def test_grava_na_primeira_e_nao_chama_na_segunda_com_modo_demo(isolado, tmp_path, monkeypatch):
    banco = tmp_path / "radar.db"
    cache_llm.ativar_cache_sqlite(banco)
    assert cache_llm.cache_cheio(banco) == 0

    assert chamar() == SAIDA
    assert isolado.chamadas == 1
    assert cache_llm.cache_cheio(banco) == 1
    chave = llm.chave_cache("modelo-x", "sistema", "usuario", SaidaClassificacao)
    assert db.cache_get(chave, caminho=banco) == SAIDA.model_dump_json()

    monkeypatch.setattr(config, "MODO_DEMO", True)
    assert chamar() == SAIDA
    assert isolado.chamadas == 1  # veio do cache, sem chamar o modelo


def test_sem_modo_demo_sempre_chama(isolado, tmp_path):
    cache_llm.ativar_cache_sqlite(tmp_path / "radar.db")
    chamar()
    chamar()
    assert isolado.chamadas == 2


def test_padrao_usa_config_database_path(isolado, tmp_path, monkeypatch):
    banco = tmp_path / "padrao.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(banco))
    cache_llm.ativar_cache_sqlite()
    chamar()
    assert banco.exists() and cache_llm.cache_cheio() == 1


def test_desativar_cache(isolado, tmp_path, monkeypatch):
    banco = tmp_path / "radar.db"
    cache_llm.ativar_cache_sqlite(banco)
    cache_llm.desativar_cache()
    chamar()
    assert cache_llm.cache_cheio(banco) == 0  # nada gravado
    monkeypatch.setattr(config, "MODO_DEMO", True)
    chamar()
    assert isolado.chamadas == 2  # nada lido


def _carregar_script():
    caminho = Path(__file__).resolve().parents[1] / "scripts" / "aquecer_cache.py"
    spec = importlib.util.spec_from_file_location("aquecer_cache", caminho)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_aquecer_enche_o_cache_com_analisar_falso(isolado, tmp_path, monkeypatch):
    script = _carregar_script()
    vistos = []

    def analisar(registro, contexto):
        vistos.append((registro.texto, config.MODO_DEMO))
        return chamar_com(registro.texto)

    def chamar_com(texto):
        return llm.chamar_estruturado("m", "s", texto, SaidaClassificacao)

    monkeypatch.setattr(config, "MODO_DEMO", True)
    banco = tmp_path / "radar.db"
    resumo = script.aquecer(analisar, pasta="data", caminho=banco)
    textos = {t for t, _ in vistos}
    assert set(script.FRASES_DEMO) <= textos  # as 3 frases da demo entram
    assert all(demo is False for _, demo in vistos)
    assert config.MODO_DEMO is True  # restaurado
    assert resumo["erros"] == 0
    assert resumo["chamadas"] == resumo["registros"] == resumo["no_cache"]
    assert resumo["no_cache"] >= 3 + 4


def test_aquecer_sem_chave_falha_com_mensagem(monkeypatch, capsys):
    script = _carregar_script()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert script.main() == 1
    assert "ANTHROPIC_API_KEY" in capsys.readouterr().err
