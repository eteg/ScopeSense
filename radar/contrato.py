"""Contrato: divide em cláusulas (G-04), extrai obrigações (G-04) e indexa no ChromaDB (G-05).

Fluxo: `carregar_contrato()` -> `extrair_obrigacoes()` (uma chamada ao modelo por cláusula,
com cache no SQLite) -> `indexar_clausulas()` -> `buscar(texto)` devolve as cláusulas mais
parecidas (RAG). O modelo só devolve JSON; o número da cláusula é sempre preenchido pelo código.
"""

import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

from radar import config, db, llm
from radar.core.models import ListaObrigacoes, Obrigacao

PADRAO_CLAUSULA = re.compile(r"^###\s+(\d+(?:\.\d+)?)\s+(.*)$", re.M)
CONTRATO_PADRAO = Path(__file__).resolve().parent.parent / "data" / "contrato_alfa.md"

COLECAO = "clausulas_alfa"
CAMINHO_CHROMA = "chroma"
MODELO_EMBEDDING = "intfloat/multilingual-e5-small"
# O e5 corta em 512 tokens (~1.800 caracteres em português); pedaços menores para ter folga.
MAX_CARACTERES = 1200

SYSTEM_OBRIGACOES = (
    "Você lê UMA cláusula de um contrato e extrai as obrigações dela. "
    "Devolva só o JSON no formato pedido. "
    "Para cada obrigação: `texto` com a obrigação em uma frase fiel à cláusula; "
    "`tipo` é um de escopo, prazo, terceiro ou outro "
    "(escopo = o que está dentro ou fora do objeto; prazo = datas, marcos e SLA; "
    "terceiro = exigências sobre subcontratados; outro = o restante); "
    "`prazo` em ISO (AAAA-MM-DD) só quando houver uma data; "
    "`documento_exigido` quando a cláusula exigir um documento (ex.: ASO, NDA, FGTS). "
    "Em `clausula` repita o número informado. Não invente nada que não esteja no texto."
)

Chamar = Callable[..., ListaObrigacoes]


# --- G-04: cláusulas e obrigações ------------------------------------------------------


def dividir_clausulas(texto_md: str) -> list[dict]:
    """Separa o contrato pelos títulos `### N Título` / `### N.N Título`.

    Cada item é `{"numero", "titulo", "texto"}`; o texto vai até o próximo título. O
    cabeçalho e o preâmbulo (antes do primeiro `###`) são ignorados.
    """
    achados = list(PADRAO_CLAUSULA.finditer(texto_md))
    clausulas = []
    for i, m in enumerate(achados):
        fim = achados[i + 1].start() if i + 1 < len(achados) else len(texto_md)
        clausulas.append(
            {
                "numero": m.group(1),
                "titulo": m.group(2).strip(),
                "texto": texto_md[m.end() : fim].strip(),
            }
        )
    return clausulas


def carregar_contrato(caminho: str | Path | None = None) -> list[dict]:
    """Lê o contrato (UTF-8; padrão `data/contrato_alfa.md`) e devolve as cláusulas."""
    arquivo = Path(caminho) if caminho is not None else CONTRATO_PADRAO
    return dividir_clausulas(arquivo.read_text(encoding="utf-8"))


def _obrigacao_bruta(clausula: dict) -> Obrigacao:
    return Obrigacao(clausula=clausula["numero"], texto=clausula["texto"], tipo="outro")


def extrair_obrigacoes(
    clausulas: list[dict],
    *,
    chamar: Chamar | None = None,
    caminho_db: str | Path | None = None,
) -> list[Obrigacao]:
    """Uma chamada ao modelo por cláusula. Cache no SQLite: com obrigações já gravadas, não chama.

    Plano B: se a chamada de uma cláusula falhar (qualquer exceção) ou vier vazia, vira UMA
    obrigação com o texto bruto e `tipo="outro"`, para o RAG continuar funcionando. Quando
    alguma cláusula caiu no plano B por falha, o resultado NÃO é gravado (senão o cache
    guardaria o plano B para sempre); a próxima execução tenta o modelo de novo.
    """
    db.init_db(caminho_db)
    existentes = db.listar_obrigacoes(caminho=caminho_db)
    if existentes:
        return existentes

    chamar = chamar or llm.chamar_estruturado
    obrigacoes: list[Obrigacao] = []
    houve_falha = False
    for clausula in clausulas:
        user = (
            f'<clausula numero="{clausula["numero"]}">\n'
            f"{clausula['titulo']}\n\n{clausula['texto']}\n</clausula>"
        )
        try:
            lista = chamar(config.MODELO_PRINCIPAL, SYSTEM_OBRIGACOES, user, ListaObrigacoes)
            extraidas = list(lista.obrigacoes)
        except Exception:  # noqa: BLE001 - plano B: a falha do modelo não derruba o RAG
            houve_falha = True
            extraidas = []
        if not extraidas:
            obrigacoes.append(_obrigacao_bruta(clausula))
            continue
        for o in extraidas:
            o.clausula = clausula["numero"]  # o número vem do código, nunca do modelo
            obrigacoes.append(o)

    if not houve_falha:
        db.salvar_obrigacoes(obrigacoes, caminho=caminho_db)
    return obrigacoes


def tipo_da_clausula(numero: str, obrigacoes: list[Obrigacao]) -> str:
    """Tipo da cláusula: o primeiro tipo diferente de "outro" entre as obrigações dela."""
    tipos = [o.tipo for o in obrigacoes if o.clausula == numero]
    return next((t for t in tipos if t != "outro"), "outro")


# --- G-05: índice no ChromaDB (RAG) ----------------------------------------------------


def _embedding_padrao() -> Any:
    """Cria o e5 só quando preciso (importar torch e baixar o modelo é lento)."""
    from chromadb.utils import embedding_functions

    return embedding_functions.SentenceTransformerEmbeddingFunction(model_name=MODELO_EMBEDDING)


def _pedacos(clausula: dict, limite: int = MAX_CARACTERES) -> list[str]:
    """Texto da cláusula (com o título) em pedaços por parágrafo, cada um até `limite`."""
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n", clausula["texto"]) if p.strip()]
    cabeca = f"{clausula['numero']} {clausula['titulo']}"
    pedacos: list[str] = []
    atual = ""
    for p in paragrafos:
        if atual and len(atual) + len(p) + 2 > limite:
            pedacos.append(atual)
            atual = ""
        atual = f"{atual}\n\n{p}" if atual else p
    if atual or not pedacos:
        pedacos.append(atual)
    return [f"{cabeca}\n{p}".strip() for p in pedacos]


def indexar_clausulas(
    clausulas: list[dict],
    *,
    caminho: str | Path = CAMINHO_CHROMA,
    embedding_function: Any = None,
    obrigacoes: list[Obrigacao] | None = None,
) -> int:
    """Indexa as cláusulas do zero (apaga e recria a coleção, então reindexar não duplica).

    Cada pedaço entra com o prefixo `passage: ` (exigido pelos modelos e5) e os metadados
    `numero` e `tipo` (de `obrigacoes`, ou da chave `tipo` da cláusula, ou "outro").
    Devolve quantos pedaços foram indexados.
    """
    import chromadb

    ef = embedding_function if embedding_function is not None else _embedding_padrao()
    cliente = chromadb.PersistentClient(path=str(caminho))
    try:
        cliente.delete_collection(COLECAO)
    except Exception:  # noqa: BLE001 - na primeira vez a coleção não existe
        pass
    colecao = cliente.create_collection(
        COLECAO, embedding_function=ef, configuration={"hnsw": {"space": "cosine"}}
    )

    ids, documentos, metadados = [], [], []
    for clausula in clausulas:
        numero = clausula["numero"]
        tipo = (
            tipo_da_clausula(numero, obrigacoes)
            if obrigacoes is not None
            else clausula.get("tipo", "outro")
        )
        completo = f"{clausula['titulo']}\n{clausula['texto']}".strip()
        for i, pedaco in enumerate(_pedacos(clausula)):
            ids.append(f"{numero}#{i}")
            documentos.append(f"passage: {pedaco}")
            metadados.append({"numero": numero, "tipo": tipo, "texto": completo})
    if ids:
        colecao.add(ids=ids, documents=documentos, metadatas=metadados)
    return len(ids)


def buscar(
    texto: str,
    k: int = config.K_CLAUSULAS,
    *,
    caminho: str | Path = CAMINHO_CHROMA,
    embedding_function: Any = None,
) -> list[dict]:
    """As `k` cláusulas mais parecidas com `texto`, da mais para a menos próxima.

    Cada item: `{"numero", "texto", "tipo", "distancia"}` (distância de cosseno: menor é
    mais parecido). O texto é o da cláusula inteira; cada cláusula aparece uma só vez.
    """
    import chromadb

    ef = embedding_function if embedding_function is not None else _embedding_padrao()
    cliente = chromadb.PersistentClient(path=str(caminho))
    colecao = cliente.get_collection(COLECAO, embedding_function=ef)
    total = colecao.count()
    if total == 0:
        return []
    # Pede mais pedaços que `k`: cláusulas longas ocupam várias posições antes de deduplicar.
    r = colecao.query(query_texts=[f"query: {texto}"], n_results=min(total, k * 4))
    resultado: list[dict] = []
    vistos: set[str] = set()
    for meta, dist in zip(r["metadatas"][0], r["distances"][0], strict=True):
        if meta["numero"] in vistos:
            continue
        vistos.add(meta["numero"])
        resultado.append(
            {
                "numero": meta["numero"],
                "texto": meta["texto"],
                "tipo": meta["tipo"],
                "distancia": dist,
            }
        )
        if len(resultado) == k:
            break
    return resultado
