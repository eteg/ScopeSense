"""Banco SQLite local (radar/db.py), sempre com um banco temporário."""

import json
import threading
from datetime import UTC, date, datetime

import pytest

from radar import db
from radar.core.models import (
    Acao,
    Alerta,
    Decisao,
    DocumentoExtraido,
    Obrigacao,
    Origem,
    Papel,
    Registro,
    TipoDesvio,
)

TABELAS = {
    "registros",
    "obrigacoes",
    "alertas",
    "decisoes",
    "documentos",
    "llm_cache",
    "eval_execucoes",
}


@pytest.fixture
def banco(tmp_path):
    caminho = tmp_path / "pasta" / "radar.db"
    db.init_db(caminho)
    return caminho


def alerta(registro_id="r1", responsavel=Papel.gestor, tipo=TipoDesvio.escopo_extra) -> Alerta:
    return Alerta(
        tipo=tipo,
        confianca=0.9,
        clausula="2.2",
        trecho_contrato="Fora do escopo",
        trecho_evidencia="a gente faz",
        justificativa="Possível desvio.",
        registro_id=registro_id,
        responsavel=responsavel,
    )


def decisao(alerta_id="r1", acao="aprovar", quem="ana") -> Decisao:
    return Decisao(
        alerta_id=alerta_id, acao=acao, quem=quem, quando=datetime(2026, 11, 25, 12, tzinfo=UTC)
    )


def test_init_db_duas_vezes_cria_as_7_tabelas(tmp_path):
    caminho = tmp_path / "novo" / "radar.db"
    db.init_db(caminho)
    db.init_db(caminho)
    con = db.conectar(caminho)
    try:
        linhas = con.execute("SELECT name FROM sqlite_master WHERE type='table'")
        nomes = {r["name"] for r in linhas}
        assert TABELAS <= nomes
        assert con.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    finally:
        con.close()


def test_conectar_usa_database_path_da_config(tmp_path, monkeypatch):
    caminho = tmp_path / "cfg" / "radar.db"
    monkeypatch.setattr(db.config, "DATABASE_PATH", str(caminho))
    db.init_db()
    assert caminho.exists()


def test_salvar_registro_guarda_canal_e_thread(banco):
    registro = Registro(
        id="r1",
        origem=Origem.slack,
        data=datetime(2026, 11, 25, 9, 30),  # sem fuso: ganha America/Sao_Paulo
        autor="cliente",
        texto="Podem incluir o treinamento?",
        metadados={"canal": "C1", "thread_id": "1700000000.000100"},
    )
    db.salvar_registro(registro, caminho=banco)
    db.salvar_registro(registro, caminho=banco)  # idempotente
    con = db.conectar(banco)
    try:
        linhas = con.execute("SELECT * FROM registros").fetchall()
    finally:
        con.close()
    assert len(linhas) == 1
    assert linhas[0]["canal"] == "C1"
    assert linhas[0]["thread_id"] == "1700000000.000100"
    assert linhas[0]["data"] == "2026-11-25T09:30:00-03:00"
    assert json.loads(linhas[0]["metadados"]) == registro.metadados
    lido = db.obter_registro("r1", caminho=banco)
    assert lido.canal == "C1" and lido.origem == Origem.slack
    assert db.obter_registro("nao-existe", caminho=banco) is None


def test_salvar_e_listar_alerta_com_filtros(banco):
    db.salvar_alerta(alerta("r1", Papel.gestor), Acao.postar, caminho=banco)
    db.salvar_alerta(
        alerta("r2", Papel.comercial, TipoDesvio.prazo_sla), "resumo", "em_resumo", caminho=banco
    )
    db.salvar_alerta(alerta("r3", Papel.gestor), Acao.postar, trace_url="http://t/3", caminho=banco)
    db.atualizar_slack_msg("r1", "C1", "1700000000.000200", caminho=banco)

    todos = db.listar_alertas(caminho=banco)
    assert [a.registro_id for a in todos] == ["r1", "r2", "r3"]
    primeiro = todos[0]
    assert primeiro.tipo == TipoDesvio.escopo_extra
    assert primeiro.responsavel == Papel.gestor
    assert primeiro.acao == Acao.postar
    assert primeiro.status == "pendente"
    assert (primeiro.slack_canal, primeiro.slack_ts) == ("C1", "1700000000.000200")
    assert primeiro.decisao is None
    assert todos[2].trace_url == "http://t/3"

    assert [a.registro_id for a in db.listar_alertas(papel=Papel.gestor, caminho=banco)] == [
        "r1",
        "r3",
    ]
    assert [a.registro_id for a in db.listar_alertas(papel="comercial", caminho=banco)] == ["r2"]
    assert [a.registro_id for a in db.listar_alertas(status="em_resumo", caminho=banco)] == ["r2"]
    assert db.listar_alertas(papel=Papel.comercial, status="pendente", caminho=banco) == []


def test_registrar_decisao_true_depois_false_e_so_a_primeira_altera_status(banco):
    db.salvar_alerta(alerta("r1"), Acao.postar, caminho=banco)

    assert db.registrar_decisao(decisao("r1", "aprovar", "ana"), caminho=banco) is True
    assert db.listar_alertas(caminho=banco)[0].status == "aprovado"

    assert db.registrar_decisao(decisao("r1", "descartar", "bia"), caminho=banco) is False
    salvo = db.listar_alertas(caminho=banco)[0]
    assert salvo.status == "aprovado"
    assert salvo.decisao.acao == "aprovar" and salvo.decisao.quem == "ana"
    assert salvo.decisao.quando == datetime(2026, 11, 25, 12, tzinfo=UTC)

    con = db.conectar(banco)
    try:
        assert con.execute("SELECT COUNT(*) FROM decisoes").fetchone()[0] == 1
    finally:
        con.close()


@pytest.mark.parametrize(
    ("acao", "status"),
    [("aprovar", "aprovado"), ("descartar", "descartado"), ("nao_e_desvio", "nao_e_desvio")],
)
def test_status_por_acao(banco, acao, status):
    db.salvar_alerta(alerta("r1"), Acao.postar, caminho=banco)
    assert db.registrar_decisao(decisao("r1", acao), caminho=banco)
    assert db.listar_alertas(status=status, caminho=banco)[0].registro_id == "r1"


def test_duas_conexoes_gravando_ao_mesmo_tempo(banco):
    erros = []
    inicio = threading.Barrier(2)

    def gravar(prefixo):
        try:
            inicio.wait()
            for i in range(40):
                db.salvar_alerta(alerta(f"{prefixo}{i}"), Acao.postar, caminho=banco)
                db.cache_set(f"{prefixo}{i}", "x", caminho=banco)
        except Exception as e:  # noqa: BLE001
            erros.append(e)

    threads = [threading.Thread(target=gravar, args=(p,)) for p in ("a", "b")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert erros == []
    assert len(db.listar_alertas(caminho=banco)) == 80


def test_cache_get_e_set(banco):
    assert db.cache_get("k", caminho=banco) is None
    db.cache_set("k", '{"a": 1}', caminho=banco)
    assert db.cache_get("k", caminho=banco) == '{"a": 1}'
    db.cache_set("k", "novo", caminho=banco)
    assert db.cache_get("k", caminho=banco) == "novo"


def test_obrigacoes(banco):
    lista = [
        Obrigacao(clausula="2.2", texto="Fora do escopo", tipo="escopo"),
        Obrigacao(
            clausula="3.1", texto="Entrega em 30 dias", tipo="prazo", prazo=date(2026, 12, 3)
        ),
        Obrigacao(clausula="4.1", texto="ASO válido", tipo="terceiro", documento_exigido="aso"),
    ]
    db.salvar_obrigacoes(lista, caminho=banco)
    db.salvar_obrigacoes(lista, caminho=banco)  # idempotente
    assert db.listar_obrigacoes(caminho=banco) == lista


def test_documentos(banco):
    docs = [
        DocumentoExtraido(
            tipo="aso",
            pessoa="Fulano",
            empresa="Terceira",
            validade=date(2027, 1, 31),
            arquivo="a.pdf",
        ),
        DocumentoExtraido(tipo="nda", arquivo="b.pdf"),
    ]
    db.salvar_documentos(docs, caminho=banco)
    assert db.listar_documentos(caminho=banco) == docs

    atualizado = docs[0].model_copy(update={"validade": date(2028, 2, 1)})
    db.salvar_documentos([atualizado], caminho=banco)  # mesmo arquivo: atualiza
    lidos = db.listar_documentos(caminho=banco)
    assert len(lidos) == 2
    assert lidos[0].validade == date(2028, 2, 1)


def test_salvar_eval(banco):
    metricas = {"precisao": 0.9, "recall": 0.8, "obs": "ação"}
    id_ = db.salvar_eval("v1", metricas, caminho=banco)
    con = db.conectar(banco)
    try:
        linha = con.execute("SELECT * FROM eval_execucoes WHERE id = ?", (id_,)).fetchone()
    finally:
        con.close()
    assert linha["versao"] == "v1"
    assert json.loads(linha["metricas"]) == metricas
    assert linha["criado_em"]
