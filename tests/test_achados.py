import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from radar.achados.demo import ACHADOS
from radar.achados.models import AchadoNovo, Categoria, DecisaoPedido, Status
from radar.achados.store import AchadoStore
from radar.api.app import app
from radar.api.deps import get_store
from radar.core.errors import Conflito, NaoEncontrado


@pytest.fixture
def store(tmp_path) -> AchadoStore:
    store = AchadoStore(tmp_path / "radar.db")
    for achado in ACHADOS:
        store.adicionar("Projeto demo", achado)
    return store


@pytest.fixture
def client(store):
    app.dependency_overrides[get_store] = lambda: store
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_desvio_sem_trecho_do_contrato_e_recusado() -> None:
    dados = ACHADOS[1].model_dump()
    dados["combinado"] = None
    with pytest.raises(ValidationError, match="combinado"):
        AchadoNovo(**dados)


def test_lista_em_ordem_de_gravidade(store) -> None:
    gravidades = [a.gravidade for a in store.listar()]
    ordem = {"critico": 0, "atencao": 1, "observacao": 2}
    assert gravidades == sorted(gravidades, key=ordem.__getitem__)
    assert {a.categoria for a in store.listar(categoria=Categoria.problema)} == {Categoria.problema}


def test_decisao_unica_e_com_historico(store) -> None:
    pedido = DecisaoPedido(decisao="nao_e_desvio", decidido_por="Ana", comentario="já tem CR")
    achado = store.decidir(1, pedido)
    assert achado.status is Status.nao_e_desvio
    assert achado.decidido_por == "Ana"
    assert achado.decidido_em is not None
    with pytest.raises(Conflito):
        store.decidir(1, DecisaoPedido(decisao="aprovado", decidido_por="Outra"))
    with pytest.raises(NaoEncontrado):
        store.obter(999)
    assert [a.id for a in store.listar(status=Status.pendente)] != []
    assert 1 not in [a.id for a in store.listar(status=Status.pendente)]


def test_rotas_de_achados(client) -> None:
    lista = client.get("/achados", params={"status": "pendente"})
    assert lista.status_code == 200
    assert len(lista.json()) == len(ACHADOS)

    corpo = {"decisao": "aprovado", "decidido_por": "Gestor"}
    ok = client.post("/achados/2/decisao", json=corpo)
    assert ok.status_code == 200
    assert ok.json()["status"] == "aprovado"
    assert client.post("/achados/2/decisao", json=corpo).status_code == 409
    assert client.post("/achados/999/decisao", json=corpo).status_code == 404
    assert client.post("/achados/3/decisao", json={"decisao": "talvez"}).status_code == 422


def test_desfazer_volta_para_pendente(store) -> None:
    store.decidir(1, DecisaoPedido(decisao="aprovado", decidido_por="Ana"))
    achado = store.desfazer(1, por="Ana")
    assert achado.status is Status.pendente
    assert achado.decidido_por is None
    with pytest.raises(Conflito):
        store.desfazer(1, por="Ana")


def test_rotas_de_projeto_analise_e_desfazer(client, store) -> None:
    from datetime import UTC, datetime

    from radar.achados.config import AchadosSettings
    from radar.achados.models import Analise
    from radar.api.deps import get_projeto_store, get_registry, get_settings
    from radar.fontes.registry import FonteRegistry
    from radar.projeto.store import ProjetoStore

    settings = AchadosSettings(_env_file=None, projeto="Projeto demo", gestor="Paulo Lima")
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_registry] = lambda: FonteRegistry({})
    app.dependency_overrides[get_projeto_store] = lambda: ProjetoStore(
        store._path, store._path.parent / "arquivos"
    )
    assert client.get("/analises/ultima").status_code == 404
    store.registrar_analise(
        Analise(projeto="Projeto demo", executada_em=datetime.now(UTC), duracao_s=38, resumo="ok")
    )
    assert client.get("/analises/ultima").json()["duracao_s"] == 38

    projeto = client.get("/projeto").json()
    assert projeto["pessoas"]["gestor"] == "Paulo Lima"
    assert projeto["valor_hora"] == 200

    client.post("/achados/1/decisao", json={"decisao": "aprovado", "decidido_por": "Paulo"})
    desfeito = client.delete("/achados/1/decisao", params={"por": "Paulo"})
    assert desfeito.json()["status"] == "pendente"
    assert client.delete("/achados/1/decisao", params={"por": "Paulo"}).status_code == 409
