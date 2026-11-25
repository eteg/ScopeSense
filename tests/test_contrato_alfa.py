"""Contrato sintético do Projeto Alfa: formato de cláusulas e fatos que sustentam os 4 desvios."""

import re
from pathlib import Path

CAMINHO = Path(__file__).parent.parent / "data" / "contrato_alfa.md"
PADRAO = re.compile(r"^###\s+(\d+(?:\.\d+)?)\s+(.*)$", re.M)

ESPERADAS = ["1", "2.1", "2.2", "3", "4", "5", "6.1", "6.2", "6.3", "6.4", "7", "8", "9"]


def _clausulas() -> dict[str, str]:
    texto = CAMINHO.read_text(encoding="utf-8")
    achados = list(PADRAO.finditer(texto))
    clausulas = {}
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(texto)
        clausulas[m.group(1)] = texto[m.end() : fim]
    return clausulas


def test_numeracao_exata_e_em_ordem():
    texto = CAMINHO.read_text(encoding="utf-8")
    assert [m.group(1) for m in PADRAO.finditer(texto)] == ESPERADAS


def test_fora_do_escopo():
    c = _clausulas()["2.2"]
    assert "relatórios" in c
    assert "treinamento presencial" in c


def test_marco_m3():
    assert "29/01/2027" in _clausulas()["3"]


def test_aditivo():
    assert "aditivo" in _clausulas()["5"]


def test_documentos_do_terceiro():
    c = _clausulas()
    assert "ASO" in c["6.1"]
    assert "FGTS" in c["6.4"]


def test_treinamento_remoto():
    c = _clausulas()["7"]
    assert "2 horas" in c or "duas horas" in c
