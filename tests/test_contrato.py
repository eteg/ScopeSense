"""Testes de radar/contrato.py (G-04 e G-05). A API do modelo e o e5 são trocados por falsos."""

import re
import shutil
from datetime import date
from pathlib import Path

import chromadb
import pytest

from radar import config, contrato, db
from radar.core.models import ListaObrigacoes, Obrigacao

NUMEROS_ESPERADOS = ["1", "2.1", "2.2", "3", "4", "5", "6.1", "6.2", "6.3", "6.4", "7", "8", "9"]


@pytest.fixture(scope="module")
def clausulas() -> list[dict]:
    return contrato.carregar_contrato()


class ModeloFalso:
    """Faz o papel de `chamar_estruturado`: uma obrigação por cláusula, com número errado."""

    def __init__(self) -> None:
        self.chamadas: list[str] = []

    def __call__(self, modelo, system, user, schema, temperatura=0.0):
        assert modelo == config.MODELO_PRINCIPAL
        assert schema is ListaObrigacoes
        numero = re.search(r'<clausula numero="([^"]+)">', user).group(1)
        self.chamadas.append(numero)
        return ListaObrigacoes(
            obrigacoes=[
                Obrigacao(
                    clausula="99",  # o "modelo" erra; o código tem de corrigir
                    texto=f"obrigação da cláusula {numero}",
                    tipo="prazo" if numero == "3" else "outro",
                    prazo=date(2026, 12, 22) if numero == "3" else None,
                )
            ]
        )


# --- G-04 ------------------------------------------------------------------------------


def test_dividir_clausulas_no_contrato_real(clausulas):
    assert [c["numero"] for c in clausulas] == NUMEROS_ESPERADOS
    por_numero = {c["numero"]: c for c in clausulas}
    assert por_numero["2.2"]["titulo"] == "Fora do escopo"
    assert "módulo de relatórios" in por_numero["2.2"]["texto"]
    assert "###" not in por_numero["2.2"]["texto"]
    assert "Pelo presente instrumento" not in por_numero["1"]["texto"]  # preâmbulo ignorado


def test_extrair_obrigacoes_preenche_clausula_pelo_codigo_e_usa_cache(clausulas, tmp_path):
    banco = tmp_path / "radar.db"
    falso = ModeloFalso()

    obrigacoes = contrato.extrair_obrigacoes(clausulas, chamar=falso, caminho_db=banco)

    assert falso.chamadas == NUMEROS_ESPERADOS  # uma chamada por cláusula
    assert [o.clausula for o in obrigacoes] == NUMEROS_ESPERADOS
    assert "99" not in {o.clausula for o in obrigacoes}
    assert len(db.listar_obrigacoes(caminho=banco)) == len(NUMEROS_ESPERADOS)

    # segunda execução: lê do SQLite, zero chamadas ao modelo
    falso2 = ModeloFalso()
    de_novo = contrato.extrair_obrigacoes(clausulas, chamar=falso2, caminho_db=banco)
    assert falso2.chamadas == []
    assert [(o.clausula, o.texto, o.prazo) for o in de_novo] == [
        (o.clausula, o.texto, o.prazo) for o in obrigacoes
    ]
    assert next(o for o in de_novo if o.clausula == "3").prazo == date(2026, 12, 22)


def test_plano_b_quando_o_modelo_falha(clausulas, tmp_path):
    banco = tmp_path / "radar.db"

    def quebrado(*args, **kwargs):
        raise RuntimeError("API fora do ar")

    obrigacoes = contrato.extrair_obrigacoes(clausulas, chamar=quebrado, caminho_db=banco)

    assert [o.clausula for o in obrigacoes] == NUMEROS_ESPERADOS
    assert all(o.tipo == "outro" for o in obrigacoes)
    por_numero = {c["numero"]: c for c in clausulas}
    assert all(o.texto == por_numero[o.clausula]["texto"] for o in obrigacoes)
    # o plano B não vira cache: quando a API voltar, a próxima execução usa o modelo
    assert db.listar_obrigacoes(caminho=banco) == []
    falso = ModeloFalso()
    contrato.extrair_obrigacoes(clausulas, chamar=falso, caminho_db=banco)
    assert len(falso.chamadas) == len(NUMEROS_ESPERADOS)


# --- G-05 ------------------------------------------------------------------------------

PALAVRAS = [
    "relatório", "treinamento", "prazo", "marco", "aso", "nda", "subcontratad", "sla",
    "incidente", "preço", "aditivo", "confidencial",
]  # fmt: skip


class EmbeddingFalso(chromadb.EmbeddingFunction):
    """Vetor por contagem de palavras-chave: determinístico e sem baixar modelo."""

    def __init__(self) -> None:
        pass

    def __call__(self, input):
        vetores = []
        for texto in input:
            baixo = texto.lower()
            vetores.append([float(baixo.count(p)) for p in PALAVRAS] + [0.01])
        return vetores

    @staticmethod
    def name() -> str:
        return "embedding_falso_contrato"

    def get_config(self):
        return {}

    @staticmethod
    def build_from_config(config):
        return EmbeddingFalso()


def test_indexar_e_buscar_com_embedding_falso(clausulas, tmp_path):
    pasta = tmp_path / "chroma"
    ef = EmbeddingFalso()
    obrigacoes = [Obrigacao(clausula="6.1", texto="ASO válido", tipo="terceiro")]

    n1 = contrato.indexar_clausulas(
        clausulas, caminho=pasta, embedding_function=ef, obrigacoes=obrigacoes
    )
    n2 = contrato.indexar_clausulas(
        clausulas, caminho=pasta, embedding_function=ef, obrigacoes=obrigacoes
    )  # reindexar não duplica
    assert n1 == n2 >= len(clausulas)
    colecao = chromadb.PersistentClient(path=str(pasta)).get_collection(
        contrato.COLECAO, embedding_function=ef
    )
    assert colecao.count() == n1

    achados = contrato.buscar(
        "o módulo de relatório está fora", k=3, caminho=pasta, embedding_function=ef
    )
    assert len(achados) == 3
    assert achados[0]["numero"] == "2.2"
    assert set(achados[0]) == {"numero", "texto", "tipo", "distancia"}
    assert "módulo de relatórios" in achados[0]["texto"]
    distancias = [a["distancia"] for a in achados]
    assert distancias == sorted(distancias)
    assert len({a["numero"] for a in achados}) == 3  # cada cláusula uma só vez

    # o tipo vem das obrigações da cláusula; sem obrigação, "outro"
    por_numero = {a["numero"]: a["tipo"] for a in contrato.buscar(
        "aso subcontratado", k=13, caminho=pasta, embedding_function=ef
    )}  # fmt: skip
    assert por_numero["6.1"] == "terceiro"
    assert por_numero["2.2"] == "outro"


def test_clausula_longa_vira_varios_pedacos_e_volta_uma_vez(tmp_path):
    paragrafos = [f"parágrafo {i} sobre prazo e marco. " + "x" * 400 for i in range(6)]
    longa = {"numero": "3", "titulo": "Prazos", "texto": "\n\n".join(paragrafos)}
    curta = {"numero": "7", "titulo": "Treinamento", "texto": "treinamento remoto"}
    pasta = tmp_path / "chroma"
    ef = EmbeddingFalso()

    n = contrato.indexar_clausulas([longa, curta], caminho=pasta, embedding_function=ef)

    assert n > 2
    assert all(len(p) <= contrato.MAX_CARACTERES + 50 for p in contrato._pedacos(longa))
    achados = contrato.buscar("prazo marco", k=3, caminho=pasta, embedding_function=ef)
    numeros = [a["numero"] for a in achados]
    assert numeros.count("3") == 1
    assert achados[0]["numero"] == "3"
    assert achados[0]["texto"].count("parágrafo") == 6  # devolve a cláusula inteira


# --- integração com o modelo real (baixa ~120 MB na primeira vez) ----------------------


@pytest.fixture(scope="module")
def indice_real(clausulas, tmp_path_factory):
    pytest.importorskip("sentence_transformers")
    pasta = tmp_path_factory.mktemp("chroma_real")
    try:
        ef = contrato._embedding_padrao()
        contrato.indexar_clausulas(clausulas, caminho=pasta, embedding_function=ef)
    except Exception as erro:  # noqa: BLE001 - sem rede ou sem o modelo: pula, não falha
        pytest.skip(f"modelo {contrato.MODELO_EMBEDDING} indisponível: {erro!r}")
    yield pasta, ef
    shutil.rmtree(Path(pasta), ignore_errors=True)


@pytest.mark.integracao
@pytest.mark.parametrize(
    ("consulta", "esperada"),
    [
        ("módulo de relatórios", {"2.2"}),
        ("o João começa amanhã", {"6.1", "6.2", "6.3", "6.4"}),
        ("entrega remarcada para depois do prazo", {"3"}),
    ],
)
def test_buscar_com_e5_real(indice_real, consulta, esperada):
    pasta, ef = indice_real
    achados = contrato.buscar(consulta, caminho=pasta, embedding_function=ef)
    numeros = [a["numero"] for a in achados]
    assert len(numeros) == config.K_CLAUSULAS
    assert esperada & set(numeros), f"{consulta!r} -> {numeros}"
