"""Arquitetura: contrato das fontes, registro e tradução de erros na API."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient

from radar.api.app import app
from radar.api.deps import get_registry
from radar.core.errors import EscritaBloqueada, FalhaNaFonte, FonteNaoConfigurada, ForaDoEscopo
from radar.core.models import Consulta, Origem, Registro
from radar.core.ports import Fonte
from radar.fontes.registry import FACTORIES, FonteRegistry


class FonteFalsa:
    """Exemplo mínimo do que um canal novo (ex.: Gmail) precisa implementar."""

    origem = Origem.email

    def __init__(self, erro: Exception | None = None) -> None:
        self.erro = erro

    def status(self) -> dict[str, Any]:
        return {"conta": "gestor@eteg.com.br"}

    def fetch(self, consulta: Consulta) -> list[Registro]:
        if self.erro:
            raise self.erro
        return [
            Registro(
                id="email:1",
                origem=Origem.email,
                data=datetime(2026, 11, 25, tzinfo=UTC),
                autor="cliente@x.com",
                texto="Podem incluir o treinamento?",
            )
        ][: consulta.limite]


def nao_configurada() -> Fonte:
    raise FonteNaoConfigurada("GMAIL_* ausente no .env.")


def test_adaptadores_cumprem_o_contrato(make_slack) -> None:
    slack, _ = make_slack()
    assert isinstance(slack, Fonte)
    assert isinstance(FonteFalsa(), Fonte)
    assert set(FACTORIES) == {Origem.slack, Origem.email}


def test_registro_informa_fontes_configuradas_e_pendentes() -> None:
    registry = FonteRegistry({Origem.email: FonteFalsa, Origem.agenda: nao_configurada})
    status = {item["origem"]: item for item in registry.available()}
    assert status[Origem.email]["configurada"] is True
    assert status[Origem.agenda]["configurada"] is False
    assert "GMAIL_" in status[Origem.agenda]["motivo"]
    assert [f.origem for f in registry.all_configured()] == [Origem.email]


def _client(registry: FonteRegistry) -> TestClient:
    app.dependency_overrides[get_registry] = lambda: registry
    return TestClient(app)


@pytest.fixture(autouse=True)
def _limpa_overrides():
    yield
    app.dependency_overrides.clear()


def test_rota_generica_serve_qualquer_fonte_registrada() -> None:
    client = _client(FonteRegistry({Origem.email: FonteFalsa}))
    response = client.get("/fontes/email/registros", params={"limite": 5})
    assert response.status_code == 200
    assert response.json()[0]["texto"] == "Podem incluir o treinamento?"
    assert client.get("/fontes/email/status").json() == {"conta": "gestor@eteg.com.br"}


@pytest.mark.parametrize(
    ("erro", "status"),
    [
        (ForaDoEscopo("canal"), 403),
        (EscritaBloqueada("chat.postMessage"), 403),
        (FalhaNaFonte("timeout"), 502),
    ],
)
def test_api_traduz_erros_do_nucleo(erro: Exception, status: int) -> None:
    client = _client(FonteRegistry({Origem.email: lambda: FonteFalsa(erro)}))
    response = client.get("/fontes/email/registros")
    assert response.status_code == status
    assert response.json()["erro"] == type(erro).__name__


def test_fonte_nao_configurada_vira_503() -> None:
    client = _client(FonteRegistry({Origem.agenda: nao_configurada}))
    assert client.get("/fontes/agenda/registros").status_code == 503
    assert client.get("/fontes/reuniao/registros").status_code == 503  # não implementada
