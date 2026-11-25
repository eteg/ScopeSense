"""Nó `buscar`: devolve as cláusulas do contrato mais próximas do registro (RAG, ChromaDB).

Usa `radar.contrato.buscar_clausulas` (e não `buscar`): ela tem a regra do terceiro, sem a qual
o desvio 3 não vê a cláusula 6. Se o índice ainda não existe, ele é criado uma vez, sozinho.
"""

import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from radar import contrato
from radar.core.models import Registro

Buscador = Callable[[str], list[dict]]

# Onde fica o índice e qual embedding usar. Os testes trocam estes dois valores
# (embedding `None` = o e5 de verdade, criado só quando preciso).
CAMINHO_INDICE: str | Path = contrato.CAMINHO_CHROMA
EMBEDDING_FUNCTION: Any = None

_trava = threading.Lock()


def _colecao_tem_dados(caminho: str | Path, embedding_function: Any) -> bool:
    """A coleção existe e tem pelo menos um pedaço? Qualquer falha de leitura vale como não."""
    import chromadb

    if not Path(caminho).exists():
        return False
    try:
        cliente = chromadb.PersistentClient(path=str(caminho))
        kwargs = {"embedding_function": embedding_function} if embedding_function else {}
        return cliente.get_collection(contrato.COLECAO, **kwargs).count() > 0
    except Exception:  # noqa: BLE001 - coleção ausente (ou ilegível): vai reindexar
        return False


def preparar_indice(caminho: str | Path | None = None, embedding_function: Any = None) -> bool:
    """Garante o índice do contrato no ChromaDB. Idempotente e seguro entre threads.

    Devolve `True` se indexou agora e `False` se já existia. Qualquer erro vira `RuntimeError`.
    """
    caminho = CAMINHO_INDICE if caminho is None else caminho
    ef = embedding_function if embedding_function is not None else EMBEDDING_FUNCTION
    with _trava:
        if _colecao_tem_dados(caminho, ef):
            return False
        try:
            total = contrato.indexar_clausulas(
                contrato.carregar_contrato(), caminho=caminho, embedding_function=ef
            )
        except Exception as erro:  # noqa: BLE001
            raise RuntimeError(
                f"Não foi possível criar o índice do contrato em '{caminho}': {erro!r}"
            ) from erro
        if total == 0:
            raise RuntimeError(f"O índice do contrato em '{caminho}' ficou vazio.")
        return True


def buscar_no_indice(texto: str) -> list[dict]:
    """Busca padrão: indexa se faltar, consulta e, se o índice sumir no meio, indexa e repete."""
    preparar_indice()
    try:
        achados = contrato.buscar_clausulas(
            texto, caminho=CAMINHO_INDICE, embedding_function=EMBEDDING_FUNCTION
        )
    except Exception as erro:  # noqa: BLE001
        raise RuntimeError(f"Falha ao consultar o índice do contrato: {erro!r}") from erro
    if achados:
        return achados
    # Coleção vazia ou apagada depois da checagem: reindexa uma vez e tenta de novo.
    with _trava:
        contrato.indexar_clausulas(
            contrato.carregar_contrato(),
            caminho=CAMINHO_INDICE,
            embedding_function=EMBEDDING_FUNCTION,
        )
    try:
        return contrato.buscar_clausulas(
            texto, caminho=CAMINHO_INDICE, embedding_function=EMBEDDING_FUNCTION
        )
    except Exception as erro:  # noqa: BLE001
        raise RuntimeError(f"Falha ao consultar o índice do contrato: {erro!r}") from erro


def buscar_clausulas_do_registro(
    registro: Registro,
    contexto: Sequence[Registro] = (),
    *,
    buscador: Buscador | None = None,
) -> list[dict]:
    """Função pura. Formato de `contrato.buscar`: numero, texto, tipo, distancia.

    A consulta é o texto do registro; `contexto` não entra na busca (só na classificação).
    `buscador` é injetável para os testes.
    """
    return (buscador or buscar_no_indice)(registro.texto)


# Nome que o pipeline já importava.
buscar_clausulas = buscar_clausulas_do_registro


def buscar(estado: dict) -> dict:
    """Wrapper fino do nó."""
    clausulas = buscar_clausulas_do_registro(estado["registro"], estado.get("contexto", ()))
    return {"clausulas": clausulas}
