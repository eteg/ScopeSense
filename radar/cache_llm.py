"""G-12: cache das respostas do modelo no SQLite (tabela `llm_cache`).

`radar.llm` já sabe usar o cache: grava toda resposta nova quando um cache está registrado e só
LÊ quando `config.MODO_DEMO` está ligado. Este módulo apenas pluga `db.cache_get`/`db.cache_set`.

    ativar_cache_sqlite()   # liga (cria as tabelas se faltarem)
    desativar_cache()       # desliga (o eval não precisa disso: ele nem liga o cache)
    cache_cheio()           # quantas respostas estão guardadas
"""

from pathlib import Path

from radar import config, db, llm


def _destino(caminho: str | Path | None) -> str | Path:
    return caminho if caminho is not None else config.DATABASE_PATH


def ativar_cache_sqlite(caminho: str | Path | None = None) -> None:
    """Liga o cache ao banco `caminho` (padrão: `config.DATABASE_PATH`)."""
    destino = _destino(caminho)
    db.init_db(destino)

    def _ler(chave: str) -> str | None:
        return db.cache_get(chave, caminho=destino)

    def _gravar(chave: str, resposta: str) -> None:
        db.cache_set(chave, resposta, caminho=destino)

    llm.registrar_cache(_ler, _gravar)


def desativar_cache() -> None:
    """Desliga leitura e gravação do cache em `radar.llm`."""
    llm._cache_get = None
    llm._cache_set = None


def cache_cheio(caminho: str | Path | None = None) -> int:
    """Número de respostas do modelo guardadas em `llm_cache`."""
    destino = _destino(caminho)
    db.init_db(destino)
    con = db.conectar(destino)
    try:
        return con.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
    finally:
        con.close()
