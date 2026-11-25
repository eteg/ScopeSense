"""Camada única de acesso ao SQLite local (data/radar.db): toda a persistência do Radar.

Só o módulo `sqlite3` da biblioteca padrão. Cada função abre a sua própria conexão e a
fecha ao terminar, então nunca há conexão compartilhada entre threads (o bot do Slack, o
Streamlit e o grafo rodam em threads/processos diferentes; o WAL deixa todos gravarem).

Todas as funções aceitam `caminho` (só por nome) para apontar para outro banco, o que
permite aos testes usar um banco temporário sem mexer em variável global.
"""

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from radar import config
from radar.core.models import (
    Acao,
    Alerta,
    Decisao,
    DocumentoExtraido,
    Obrigacao,
    Origem,
    Papel,
    Registro,
)

FUSO = ZoneInfo("America/Sao_Paulo")

_STATUS_POR_ACAO = {
    "aprovar": "aprovado",
    "descartar": "descartado",
    "nao_e_desvio": "nao_e_desvio",
}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS registros (
  id TEXT PRIMARY KEY, origem TEXT NOT NULL, data TEXT NOT NULL, autor TEXT NOT NULL,
  texto TEXT NOT NULL, link TEXT, canal TEXT, thread_id TEXT, metadados TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS obrigacoes (
  clausula TEXT NOT NULL, texto TEXT NOT NULL, tipo TEXT NOT NULL, prazo TEXT,
  documento_exigido TEXT,
  PRIMARY KEY (clausula, texto));
CREATE TABLE IF NOT EXISTS alertas (
  registro_id TEXT PRIMARY KEY, tipo TEXT NOT NULL, confianca REAL NOT NULL, clausula TEXT NOT NULL,
  trecho_contrato TEXT NOT NULL, trecho_evidencia TEXT NOT NULL, justificativa TEXT NOT NULL,
  responsavel TEXT, acao TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pendente',
  trace_url TEXT, slack_canal TEXT, slack_ts TEXT,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS decisoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, alerta_id TEXT NOT NULL UNIQUE,
  acao TEXT NOT NULL, quem TEXT NOT NULL, quando TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS documentos (
  id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT NOT NULL, pessoa TEXT, empresa TEXT,
  validade TEXT, arquivo TEXT NOT NULL UNIQUE);
CREATE TABLE IF NOT EXISTS llm_cache (
  chave TEXT PRIMARY KEY, resposta TEXT NOT NULL,
  criado_em TEXT NOT NULL DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS eval_execucoes (
  id INTEGER PRIMARY KEY AUTOINCREMENT, criado_em TEXT NOT NULL DEFAULT (datetime('now')),
  versao TEXT, metricas TEXT NOT NULL);
"""


class AlertaSalvo(Alerta):
    """Alerta como está guardado: o `Alerta` do modelo mais o estado do ciclo de vida."""

    acao: Acao
    status: str = "pendente"
    trace_url: str | None = None
    slack_canal: str | None = None
    slack_ts: str | None = None
    criado_em: str | None = None
    decisao: Decisao | None = None


def _iso(valor: datetime | date | None) -> str | None:
    """Data em ISO 8601. `datetime` sem fuso ganha America/Sao_Paulo (ordenação estável)."""
    if valor is None:
        return None
    if isinstance(valor, datetime) and valor.tzinfo is None:
        valor = valor.replace(tzinfo=FUSO)
    return valor.isoformat()


def conectar(caminho: str | Path | None = None) -> sqlite3.Connection:
    """Abre uma conexão nova (use uma por chamada ou por thread; não compartilhe)."""
    destino = Path(caminho if caminho is not None else config.DATABASE_PATH)
    destino.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(destino, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA busy_timeout=10000")
    return con


@contextmanager
def _sessao(caminho: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    """Conexão própria da chamada: confirma ao sair com sucesso, desfaz no erro e fecha."""
    con = conectar(caminho)
    try:
        with con:
            yield con
    finally:
        con.close()


def init_db(caminho: str | Path | None = None) -> None:
    """Cria as 7 tabelas se faltarem. Idempotente."""
    con = conectar(caminho)
    try:
        with con:
            con.executescript(_SCHEMA)
    finally:
        con.close()


# --- registros -------------------------------------------------------------------------


def salvar_registro(registro: Registro, *, caminho: str | Path | None = None) -> None:
    with _sessao(caminho) as con:
        con.execute(
            "INSERT OR REPLACE INTO registros "
            "(id, origem, data, autor, texto, link, canal, thread_id, metadados) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                registro.id,
                registro.origem.value,
                _iso(registro.data),
                registro.autor,
                registro.texto,
                registro.link,
                registro.canal,
                registro.thread_id,
                json.dumps(registro.metadados, ensure_ascii=False, default=str),
            ),
        )


def obter_registro(registro_id: str, *, caminho: str | Path | None = None) -> Registro | None:
    with _sessao(caminho) as con:
        r = con.execute("SELECT * FROM registros WHERE id = ?", (registro_id,)).fetchone()
    if r is None:
        return None
    return Registro(
        id=r["id"],
        origem=Origem(r["origem"]),
        data=datetime.fromisoformat(r["data"]),
        autor=r["autor"],
        texto=r["texto"],
        link=r["link"],
        metadados=json.loads(r["metadados"]),
    )


# --- obrigações ------------------------------------------------------------------------


def salvar_obrigacoes(obrigacoes: list[Obrigacao], *, caminho: str | Path | None = None) -> None:
    with _sessao(caminho) as con:
        con.executemany(
            "INSERT OR REPLACE INTO obrigacoes (clausula, texto, tipo, prazo, documento_exigido) "
            "VALUES (?, ?, ?, ?, ?)",
            [(o.clausula, o.texto, o.tipo, _iso(o.prazo), o.documento_exigido) for o in obrigacoes],
        )


def listar_obrigacoes(*, caminho: str | Path | None = None) -> list[Obrigacao]:
    with _sessao(caminho) as con:
        linhas = con.execute("SELECT * FROM obrigacoes ORDER BY rowid").fetchall()
    return [
        Obrigacao(
            clausula=r["clausula"],
            texto=r["texto"],
            tipo=r["tipo"],
            prazo=date.fromisoformat(r["prazo"]) if r["prazo"] else None,
            documento_exigido=r["documento_exigido"],
        )
        for r in linhas
    ]


# --- alertas e decisões ----------------------------------------------------------------


def salvar_alerta(
    alerta: Alerta,
    acao: Acao | str,
    status: str = "pendente",
    *,
    trace_url: str | None = None,
    caminho: str | Path | None = None,
) -> None:
    """Grava (ou atualiza) o alerta do registro. Não mexe nos campos do Slack."""
    with _sessao(caminho) as con:
        con.execute(
            "INSERT INTO alertas (registro_id, tipo, confianca, clausula, trecho_contrato, "
            "trecho_evidencia, justificativa, responsavel, acao, status, trace_url) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(registro_id) DO UPDATE SET tipo=excluded.tipo, "
            "confianca=excluded.confianca, clausula=excluded.clausula, "
            "trecho_contrato=excluded.trecho_contrato, trecho_evidencia=excluded.trecho_evidencia, "
            "justificativa=excluded.justificativa, responsavel=excluded.responsavel, "
            "acao=excluded.acao, status=excluded.status, "
            "trace_url=COALESCE(excluded.trace_url, alertas.trace_url)",
            (
                alerta.registro_id,
                alerta.tipo.value,
                alerta.confianca,
                alerta.clausula,
                alerta.trecho_contrato,
                alerta.trecho_evidencia,
                alerta.justificativa,
                alerta.responsavel.value if alerta.responsavel else None,
                Acao(acao).value,
                status,
                trace_url,
            ),
        )


def atualizar_slack_msg(
    registro_id: str, canal: str, ts: str, *, caminho: str | Path | None = None
) -> None:
    """Guarda a mensagem do alerta no Slack, para atualizá-la depois do clique."""
    with _sessao(caminho) as con:
        con.execute(
            "UPDATE alertas SET slack_canal = ?, slack_ts = ? WHERE registro_id = ?",
            (canal, ts, registro_id),
        )


def listar_alertas(
    papel: Papel | str | None = None,
    status: str | None = None,
    *,
    caminho: str | Path | None = None,
) -> list[AlertaSalvo]:
    """Alertas (mais antigos primeiro), já com a decisão, se houver. Filtra por papel e status."""
    sql = (
        "SELECT a.*, d.acao AS d_acao, d.quem AS d_quem, d.quando AS d_quando "
        "FROM alertas a LEFT JOIN decisoes d ON d.alerta_id = a.registro_id"
    )
    filtros, params = [], []
    if papel is not None:
        filtros.append("a.responsavel = ?")
        params.append(Papel(papel).value)
    if status is not None:
        filtros.append("a.status = ?")
        params.append(status)
    if filtros:
        sql += " WHERE " + " AND ".join(filtros)
    sql += " ORDER BY a.criado_em, a.rowid"
    with _sessao(caminho) as con:
        linhas = con.execute(sql, params).fetchall()
    resultado = []
    for r in linhas:
        decisao = None
        if r["d_acao"] is not None:
            decisao = Decisao(
                alerta_id=r["registro_id"],
                acao=r["d_acao"],
                quem=r["d_quem"],
                quando=datetime.fromisoformat(r["d_quando"]),
            )
        resultado.append(
            AlertaSalvo(
                registro_id=r["registro_id"],
                tipo=r["tipo"],
                confianca=r["confianca"],
                clausula=r["clausula"],
                trecho_contrato=r["trecho_contrato"],
                trecho_evidencia=r["trecho_evidencia"],
                justificativa=r["justificativa"],
                responsavel=r["responsavel"],
                acao=r["acao"],
                status=r["status"],
                trace_url=r["trace_url"],
                slack_canal=r["slack_canal"],
                slack_ts=r["slack_ts"],
                criado_em=r["criado_em"],
                decisao=decisao,
            )
        )
    return resultado


def registrar_decisao(decisao: Decisao, *, caminho: str | Path | None = None) -> bool:
    """Um clique, uma decisão. True se gravou; False se o alerta já tinha decisão.

    Só a primeira decisão altera `alertas.status`.
    """
    with _sessao(caminho) as con:
        cur = con.execute(
            "INSERT OR IGNORE INTO decisoes (alerta_id, acao, quem, quando) VALUES (?, ?, ?, ?)",
            (decisao.alerta_id, decisao.acao, decisao.quem, _iso(decisao.quando)),
        )
        if cur.rowcount == 0:
            return False
        con.execute(
            "UPDATE alertas SET status = ? WHERE registro_id = ?",
            (_STATUS_POR_ACAO[decisao.acao], decisao.alerta_id),
        )
        return True


# --- documentos do terceiro ------------------------------------------------------------


def salvar_documentos(
    documentos: list[DocumentoExtraido], *, caminho: str | Path | None = None
) -> None:
    """Um documento por arquivo: regravar o mesmo arquivo atualiza a linha."""
    with _sessao(caminho) as con:
        con.executemany(
            "INSERT INTO documentos (tipo, pessoa, empresa, validade, arquivo) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(arquivo) DO UPDATE SET tipo=excluded.tipo, pessoa=excluded.pessoa, "
            "empresa=excluded.empresa, validade=excluded.validade",
            [(d.tipo, d.pessoa, d.empresa, _iso(d.validade), d.arquivo) for d in documentos],
        )


def listar_documentos(*, caminho: str | Path | None = None) -> list[DocumentoExtraido]:
    with _sessao(caminho) as con:
        linhas = con.execute("SELECT * FROM documentos ORDER BY id").fetchall()
    return [
        DocumentoExtraido(
            tipo=r["tipo"],
            pessoa=r["pessoa"],
            empresa=r["empresa"],
            validade=date.fromisoformat(r["validade"]) if r["validade"] else None,
            arquivo=r["arquivo"],
        )
        for r in linhas
    ]


# --- cache do modelo e eval ------------------------------------------------------------


def cache_get(chave: str, *, caminho: str | Path | None = None) -> str | None:
    with _sessao(caminho) as con:
        r = con.execute("SELECT resposta FROM llm_cache WHERE chave = ?", (chave,)).fetchone()
    return r["resposta"] if r else None


def cache_set(chave: str, resposta: str, *, caminho: str | Path | None = None) -> None:
    with _sessao(caminho) as con:
        con.execute(
            "INSERT OR REPLACE INTO llm_cache (chave, resposta) VALUES (?, ?)", (chave, resposta)
        )


def salvar_eval(versao: str, metricas: dict, *, caminho: str | Path | None = None) -> int:
    """Guarda uma execução do eval e devolve o id dela."""
    with _sessao(caminho) as con:
        cur = con.execute(
            "INSERT INTO eval_execucoes (versao, metricas) VALUES (?, ?)",
            (versao, json.dumps(metricas, ensure_ascii=False, default=str)),
        )
        return cur.lastrowid
