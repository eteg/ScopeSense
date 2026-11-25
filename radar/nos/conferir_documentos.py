"""Nó `conferir_documentos`: confere em código os documentos exigidos do terceiro (desvio 3).

Sem modelo e sem rede: nomes, datas e listas. O ASO (cláusula 6.1) é exigência da PESSOA e é o
que dispara o alerta; a guia de FGTS (cláusula 6.4) é exigência da EMPRESA e só entra na
justificativa, nunca dispara alerta sozinha.
"""

import unicodedata
from collections.abc import Sequence
from datetime import date, timedelta

from radar.core.models import Alerta, DocumentoExtraido, Registro, TipoDesvio
from radar.documentos import carregar_documentos, resumo_documento

PESSOAS_PADRAO = ("João Teixeira", "Carla Mota")

# Frase copiada literalmente da cláusula 6.1 de data/contrato_alfa.md.
TRECHO_CLAUSULA_6_1 = "O ASO vencido impede o início das atividades."


def _palavras(texto: str) -> str:
    """Minúsculas, sem acento nem pontuação, palavras separadas por um espaço, com bordas.

    Serve para achar nomes e "amanhã" por palavra inteira: " amanha " em " ... amanha ... ".
    """
    sem_acento = "".join(
        c for c in unicodedata.normalize("NFD", texto) if not unicodedata.combining(c)
    )
    limpo = "".join(c if c.isalnum() else " " for c in sem_acento.casefold())
    return f" {' '.join(limpo.split())} "


def _identificar_pessoa(texto: str, pessoas: Sequence[str]) -> str | None:
    """Nome completo ou primeiro nome, devolvido como está em `pessoas`."""
    palavras = _palavras(texto)
    for pessoa in pessoas:
        nome = _palavras(pessoa)
        primeiro = f" {nome.split()[0]} "
        if nome in palavras or primeiro in palavras:
            return pessoa
    return None


def _data_inicio(registro: Registro) -> date:
    """Data do registro, mais um dia se o texto diz "amanhã". Sempre `date`, nunca texto."""
    inicio = registro.data.date()
    if " amanha " in _palavras(registro.texto):
        inicio += timedelta(days=1)
    return inicio


def _escolher_aso(asos: list[DocumentoExtraido], inicio: date) -> DocumentoExtraido | None:
    """O ASO que vale na data de início; senão, o de validade mais recente (ou o sem validade)."""
    validos = [d for d in asos if d.validade is not None and d.validade >= inicio]
    if validos:
        return validos[0]
    return max(asos, key=lambda d: d.validade or date.min, default=None)


def conferir(
    alerta: Alerta,
    registro: Registro,
    documentos: Sequence[DocumentoExtraido] | None = None,
    pessoas: Sequence[str] = PESSOAS_PADRAO,
) -> Alerta | None:
    """Função pura. Só age no tipo `terceiro_sem_documento`; os demais voltam inalterados.

    Devolve o alerta reforçado (confiança 1.0, cláusula 6.1, documento como evidência) quando o
    ASO da pessoa venceu antes do início ou não foi entregue; `None` quando está tudo em dia.
    Se a pessoa não for identificada no texto, o alerta volta como veio. Não preenche
    `responsavel` (o roteamento faz isso).
    """
    if alerta.tipo != TipoDesvio.terceiro_sem_documento:
        return alerta
    pessoa = _identificar_pessoa(registro.texto, pessoas)
    if pessoa is None:
        return alerta

    inicio = _data_inicio(registro)
    docs = list(carregar_documentos() if documentos is None else documentos)
    dono = _palavras(pessoa)
    asos = [d for d in docs if d.tipo == "aso" and d.pessoa and _palavras(d.pessoa) == dono]
    aso = _escolher_aso(asos, inicio)
    if aso is not None and aso.validade is not None and aso.validade >= inicio:
        return None  # ASO em dia: a guia de FGTS sozinha não gera alerta

    if aso is None:
        evidencia = f"Sem ASO entregue para {pessoa}"
        motivo = f"não consta ASO de {pessoa} entre os documentos entregues"
    elif aso.validade is None:
        evidencia = resumo_documento(aso)
        motivo = f"o ASO de {pessoa} não informa validade"
    else:
        evidencia = resumo_documento(aso)
        motivo = f"o ASO de {pessoa} venceu em {aso.validade.strftime('%d/%m/%Y')}"
    justificativa = (
        f"Possível desvio: {motivo}, antes do início previsto ({inicio.strftime('%d/%m/%Y')}). "
        "Cláusula 6.1."
    )
    if not any(d.tipo == "fgts" for d in docs):
        justificativa += " Também não consta guia de FGTS (cláusula 6.4)."

    return alerta.model_copy(
        update={
            "tipo": TipoDesvio.terceiro_sem_documento,
            "confianca": 1.0,
            "clausula": "6.1",
            "trecho_contrato": TRECHO_CLAUSULA_6_1,
            "trecho_evidencia": evidencia,
            "justificativa": justificativa,
        }
    )


def conferir_documentos(estado: dict) -> dict:
    """Wrapper fino do nó.

    `conferir` devolve `None` quando está tudo em dia. O grafo liga este nó direto ao `rotear`
    (que não aceita `None`), então aqui isso vira um alerta `nenhum`: o roteamento descarta e o
    fluxo termina sem notificar.
    """
    alerta = estado["alerta"]
    conferido = conferir(alerta, estado["registro"])
    if conferido is None:
        conferido = alerta.model_copy(
            update={
                "tipo": TipoDesvio.nenhum,
                "confianca": 1.0,
                "clausula": "",
                "trecho_contrato": "",
                "trecho_evidencia": "",
                "justificativa": "Documentos do terceiro em dia na data de início.",
            }
        )
    return {"alerta": conferido}
