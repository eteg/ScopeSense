"""Nó `buscar`: usa o RAG real (ChromaDB), indexa sozinho se faltar índice. Sem baixar modelo."""

from datetime import UTC, datetime

import chromadb
import pytest

from radar import contrato
from radar.core.models import Origem, Registro
from radar.nos import buscar as no

# O conftest troca `buscar_no_indice` por um falso em todo teste; guardamos o real aqui.
BUSCAR_REAL = no.buscar_no_indice


class EmbeddingFalso(chromadb.EmbeddingFunction):
    """Vetor por contagem de palavras-chave: determinístico e sem baixar modelo."""

    PALAVRAS = ("relatório", "treinamento", "prazo", "marco", "aso", "subcontratado", "aditivo")

    def __init__(self) -> None:
        pass

    def __call__(self, input):
        return [
            [float(texto.lower().count(p)) for p in self.PALAVRAS] + [0.01] for texto in input
        ]

    @staticmethod
    def name() -> str:
        return "embedding_falso_buscar_no"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return EmbeddingFalso()


def _registro(texto: str) -> Registro:
    data = datetime(2026, 12, 10, tzinfo=UTC)
    return Registro(id="r1", origem=Origem.slack, data=data, autor="A", texto=texto)


@pytest.fixture
def indice_tmp(tmp_path, monkeypatch):
    pasta = tmp_path / "chroma"
    monkeypatch.setattr(no, "CAMINHO_INDICE", pasta)
    monkeypatch.setattr(no, "EMBEDDING_FUNCTION", EmbeddingFalso())
    return pasta


def test_buscar_clausulas_do_registro_usa_buscador_injetado_com_o_texto():
    recebidos = []

    def buscador(texto):
        recebidos.append(texto)
        return [{"numero": "9", "texto": "x", "tipo": "outro", "distancia": 0.0}]

    achados = no.buscar_clausulas_do_registro(_registro("olá"), buscador=buscador)
    assert recebidos == ["olá"]
    assert achados[0]["numero"] == "9"


def test_no_buscar_devolve_clausulas_no_estado():
    estado = {"registro": _registro("módulo de relatórios"), "contexto": []}
    resultado = no.buscar(estado)  # buscador falso do conftest
    assert resultado["clausulas"][0]["numero"] == "2.2"


def test_nome_antigo_do_pipeline_continua_existindo():
    assert no.buscar_clausulas is no.buscar_clausulas_do_registro


def test_sem_indice_o_no_indexa_sozinho_e_busca(indice_tmp, monkeypatch):
    monkeypatch.setattr(no, "buscar_no_indice", BUSCAR_REAL)
    assert not indice_tmp.exists()

    achados = no.buscar_clausulas_do_registro(_registro("o módulo de relatório está fora"))

    assert indice_tmp.exists()
    assert len(achados) == 3
    assert achados[0]["numero"] == "2.2"
    assert set(achados[0]) == {"numero", "texto", "tipo", "distancia"}


def test_preparar_indice_e_idempotente(indice_tmp):
    assert no.preparar_indice() is True  # indexou agora
    assert no.preparar_indice() is False  # já existia: não reindexa
    colecao = chromadb.PersistentClient(path=str(indice_tmp)).get_collection(
        contrato.COLECAO, embedding_function=EmbeddingFalso()
    )
    total = colecao.count()
    assert total >= len(contrato.carregar_contrato())
    no.preparar_indice()
    assert colecao.count() == total


def test_colecao_vazia_e_reindexada(indice_tmp):
    pasta = str(indice_tmp)
    ef = EmbeddingFalso()
    cliente = chromadb.PersistentClient(path=pasta)
    cliente.create_collection(contrato.COLECAO, embedding_function=ef)  # existe, mas vazia
    assert no.preparar_indice() is True
    assert cliente.get_collection(contrato.COLECAO, embedding_function=ef).count() > 0


def test_erro_de_indexacao_vira_runtime_error_claro(indice_tmp, monkeypatch):
    def quebra(*a, **k):
        raise OSError("disco cheio")

    monkeypatch.setattr(contrato, "indexar_clausulas", quebra)
    with pytest.raises(RuntimeError, match="índice do contrato"):
        no.preparar_indice()


# --- integração com o e5 real (baixa ~120 MB na primeira vez) ---------------------------


@pytest.mark.integracao
def test_integracao_mensagem_do_joao_traz_clausula_6_entre_as_3(tmp_path, monkeypatch):
    pytest.importorskip("sentence_transformers")
    pasta = tmp_path / "chroma_real"
    try:
        ef = contrato._embedding_padrao()
        monkeypatch.setattr(no, "CAMINHO_INDICE", pasta)
        monkeypatch.setattr(no, "EMBEDDING_FUNCTION", ef)
        monkeypatch.setattr(no, "buscar_no_indice", BUSCAR_REAL)
        achados = no.buscar_clausulas_do_registro(_registro("o João da Nimbus começa amanhã"))
    except Exception as erro:  # noqa: BLE001 - sem rede ou sem o modelo: pula, não falha
        pytest.skip(f"modelo {contrato.MODELO_EMBEDDING} indisponível: {erro!r}")
    assert any(a["numero"].startswith("6.") for a in achados)
