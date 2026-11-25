"""Pausa de aprovação humana: processar para, retomar continua e grava UMA decisão (sem rede)."""

from datetime import UTC, datetime

import pytest

from radar import config, db, grafo
from radar.core.models import Alerta, Decisao, Origem, Registro, TipoDesvio
from radar.nos.rotear import notificador_padrao

TEXTO_DESVIO = "Pode incluir o módulo de relatórios sem custo?"


@pytest.fixture(autouse=True)
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "t.db")
    monkeypatch.setattr(config, "DATABASE_PATH", caminho)
    return caminho


@pytest.fixture
def avisos():
    chamadas: list[tuple[Alerta, Registro]] = []
    grafo.configurar(lambda alerta, registro: chamadas.append((alerta, registro)))
    yield chamadas
    grafo.configurar(notificador_padrao)


def _registro(id_: str, texto: str = TEXTO_DESVIO) -> Registro:
    return Registro(
        id=id_,
        origem=Origem.slack,
        data=datetime(2027, 1, 19, tzinfo=UTC),
        autor="cliente",
        texto=texto,
    )


def _decisao(id_: str, acao: str = "aprovar") -> Decisao:
    return Decisao(alerta_id=id_, acao=acao, quem="teste", quando=datetime.now(UTC))


def _decisoes(caminho: str) -> list:
    db.init_db(caminho)  # o banco só existe depois de um alerta gravado
    con = db.conectar(caminho)
    try:
        return con.execute("SELECT alerta_id, acao FROM decisoes").fetchall()
    finally:
        con.close()


def test_processar_para_no_aprovar_com_alerta_pendente(avisos, banco):
    resultado = grafo.processar(_registro("a:pausa"))

    assert "__interrupt__" in resultado
    assert resultado["__interrupt__"][0].value["alerta"]["registro_id"] == "a:pausa"
    assert len(avisos) == 1
    alertas = db.listar_alertas(caminho=banco)
    assert [(a.registro_id, a.status) for a in alertas] == [("a:pausa", "pendente")]
    assert alertas[0].tipo is TipoDesvio.escopo_extra
    assert _decisoes(banco) == []  # nada registrado sem decisão humana


def test_retomar_aprova_e_grava_uma_decisao(avisos, banco):
    grafo.processar(_registro("a:aprova"))

    resultado = grafo.retomar("a:aprova", _decisao("a:aprova"))

    assert resultado is not None
    assert resultado["decisao"].acao == "aprovar"
    assert [tuple(r) for r in _decisoes(banco)] == [("a:aprova", "aprovar")]
    assert db.listar_alertas(caminho=banco)[0].status == "aprovado"
    assert len(avisos) == 1  # a retomada não avisa de novo


def test_segundo_retomar_devolve_none_e_nao_grava_de_novo(avisos, banco):
    grafo.processar(_registro("a:duplo"))
    assert grafo.retomar("a:duplo", _decisao("a:duplo")) is not None

    assert grafo.retomar("a:duplo", _decisao("a:duplo", "descartar")) is None
    assert len(_decisoes(banco)) == 1
    alerta = db.listar_alertas(caminho=banco)[0]
    assert alerta.status == "aprovado"  # o segundo clique não muda nada
    assert alerta.decisao.acao == "aprovar"


@pytest.mark.parametrize(
    ("acao", "status"), [("nao_e_desvio", "nao_e_desvio"), ("descartar", "descartado")]
)
def test_outras_decisoes(avisos, banco, acao, status):
    id_ = f"a:{acao}"
    grafo.processar(_registro(id_))

    assert grafo.retomar(id_, _decisao(id_, acao)) is not None
    assert [tuple(r) for r in _decisoes(banco)] == [(id_, acao)]
    assert db.listar_alertas(caminho=banco)[0].status == status


def test_retomar_sem_ter_pausado_devolve_none(avisos, banco):
    assert grafo.retomar("a:nunca", _decisao("a:nunca")) is None
    assert _decisoes(banco) == []


def test_dois_registros_nao_misturam_estados(avisos, banco):
    grafo.processar(_registro("a:um"))
    grafo.processar(_registro("a:dois", "O módulo de relatórios entra no escopo?"))

    grafo.retomar("a:um", _decisao("a:um", "aprovar"))

    por_id = {a.registro_id: a for a in db.listar_alertas(caminho=banco)}
    assert por_id["a:um"].status == "aprovado"
    assert por_id["a:dois"].status == "pendente"
    assert por_id["a:dois"].decisao is None
    # o segundo ainda está pausado e pode ser decidido
    assert grafo.retomar("a:dois", _decisao("a:dois", "descartar")) is not None
    assert {tuple(r) for r in _decisoes(banco)} == {("a:um", "aprovar"), ("a:dois", "descartar")}


def test_confianca_media_vira_resumo_sem_pausar(avisos, banco, monkeypatch):
    # Com confiança entre os dois limiares a ação é `resumo`: grava `em_resumo` e não pausa.
    monkeypatch.setattr(config, "LIMIAR_POSTAR", 0.95)
    monkeypatch.setattr(config, "LIMIAR_RESUMO", 0.5)
    resultado = grafo.processar(_registro("a:resumo"))

    assert "__interrupt__" not in resultado
    assert resultado["acao"] == "resumo"
    assert avisos == []
    alertas = db.listar_alertas(caminho=banco)
    assert [(a.registro_id, a.status) for a in alertas] == [("a:resumo", "em_resumo")]
    assert grafo.retomar("a:resumo", _decisao("a:resumo")) is None
    assert _decisoes(banco) == []


def test_registro_sem_desvio_nao_grava_nada(avisos, banco):
    resultado = grafo.processar(_registro("a:ok", "Bom dia, tudo certo."))

    assert "__interrupt__" not in resultado
    assert avisos == []
    db.init_db(banco)  # o fluxo nem chegou a criar o banco
    assert db.listar_alertas(caminho=banco) == []
    assert _decisoes(banco) == []
