import pytest
from fastapi.testclient import TestClient

from radar.achados.config import AchadosSettings
from radar.achados.models import Papel
from radar.api.app import app
from radar.api.deps import get_projeto_store, get_registry, get_settings
from radar.core.errors import EntradaInvalida
from radar.core.models import Origem
from radar.fontes.registry import FonteRegistry
from radar.projeto.models import CanalSlack, ConfigPedido, Pessoa, ProjetoConfig
from radar.projeto.service import aplicar_pedido
from radar.projeto.store import ProjetoStore, tipo_pelo_nome
from tests.conftest import CANAL

PDF = b"%PDF-1.4\n%fake\n"

CANAIS = {
    "channels": [
        {"id": "C222222222", "name": "alfa-projeto"},
        {"id": "C333333333", "name": "alfa-contratos"},
    ],
    "response_metadata": {"next_cursor": ""},
}


@pytest.fixture
def pstore(tmp_path) -> ProjetoStore:
    return ProjetoStore(tmp_path / "radar.db", tmp_path / "arquivos")


# --- regras -----------------------------------------------------------------------


def test_salvar_sem_canal_novo_nao_consulta_o_slack() -> None:
    atual = ProjetoConfig(canais_slack=[CanalSlack(id="C0DEMO00001", nome="alfa-projeto")])
    pedido = ConfigPedido(
        canais_slack=["#Alfa-Projeto", "C0DEMO00001"],
        pessoas=[Pessoa(nome="Ana", papel=Papel.gestor)],
    )

    def sem_slack():
        raise AssertionError("não deveria consultar o Slack")

    nova = aplicar_pedido(atual, pedido, sem_slack)
    assert [c.id for c in nova.canais_slack] == ["C0DEMO00001"]
    assert nova.pessoas[0].nome == "Ana"


def test_canal_novo_e_resolvido_no_slack() -> None:
    pedido = ConfigPedido(canais_slack=["#novo"])
    nova = aplicar_pedido(
        ProjetoConfig(), pedido, lambda: lambda refs: [{"id": "C9", "nome": "novo"}]
    )
    assert nova.canais_slack == [CanalSlack(id="C9", nome="novo")]


def test_slack_resolve_por_nome_e_recusa_o_que_nao_existe(make_slack) -> None:
    slack, fake = make_slack(**{"conversations.list": CANAIS})
    assert slack.resolver_canais(["#alfa-projeto"]) == [
        {"id": "C222222222", "nome": "alfa-projeto"}
    ]
    with pytest.raises(EntradaInvalida, match="#nao-existe"):
        slack.resolver_canais(["#nao-existe"])


# --- arquivos ---------------------------------------------------------------------


@pytest.mark.parametrize(
    ("nome", "tipo"),
    [
        ("contrato_projeto_alfa.pdf", "Contrato"),
        ("ASO_Joao_Pereira.pdf", "Terceiro"),
        ("Ata reunião 23-11.pdf", "Reunião"),
        ("cronograma.pdf", "Documento"),
    ],
)
def test_tipo_pelo_nome(nome: str, tipo: str) -> None:
    assert tipo_pelo_nome(nome) == tipo


def test_arquivo_so_pdf_e_sem_caminho(pstore, tmp_path) -> None:
    arquivo = pstore.adicionar_arquivo("P", "../../contrato.pdf", PDF)
    assert arquivo.nome == "contrato.pdf"
    assert (tmp_path / "arquivos" / f"{arquivo.id}.pdf").read_bytes() == PDF
    with pytest.raises(EntradaInvalida):
        pstore.adicionar_arquivo("P", "planilha.pdf", b"PK\x03\x04")
    pstore.remover_arquivo("P", arquivo.id)
    assert pstore.arquivos("P") == []
    assert not (tmp_path / "arquivos" / f"{arquivo.id}.pdf").exists()


# --- API ------------------------------------------------------------------------


@pytest.fixture
def api(make_slack, pstore):
    slack, fake = make_slack(**{"conversations.list": CANAIS})
    settings = AchadosSettings(_env_file=None, projeto="Projeto Alfa", gestor="Paulo Lima")
    registry = FonteRegistry({Origem.slack: lambda: slack})
    app.dependency_overrides.update(
        {
            get_settings: lambda: settings,
            get_projeto_store: lambda: pstore,
            get_registry: lambda: registry,
        }
    )
    try:
        yield TestClient(app), slack
    finally:
        app.dependency_overrides.clear()


def test_rotas_da_configuracao(api) -> None:
    client, slack = api

    inicial = client.get("/projeto").json()  # antes de salvar: vem do .env
    assert inicial["pessoas"]["gestor"] == "Paulo Lima"
    assert [c["id"] for c in inicial["canais_slack"]] == [CANAL]

    corpo = {
        "canais_slack": ["#alfa-projeto", "#alfa-contratos"],
        "pessoas": [
            {"nome": "Carla Melo", "papel": "comercial"},
            {"nome": "  ", "papel": "gestor"},  # linha vazia é ignorada
        ],
    }
    salvo = client.put("/projeto/config", json=corpo)
    assert salvo.status_code == 200
    assert salvo.json()["canal_slack"] == "#alfa-projeto"
    assert salvo.json()["pessoas"] == {
        "gestor": None, "comercial": "Carla Melo", "adm_contratos": None
    }  # fmt: skip
    assert slack._allowed == {"C222222222", "C333333333"}  # a leitura segue a tela

    ruim = client.put("/projeto/config", json={"canais_slack": ["#nao-existe"]})
    assert ruim.status_code == 422
    assert "#nao-existe" in ruim.json()["detail"]

    assert client.get("/projeto/slack").json()["conectado"] is True


def test_rotas_de_arquivos(api) -> None:
    client, _ = api
    enviado = client.post("/projeto/arquivos", params={"nome": "contrato_alfa.pdf"}, content=PDF)
    assert enviado.status_code == 201
    assert enviado.json()["tipo"] == "Contrato"
    assert [a["nome"] for a in client.get("/projeto/arquivos").json()] == ["contrato_alfa.pdf"]
    nao_pdf = client.post("/projeto/arquivos", params={"nome": "x.pdf"}, content=b"oi")
    assert nao_pdf.status_code == 422
    assert client.delete(f"/projeto/arquivos/{enviado.json()['id']}").status_code == 204
    assert client.delete("/projeto/arquivos/naoexiste").status_code == 404
