"""Armazenamento dos achados em SQLite (um arquivo, sem infraestrutura).

O achado inteiro fica em JSON; status e decisão ficam em colunas próprias para
filtrar. Cada decisão também entra em `decisoes`, que é o histórico usado
nos evals (cada "não é desvio" é um falso positivo registrado).
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from radar.achados.models import (
    Achado,
    AchadoNovo,
    Analise,
    Categoria,
    DecisaoPedido,
    Gravidade,
    Status,
)
from radar.core.errors import Conflito, NaoEncontrado

_SCHEMA = """
CREATE TABLE IF NOT EXISTS achados (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto TEXT NOT NULL,
    categoria TEXT NOT NULL,
    gravidade TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pendente',
    criado_em TEXT NOT NULL,
    decidido_por TEXT,
    decidido_em TEXT,
    comentario TEXT,
    conteudo TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS analises (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    projeto TEXT NOT NULL,
    executada_em TEXT NOT NULL,
    conteudo TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisoes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    achado_id INTEGER NOT NULL REFERENCES achados(id),
    decisao TEXT NOT NULL,
    decidido_por TEXT NOT NULL,
    decidido_em TEXT NOT NULL,
    comentario TEXT
);
"""

# Ordem do relatório: crítico -> atenção -> observação; no empate, o mais antigo.
_ORDEM_GRAVIDADE = {Gravidade.critico: 0, Gravidade.atencao: 1, Gravidade.observacao: 2}


class AchadoStore:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        """Uma conexão por operação: as rotas síncronas rodam em threads diferentes."""
        conn = sqlite3.connect(self._path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- escrita (só no banco do próprio Radar) -----------------------------

    def adicionar(self, projeto: str, novo: AchadoNovo) -> Achado:
        agora = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO achados (projeto, categoria, gravidade, criado_em, conteudo) "
                "VALUES (?, ?, ?, ?, ?)",
                (projeto, novo.categoria, novo.gravidade, agora, novo.model_dump_json()),
            )
            achado_id = cur.lastrowid
        return self.obter(achado_id)  # type: ignore[arg-type]

    def decidir(self, achado_id: int, pedido: DecisaoPedido) -> Achado:
        """Registra a decisão. Um achado só é decidido uma vez."""
        atual = self.obter(achado_id)
        if atual.status is not Status.pendente:
            raise Conflito(
                f"Achado {achado_id} já foi decidido ({atual.status}) por {atual.decidido_por}."
            )
        agora = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE achados SET status = ?, decidido_por = ?, decidido_em = ?, "
                "comentario = ? WHERE id = ? AND status = 'pendente'",
                (pedido.decisao, pedido.decidido_por, agora, pedido.comentario, achado_id),
            )
            conn.execute(
                "INSERT INTO decisoes (achado_id, decisao, decidido_por, decidido_em, comentario)"
                " VALUES (?, ?, ?, ?, ?)",
                (achado_id, pedido.decisao, pedido.decidido_por, agora, pedido.comentario),
            )
        return self.obter(achado_id)

    def desfazer(self, achado_id: int, por: str) -> Achado:
        """Volta o achado para pendente. O histórico guarda o "desfeito"."""
        atual = self.obter(achado_id)
        if atual.status is Status.pendente:
            raise Conflito(f"Achado {achado_id} ainda não foi decidido.")
        agora = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE achados SET status = 'pendente', decidido_por = NULL, "
                "decidido_em = NULL, comentario = NULL WHERE id = ?",
                (achado_id,),
            )
            conn.execute(
                "INSERT INTO decisoes (achado_id, decisao, decidido_por, decidido_em, comentario)"
                " VALUES (?, 'desfeito', ?, ?, ?)",
                (achado_id, por, agora, f"desfez: {atual.status}"),
            )
        return self.obter(achado_id)

    def registrar_analise(self, analise: Analise) -> None:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO analises (projeto, executada_em, conteudo) VALUES (?, ?, ?)",
                (analise.projeto, analise.executada_em.isoformat(), analise.model_dump_json()),
            )

    def ultima_analise(self, projeto: str) -> Analise:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT conteudo FROM analises WHERE projeto = ? "
                "ORDER BY executada_em DESC, id DESC",
                (projeto,),
            ).fetchone()
        if row is None:
            raise NaoEncontrado(f"Nenhuma análise registrada para {projeto}.")
        return Analise.model_validate_json(row["conteudo"])

    # --- leitura ------------------------------------------------------------

    def obter(self, achado_id: int) -> Achado:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM achados WHERE id = ?", (achado_id,)).fetchone()
        if row is None:
            raise NaoEncontrado(f"Achado {achado_id} não existe.")
        return _to_achado(row)

    def listar(
        self,
        *,
        projeto: str | None = None,
        status: Status | None = None,
        categoria: Categoria | None = None,
    ) -> list[Achado]:
        filtros, params = [], []
        for coluna, valor in (("projeto", projeto), ("status", status), ("categoria", categoria)):
            if valor is not None:
                filtros.append(f"{coluna} = ?")
                params.append(str(valor))
        where = f"WHERE {' AND '.join(filtros)}" if filtros else ""
        with self._conn() as conn:
            rows = conn.execute(f"SELECT * FROM achados {where}", params).fetchall()
        achados = [_to_achado(r) for r in rows]
        achados.sort(key=lambda a: (_ORDEM_GRAVIDADE[a.gravidade], a.criado_em, a.id))
        return achados


def _to_achado(row: sqlite3.Row) -> Achado:
    conteudo = json.loads(row["conteudo"])
    return Achado(
        **conteudo,
        id=row["id"],
        projeto=row["projeto"],
        criado_em=row["criado_em"],
        status=row["status"],
        decidido_por=row["decidido_por"],
        decidido_em=row["decidido_em"],
        comentario=row["comentario"],
    )
