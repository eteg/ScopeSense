"""Configuração e arquivos do projeto, no mesmo SQLite dos achados.

Os PDFs ficam em disco (`arquivos_dir`, fora do Git); o banco guarda o índice.
"""

import re
import sqlite3
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

from radar.core.errors import EntradaInvalida, NaoEncontrado
from radar.projeto.models import Arquivo, ProjetoConfig

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projeto_config (
    projeto TEXT PRIMARY KEY,
    conteudo TEXT NOT NULL,
    atualizado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS arquivos (
    id TEXT PRIMARY KEY,
    projeto TEXT NOT NULL,
    nome TEXT NOT NULL,
    tipo TEXT NOT NULL,
    tamanho INTEGER NOT NULL,
    enviado_em TEXT NOT NULL,
    caminho TEXT NOT NULL
);
"""

MAX_BYTES = 20 * 1024 * 1024

# Tipo do arquivo pelo nome, enquanto o detector não lê o conteúdo.
_TIPOS = [
    (re.compile(r"contrato|aditivo|sow|proposta", re.I), "Contrato"),
    (re.compile(r"aso|fgts|cnd|certid|nr-?\d|seguro", re.I), "Terceiro"),
    (re.compile(r"ata|reuni|transcri", re.I), "Reunião"),
    (re.compile(r"e-?mail", re.I), "E-mail"),
]


def tipo_pelo_nome(nome: str) -> str:
    return next((tipo for padrao, tipo in _TIPOS if padrao.search(nome)), "Documento")


class ProjetoStore:
    def __init__(self, db_path: str | Path, arquivos_dir: str | Path) -> None:
        self._db = Path(db_path)
        self._dir = Path(arquivos_dir)
        self._db.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _conn(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self._db)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # --- configuração -------------------------------------------------------

    def config(self, projeto: str) -> ProjetoConfig | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT conteudo FROM projeto_config WHERE projeto = ?", (projeto,)
            ).fetchone()
        return ProjetoConfig.model_validate_json(row["conteudo"]) if row else None

    def salvar_config(self, projeto: str, config: ProjetoConfig) -> ProjetoConfig:
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO projeto_config (projeto, conteudo, atualizado_em) VALUES (?, ?, ?) "
                "ON CONFLICT(projeto) DO UPDATE SET conteudo = excluded.conteudo, "
                "atualizado_em = excluded.atualizado_em",
                (projeto, config.model_dump_json(), datetime.now(UTC).isoformat()),
            )
        return config

    # --- arquivos -----------------------------------------------------------

    def arquivos(self, projeto: str) -> list[Arquivo]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM arquivos WHERE projeto = ? ORDER BY enviado_em", (projeto,)
            ).fetchall()
        return [_to_arquivo(r) for r in rows]

    def adicionar_arquivo(self, projeto: str, nome: str, dados: bytes) -> Arquivo:
        nome = Path(nome).name.strip()  # nunca um caminho vindo do navegador
        if not nome:
            raise EntradaInvalida("Informe o nome do arquivo.")
        if len(dados) > MAX_BYTES:
            raise EntradaInvalida("Arquivo maior que 20 MB.")
        if not dados.startswith(b"%PDF-"):
            raise EntradaInvalida("Só PDF por enquanto.")
        arquivo_id = uuid.uuid4().hex
        destino = self._dir / f"{arquivo_id}.pdf"
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_bytes(dados)
        agora = datetime.now(UTC).isoformat()
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO arquivos (id, projeto, nome, tipo, tamanho, enviado_em, caminho) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (arquivo_id, projeto, nome, tipo_pelo_nome(nome), len(dados), agora, str(destino)),
            )
        return next(a for a in self.arquivos(projeto) if a.id == arquivo_id)

    def remover_arquivo(self, projeto: str, arquivo_id: str) -> None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT caminho FROM arquivos WHERE id = ? AND projeto = ?", (arquivo_id, projeto)
            ).fetchone()
            if row is None:
                raise NaoEncontrado(f"Arquivo {arquivo_id} não existe neste projeto.")
            conn.execute("DELETE FROM arquivos WHERE id = ?", (arquivo_id,))
        Path(row["caminho"]).unlink(missing_ok=True)


def _to_arquivo(row: sqlite3.Row) -> Arquivo:
    return Arquivo(
        id=row["id"],
        nome=row["nome"],
        tipo=row["tipo"],
        tamanho=row["tamanho"],
        enviado_em=row["enviado_em"],
    )
