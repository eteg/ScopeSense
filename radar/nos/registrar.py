"""Nó `registrar`: grava a decisão humana no SQLite (o status do alerta muda junto)."""

from radar import config, db


def registrar(estado: dict) -> dict:
    """Grava `estado["decisao"]`. Se o alerta já tinha decisão, não faz mais nada."""
    decisao = estado.get("decisao")
    if decisao is None:
        return {}
    caminho = config.DATABASE_PATH  # lido na hora da chamada (os testes trocam o banco)
    db.init_db(caminho)
    db.registrar_decisao(decisao, caminho=caminho)  # False = já decidido; nada mais a fazer
    return {}
