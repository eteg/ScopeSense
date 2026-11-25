"""Gera os 3 PDFs sintéticos do terceiro (Nimbus Serviços) em data/documentos/ (issue G-10).

Texto selecionável (sem imagem, sem OCR), formato fixo e simples para a extração por regex
de `radar/documentos.py` ser confiável. Tudo fictício: o CPF vem do Faker pt_BR com seed fixa.

Uso:
    python scripts/gerar_pdfs.py [pasta_de_saida]
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf
from faker import Faker

RAIZ = Path(__file__).resolve().parents[1]
PASTA_PADRAO = RAIZ / "data" / "documentos"

MARCA = "DOCUMENTO FICTÍCIO"
EMPRESA = "Nimbus Serviços"
SEED_CPF = 20261125  # fixa: o CPF falso sai igual em toda execução


def gerar_cpf() -> str:
    """CPF falso (formato 000.000.000-00) do Faker pt_BR, reprodutível. Nunca um CPF real."""
    fake = Faker("pt_BR")
    fake.seed_instance(SEED_CPF)
    return fake.cpf()


def _escrever(caminho: Path, titulo: str, linhas: list[str]) -> None:
    """Uma página A4: marca no topo, título em negrito e uma linha de texto por item."""
    doc = pymupdf.open()
    pagina = doc.new_page(width=595, height=842)
    pagina.insert_text((50, 60), MARCA, fontname="hebo", fontsize=14, color=(0.7, 0.1, 0.1))
    pagina.insert_text((50, 100), titulo, fontname="hebo", fontsize=13)
    y = 140
    for linha in linhas:
        pagina.insert_text((50, y), linha, fontname="helv", fontsize=11)
        y += 22
    doc.save(caminho)
    doc.close()


def gerar_aso(pasta: Path) -> Path:
    caminho = pasta / "aso_joao_teixeira.pdf"
    _escrever(
        caminho,
        "ATESTADO DE SAÚDE OCUPACIONAL (ASO)",
        [
            f"Empresa: {EMPRESA}",
            "Colaborador: João Teixeira",
            f"CPF: {gerar_cpf()}",
            "Parecer: Apto para a função",
            "Validade: 10/11/2026",
        ],
    )
    return caminho


def gerar_relacao(pasta: Path) -> Path:
    caminho = pasta / "documentos_nimbus_012027.pdf"
    # A guia de FGTS do mês NÃO está na lista, de propósito: quem acusa a falta é outra issue.
    _escrever(
        caminho,
        "RELAÇÃO DE DOCUMENTOS ENTREGUES",
        [
            f"Empresa: {EMPRESA}",
            "Competência: 01/2027",
            "Data de entrega: 26/01/2027",
            "pessoa | documento | validade",
            "Carla Mota | ASO | 15/08/2027",
            "- | NDA assinado | sem validade",
            "Carla Mota | Certificado de treinamento de segurança | 30/11/2027",
        ],
    )
    return caminho


def gerar_certidao(pasta: Path) -> Path:
    caminho = pasta / "certidao_negativa_nimbus.pdf"
    _escrever(
        caminho,
        "CERTIDÃO NEGATIVA DE DÉBITOS",
        [
            f"Empresa: {EMPRESA}",
            "Situação: sem débitos pendentes",
            "Validade: 30/06/2027",
        ],
    )
    return caminho


def gerar_pdfs(pasta: str | Path | None = None) -> list[Path]:
    destino = Path(pasta) if pasta else PASTA_PADRAO
    destino.mkdir(parents=True, exist_ok=True)
    return [gerar_aso(destino), gerar_relacao(destino), gerar_certidao(destino)]


if __name__ == "__main__":
    saida = sys.argv[1] if len(sys.argv) > 1 else None
    for arquivo in gerar_pdfs(saida):
        print(arquivo)
