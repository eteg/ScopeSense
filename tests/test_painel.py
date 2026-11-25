"""Fila da tela web: alertas do pipeline, decisão, desfazer e o demo do gabarito."""

import pytest
from fastapi.testclient import TestClient

from radar import config, db, painel
from radar.api.app import app
from radar.core.models import Acao, Alerta, Origem, Registro, TipoDesvio
from radar.demo import popular
from radar.roteamento import rotear_alerta


@pytest.fixture
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "radar.db")
    monkeypatch.setattr(config, "DATABASE_PATH", caminho)
    db.init_db(caminho)
    return caminho


def _alerta(banco, registro_id: str, tipo: TipoDesvio, confianca: float = 0.9, registro=True):
    alerta, acao = rotear_alerta(
        Alerta(
            registro_id=registro_id,
            tipo=tipo,
            confianca=confianca,
            clausula="2.2",
            trecho_contrato="Relatórios estão fora do escopo.",
            trecho_evidencia="a gente faz o relatório",
            justificativa="Pedido fora do escopo aceito.",
        )
    )
    db.salvar_alerta(alerta, acao, "pendente" if acao == Acao.postar else "em_resumo", caminho=banco)
    if registro:
        db.salvar_registro(
            Registro(
                id=registro_id,
                origem=Origem.slack,
                data="2026-11-25T14:32:00-03:00",
                autor="Marcos Lima",
                texto="a gente faz o relatório",
                metadados={"canal": "projeto-alfa-cliente"},
            ),
            caminho=banco,
        )


def test_lista_ordena_por_gravidade_e_esconde_descartados(banco) -> None:
    _alerta(banco, "slack:prazo", TipoDesvio.prazo_sla)
    _alerta(banco, "slack:escopo", TipoDesvio.escopo_extra, registro=False)
    _alerta(banco, "slack:fraco", TipoDesvio.escopo_extra, confianca=0.3)  # descartado
    alertas = painel.listar(caminho=banco)
    assert [a.id for a in alertas] == ["slack:escopo", "slack:prazo"]
    assert alertas[0].gravidade == painel.Gravidade.critico
    assert alertas[0].evidencia is None  # registro de origem não guardado
    assert alertas[1].evidencia.autor == "Marcos Lima"
    assert alertas[1].responsavel == "comercial"
    assert alertas[1].titulo == "Possível desvio de prazo"


def test_rotas_decidir_conflito_e_desfazer(banco) -> None:
    _alerta(banco, "slack:escopo", TipoDesvio.escopo_extra)
    client = TestClient(app)

    lista = client.get("/alertas").json()
    assert [a["id"] for a in lista] == ["slack:escopo"]
    assert client.get("/alertas/resumo").json()["registros_lidos"] == {"slack": 1}

    corpo = {"acao": "nao_e_desvio", "quem": "Helena"}
    decidido = client.post("/alertas/slack:escopo/decisao", json=corpo)
    assert decidido.status_code == 200
    assert decidido.json()["status"] == "nao_e_desvio"
    assert decidido.json()["decisao"]["quem"] == "Helena"
    assert client.post("/alertas/slack:escopo/decisao", json=corpo).status_code == 409
    assert client.post("/alertas/nao:existe/decisao", json=corpo).status_code == 404

    desfeito = client.delete("/alertas/slack:escopo/decisao", params={"quem": "Helena"})
    assert desfeito.json()["status"] == "pendente"
    assert desfeito.json()["decisao"] is None
    assert client.delete("/alertas/slack:escopo/decisao", params={"quem": "x"}).status_code == 409


def test_demo_cria_os_4_desvios_do_gabarito(banco) -> None:
    assert popular("data", caminho=banco) == 4
    alertas = painel.listar(caminho=banco)
    por_tipo = {a.tipo: a for a in alertas}
    assert set(por_tipo) == {
        TipoDesvio.escopo_extra,
        TipoDesvio.prazo_sla,
        TipoDesvio.terceiro_sem_documento,
        TipoDesvio.promessa_fora_do_contrato,
    }
    assert por_tipo[TipoDesvio.terceiro_sem_documento].responsavel == "administrativo_contratos"
    assert all(a.evidencia is not None for a in alertas)
    assert all(a.justificativa.startswith("[gabarito]") for a in alertas)
    assert popular("data", caminho=banco) == 4  # idempotente
    assert len(painel.listar(caminho=banco)) == 4
