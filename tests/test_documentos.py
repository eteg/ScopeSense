"""G-10: PDFs sintéticos do terceiro e extração determinística de tipo, pessoa e validade."""

import importlib.util
import re
from datetime import date
from pathlib import Path

import pymupdf
import pytest
from faker import Faker

from radar.core.models import Origem
from radar.documentos import (
    carregar_documentos,
    documentos_como_registros,
    resumo_documento,
)

RAIZ = Path(__file__).resolve().parents[1]


def _carregar_script():
    spec = importlib.util.spec_from_file_location("gerar_pdfs", RAIZ / "scripts" / "gerar_pdfs.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


@pytest.fixture
def script():
    return _carregar_script()


@pytest.fixture
def pasta(tmp_path, script):
    script.gerar_pdfs(tmp_path)
    return tmp_path


def _achar(docs, tipo, pessoa=None, arquivo=None):
    return [
        d
        for d in docs
        if d.tipo == tipo
        and (pessoa is None or d.pessoa == pessoa)
        and (arquivo is None or d.arquivo == arquivo)
    ]


def _texto(pasta: Path, nome: str) -> str:
    with pymupdf.open(pasta / nome) as pdf:
        return "\n".join(p.get_text() for p in pdf)


def test_gera_tres_pdfs_com_marca_e_texto_selecionavel(pasta):
    nomes = sorted(p.name for p in pasta.glob("*.pdf"))
    assert nomes == [
        "aso_joao_teixeira.pdf",
        "certidao_negativa_nimbus.pdf",
        "documentos_nimbus_012027.pdf",
    ]
    for nome in nomes:
        assert "DOCUMENTO FICTÍCIO" in _texto(pasta, nome)


def test_aso_do_joao_vencido(pasta):
    (aso,) = _achar(carregar_documentos(pasta), "aso", "João Teixeira")
    assert aso.validade == date(2026, 11, 10)
    assert aso.empresa == "Nimbus Serviços"
    assert aso.arquivo == "aso_joao_teixeira.pdf"


def test_aso_da_carla_em_dia_e_demais_itens_da_relacao(pasta):
    docs = carregar_documentos(pasta)
    (aso,) = _achar(docs, "aso", "Carla Mota")
    assert aso.validade == date(2027, 8, 15)
    assert aso.arquivo == "documentos_nimbus_012027.pdf"
    (nda,) = _achar(docs, "nda")
    assert nda.pessoa is None and nda.validade is None and nda.empresa == "Nimbus Serviços"
    (treino,) = _achar(docs, "treinamento", "Carla Mota")
    assert treino.validade == date(2027, 11, 30)


def test_certidao_negativa(pasta):
    (certidao,) = _achar(carregar_documentos(pasta), "certidao_negativa")
    assert certidao.validade == date(2027, 6, 30)
    assert certidao.empresa == "Nimbus Serviços"


def test_guia_de_fgts_ausente_nao_vira_item(pasta):
    docs = carregar_documentos(pasta)
    assert _achar(docs, "fgts") == []
    assert len(docs) == 5  # ASO do João + 3 da relação + certidão
    assert {d.tipo for d in docs} == {"aso", "nda", "treinamento", "certidao_negativa"}


def test_resumo(pasta):
    docs = carregar_documentos(pasta)
    (aso,) = _achar(docs, "aso", "João Teixeira")
    assert resumo_documento(aso) == "ASO de João Teixeira, válido até 10/11/2026"


def test_registros_com_id_estavel(pasta):
    docs = carregar_documentos(pasta)
    registros = documentos_como_registros(docs)
    de_novo = documentos_como_registros(carregar_documentos(pasta))
    assert [r.id for r in registros] == [r.id for r in de_novo]
    assert len({r.id for r in registros}) == len(registros)
    joao = next(r for r in registros if r.metadados["pessoa"] == "João Teixeira")
    assert joao.id.startswith("documento:") and len(joao.id) == len("documento:") + 40
    assert joao.origem is Origem.documento
    assert joao.texto == "ASO de João Teixeira, válido até 10/11/2026"
    assert joao.autor == "Nimbus Serviços"
    assert joao.data.isoformat() == "2027-01-26T00:00:00-03:00"
    assert joao.metadados["arquivo"] == "aso_joao_teixeira.pdf"


def test_cpf_do_aso_e_falso_do_faker(pasta, script):
    achou = re.search(r"CPF:\s*(\S+)", _texto(pasta, "aso_joao_teixeira.pdf"))
    assert achou
    cpf = achou.group(1)
    assert re.fullmatch(r"\d{3}\.\d{3}\.\d{3}-\d{2}", cpf)
    assert len(re.sub(r"\D", "", cpf)) == 11
    fake = Faker("pt_BR")
    fake.seed_instance(script.SEED_CPF)
    assert cpf == fake.cpf() == script.gerar_cpf()


def test_pasta_inexistente_devolve_vazio(tmp_path):
    assert carregar_documentos(tmp_path / "nao_existe") == []
