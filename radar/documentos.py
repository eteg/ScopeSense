"""PDFs do terceiro → `DocumentoExtraido` por regex (determinístico, sem LLM) e → `Registro`."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pymupdf

from radar.core.models import DocumentoExtraido, Origem, Registro

PASTA_PADRAO = Path(__file__).resolve().parents[1] / "data" / "documentos"
FUSO = ZoneInfo("America/Sao_Paulo")
DATA_ENTREGA = datetime(2027, 1, 26, tzinfo=FUSO)  # data de entrega fixa dos documentos

_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4})")
_EMPRESA = re.compile(r"^Empresa:\s*(.+)$", re.MULTILINE)
_PESSOA = re.compile(r"^(?:Colaborador|Pessoa):\s*(.+)$", re.MULTILINE)
_VALIDADE = re.compile(r"^Validade:\s*(.+)$", re.MULTILINE)

# (trecho no título/nome do documento, tipo). Vale para o cabeçalho do PDF e para as linhas
# da relação. Texto já em minúsculas.
_TIPOS = [
    ("saúde ocupacional", "aso"),
    ("aso", "aso"),
    ("certidão negativa", "certidao_negativa"),
    ("certidao negativa", "certidao_negativa"),
    ("fgts", "fgts"),
    ("nda", "nda"),
    ("treinamento", "treinamento"),
]

_ROTULOS = {
    "aso": "ASO",
    "fgts": "Guia de FGTS",
    "certidao_negativa": "Certidão negativa",
    "nda": "NDA assinado",
    "treinamento": "Treinamento de segurança",
}


def _data(texto: str) -> date | None:
    """Primeira data dd/mm/aaaa do texto como `date` (dia primeiro, nunca mês primeiro)."""
    achou = _DATA.search(texto)
    if not achou:
        return None
    dia, mes, ano = (int(g) for g in achou.groups())
    return date(ano, mes, dia)


def _tipo(texto: str) -> str | None:
    baixo = texto.lower()
    for trecho, tipo in _TIPOS:
        if re.search(rf"\b{re.escape(trecho)}\b", baixo):
            return tipo
    return None


def _campo(padrao: re.Pattern[str], texto: str) -> str | None:
    achou = padrao.search(texto)
    return achou.group(1).strip() if achou else None


def _extrair_relacao(texto: str, arquivo: str) -> list[DocumentoExtraido]:
    """Uma linha `pessoa | documento | validade` vira um documento. O que não está listado
    (a guia de FGTS do mês) simplesmente não vira item."""
    empresa = _campo(_EMPRESA, texto)
    docs = []
    for linha in texto.splitlines():
        partes = [p.strip() for p in linha.split("|")]
        if len(partes) != 3 or partes[0].lower() == "pessoa":
            continue
        pessoa, documento, validade = partes
        tipo = _tipo(documento)
        if tipo is None:
            continue
        docs.append(
            DocumentoExtraido(
                tipo=tipo,
                pessoa=None if pessoa in ("", "-") else pessoa,
                empresa=empresa,
                validade=_data(validade),
                arquivo=arquivo,
            )
        )
    return docs


def _extrair(texto: str, arquivo: str) -> list[DocumentoExtraido]:
    cabecalho = " ".join(texto.splitlines()[:3])
    if "relação de documentos" in cabecalho.lower():
        return _extrair_relacao(texto, arquivo)
    tipo = _tipo(cabecalho)
    if tipo is None:
        return []
    return [
        DocumentoExtraido(
            tipo=tipo,
            pessoa=_campo(_PESSOA, texto),
            empresa=_campo(_EMPRESA, texto),
            validade=_data(_campo(_VALIDADE, texto) or ""),
            arquivo=arquivo,
        )
    ]


def carregar_documentos(pasta: str | Path | None = None) -> list[DocumentoExtraido]:
    """Lê todos os PDFs da pasta (padrão: `data/documentos`) e extrai tipo, pessoa, empresa e
    validade por regex. Ordem estável: por nome de arquivo."""
    pasta = Path(pasta) if pasta else PASTA_PADRAO
    docs: list[DocumentoExtraido] = []
    for caminho in sorted(pasta.glob("*.pdf")):
        with pymupdf.open(caminho) as pdf:
            texto = "\n".join(pagina.get_text() for pagina in pdf)
        docs.extend(_extrair(texto, caminho.name))
    return docs


def resumo_documento(doc: DocumentoExtraido) -> str:
    """Ex.: "ASO de João Teixeira, válido até 10/11/2026"."""
    rotulo = _ROTULOS.get(doc.tipo, doc.tipo)
    dono = doc.pessoa or doc.empresa
    texto = f"{rotulo} de {dono}" if dono else rotulo
    if doc.validade:
        valido = "válida" if doc.tipo in ("certidao_negativa", "fgts") else "válido"
        texto += f", {valido} até {doc.validade.strftime('%d/%m/%Y')}"
    else:
        texto += ", sem validade"
    return texto


def documentos_como_registros(docs: list[DocumentoExtraido]) -> list[Registro]:
    """Cada documento vira um Registro (origem=documento) para aparecer como evidência."""
    registros = []
    for doc in docs:
        texto = resumo_documento(doc)
        registros.append(
            Registro(
                id="documento:" + hashlib.sha1(texto.encode("utf-8")).hexdigest(),
                origem=Origem.documento,
                data=DATA_ENTREGA,
                autor=doc.empresa or "Terceiro",
                texto=texto,
                metadados={"arquivo": doc.arquivo, "pessoa": doc.pessoa, "tipo": doc.tipo},
            )
        )
    return registros
