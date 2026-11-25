"""Grafo base: percurso com nós de teste, notificador injetado e isolamento por registro."""

from datetime import UTC, datetime

import pytest

from radar import grafo
from radar.core.models import Alerta, Origem, Papel, Registro, TipoDesvio
from radar.nos.rotear import notificador_padrao
from radar.pipeline import analisar


def _registro(id_: str, texto: str) -> Registro:
    return Registro(
        id=id_,
        origem=Origem.slack,
        data=datetime(2027, 1, 19, tzinfo=UTC),
        autor="cliente",
        texto=texto,
    )


@pytest.fixture
def avisos():
    chamadas: list[tuple[Alerta, Registro]] = []
    grafo.configurar(lambda alerta, registro: chamadas.append((alerta, registro)))
    yield chamadas
    grafo.configurar(notificador_padrao)


def test_desvio_percorre_o_grafo_e_notifica(avisos):
    registro = _registro("t:desvio", "Pode incluir o módulo de relatórios sem custo?")
    resultado = grafo.processar(registro)

    assert len(avisos) == 1
    alerta, reg = avisos[0]
    assert reg.id == registro.id
    assert alerta.tipo is TipoDesvio.escopo_extra
    assert alerta.responsavel is Papel.gestor
    assert resultado["acao"] == "postar"
    assert resultado["alerta"].responsavel is Papel.gestor
    assert resultado["clausulas"][0]["numero"] == "2.2"


def test_registro_sem_desvio_termina_sem_notificar(avisos):
    resultado = grafo.processar(_registro("t:ok", "Bom dia, tudo certo com o atendimento."))

    assert avisos == []
    assert resultado["alerta"].tipo is TipoDesvio.nenhum
    assert "acao" not in resultado


def test_analisar_devolve_alerta_com_responsavel_ou_none(avisos):
    alerta = analisar(_registro("t:a1", "Precisamos do módulo de relatórios"))
    assert alerta is not None
    assert alerta.responsavel is Papel.gestor
    assert alerta.registro_id == "t:a1"

    assert analisar(_registro("t:a2", "Bom dia")) is None
    assert avisos == []  # analisar nunca notifica


def test_ids_diferentes_nao_misturam_estados(avisos):
    com = _registro("t:b1", "módulo de relatórios")
    sem = _registro("t:b2", "bom dia")
    grafo.processar(com)
    grafo.processar(sem)

    estado_com = grafo.grafo.get_state({"configurable": {"thread_id": "t:b1"}}).values
    estado_sem = grafo.grafo.get_state({"configurable": {"thread_id": "t:b2"}}).values
    assert estado_com["registro"].id == "t:b1"
    assert estado_com["alerta"].tipo is TipoDesvio.escopo_extra
    assert estado_sem["registro"].id == "t:b2"
    assert estado_sem["alerta"].tipo is TipoDesvio.nenhum
    assert [r.id for _, r in avisos] == ["t:b1"]


def test_grafo_exportado_em_mermaid(tmp_path):
    texto = grafo.grafo.get_graph().draw_mermaid()
    destino = tmp_path / "grafo.mmd"
    destino.write_text(texto, encoding="utf-8")
    for no in ("buscar", "classificar", "conferir_documentos", "rotear", "aprovar", "registrar"):
        assert no in destino.read_text(encoding="utf-8")
