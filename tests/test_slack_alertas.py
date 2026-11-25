"""G-07: Block Kit do alerta, envio ao grupo e atualização depois da decisão (sem rede)."""

import json
from datetime import UTC, datetime

import pytest

from radar import config, db
from radar.core.models import Acao, Alerta, Decisao, Origem, Papel, Registro, TipoDesvio
from radar.slack_alertas import (
    atualizar_apos_decisao,
    enviar_alerta,
    montar_blocos,
    texto_fallback,
    titulo_do_alerta,
    usuario_do_papel,
)
from radar.ui import textos


class ClienteFalso:
    """Registra as chamadas de escrita do Slack."""

    def __init__(self):
        self.postadas: list[dict] = []
        self.atualizadas: list[dict] = []

    def chat_postMessage(self, **kwargs):  # noqa: N802
        self.postadas.append(kwargs)
        return {"ok": True, "channel": kwargs["channel"], "ts": "1700000000.000100"}

    def chat_update(self, **kwargs):
        self.atualizadas.append(kwargs)
        return {"ok": True}


def _alerta(tipo=TipoDesvio.escopo_extra, **extra) -> Alerta:
    campos = dict(
        tipo=tipo,
        confianca=0.92,
        clausula="2.2",
        trecho_contrato="Fica fora do escopo qualquer relatório não listado.",
        trecho_evidencia="Pode incluir o módulo de relatórios sem custo?",
        justificativa="Pedido fora do escopo.",
        registro_id="r1",
        responsavel=Papel.gestor,
    )
    campos.update(extra)
    return Alerta(**campos)


def _registro(**extra) -> Registro:
    campos = dict(
        id="r1",
        origem=Origem.slack,
        data=datetime(2027, 1, 19, 15, 30, tzinfo=UTC),
        autor="Marcos Lima",
        texto="Pode incluir o módulo de relatórios sem custo?",
        link="https://teste.slack.com/archives/C1/p1",
    )
    campos.update(extra)
    return Registro(**campos)


@pytest.fixture
def banco(tmp_path, monkeypatch):
    caminho = str(tmp_path / "t.db")
    monkeypatch.setattr(config, "DATABASE_PATH", caminho)
    db.init_db(caminho)
    return caminho


def _por_tipo(blocos, tipo):
    return [b for b in blocos if b["type"] == tipo]


def test_blocos_tem_header_neutro_e_sem_o_autor():
    blocos = montar_blocos(_alerta(), _registro())
    header = _por_tipo(blocos, "header")[0]["text"]["text"]
    assert textos.TITULO_DESVIO["escopo"] in header
    assert "Marcos" not in header
    assert "Possível" in header


@pytest.mark.parametrize(
    "tipo,chave",
    [
        (TipoDesvio.escopo_extra, "escopo"),
        (TipoDesvio.prazo_sla, "prazo"),
        (TipoDesvio.terceiro_sem_documento, "documento"),
        (TipoDesvio.promessa_fora_do_contrato, "promessa"),
    ],
)
def test_titulo_por_tipo(tipo, chave):
    assert titulo_do_alerta(_alerta(tipo=tipo)) == textos.TITULO_DESVIO[chave]


def test_section_com_duas_citacoes_lado_a_lado():
    section = _por_tipo(montar_blocos(_alerta(), _registro()), "section")[0]
    esquerda, direita = (f["text"] for f in section["fields"])
    assert esquerda.startswith("*Cláusula 2.2*")
    assert "Fica fora do escopo" in esquerda
    assert direita.startswith("*Evidência (Marcos Lima, ")
    assert "módulo de relatórios" in direita


def test_trechos_longos_sao_cortados_em_300():
    longo = "x" * 1000
    alerta = _alerta(trecho_contrato=longo, trecho_evidencia=longo)
    section = _por_tipo(montar_blocos(alerta, _registro()), "section")[0]
    for campo in section["fields"]:
        corpo = campo["text"].split("\n", 1)[1]
        assert len(corpo) <= 300
        assert corpo.endswith("…")


def test_contexto_com_confianca_origem_e_link_so_se_http():
    contexto = _por_tipo(montar_blocos(_alerta(), _registro()), "context")[0]
    itens = [e["text"] for e in contexto["elements"]]
    assert "Confiança: 92%" in itens
    assert "Origem: Slack" in itens
    assert any("https://teste.slack.com/archives/C1/p1" in i for i in itens)

    sem_link = _registro(link="slack://projeto-alfa/1768827600.000100")
    contexto = _por_tipo(montar_blocos(_alerta(), sem_link), "context")[0]
    itens = [e["text"] for e in contexto["elements"]]
    assert not any("slack://" in i for i in itens)
    assert len(itens) == 2


def test_tres_botoes_com_action_id_e_value_certos():
    acoes = _por_tipo(montar_blocos(_alerta(), _registro()), "actions")[0]["elements"]
    assert [b["action_id"] for b in acoes] == ["aprovar", "descartar", "nao_e_desvio"]
    assert all(b["value"] == "r1" for b in acoes)
    assert acoes[0]["style"] == "primary"
    assert "style" not in acoes[1] and "style" not in acoes[2]


def test_texto_fallback_com_e_sem_mencao():
    assert texto_fallback(_alerta()) == "Possível desvio de escopo · cláusula 2.2"
    assert texto_fallback(_alerta(), "U123").startswith("<@U123> · ")


def test_enviar_alerta_posta_no_canal_com_mencao_e_grava_canal_ts(banco):
    alerta = _alerta()
    db.salvar_alerta(alerta, Acao.postar, "pendente", caminho=banco)
    cliente = ClienteFalso()

    saida = enviar_alerta(cliente, alerta, _registro(), "CALERTAS", usuario_id="UGESTOR")

    assert saida == {"canal": "CALERTAS", "ts": "1700000000.000100"}
    postada = cliente.postadas[0]
    assert postada["channel"] == "CALERTAS"
    assert "<@UGESTOR>" in postada["text"]
    primeiro = postada["blocks"][0]
    assert primeiro["type"] == "section" and "<@UGESTOR>" in primeiro["text"]["text"]
    salvo = db.listar_alertas(caminho=banco)[0]
    assert (salvo.slack_canal, salvo.slack_ts) == ("CALERTAS", "1700000000.000100")


def test_enviar_alerta_sem_usuario_nao_marca_ninguem(banco):
    alerta = _alerta()
    db.salvar_alerta(alerta, Acao.postar, "pendente", caminho=banco)
    cliente = ClienteFalso()
    enviar_alerta(cliente, alerta, _registro(), "CALERTAS")
    postada = cliente.postadas[0]
    assert "<@" not in postada["text"]
    assert postada["blocks"][0]["type"] == "header"


def _projeto(tmp_path, slack_id):
    caminho = tmp_path / "projeto.json"
    caminho.write_text(
        json.dumps({"papeis": {"gestor": {"nome": "Helena", "slack_id": slack_id}}}),
        encoding="utf-8",
    )
    return caminho


def test_usuario_do_papel(tmp_path):
    assert usuario_do_papel(Papel.gestor, _projeto(tmp_path, "U0REAL")) == "U0REAL"
    assert usuario_do_papel("gestor", _projeto(tmp_path, "U0REAL")) == "U0REAL"
    assert usuario_do_papel(Papel.gestor, _projeto(tmp_path, "U_PENDENTE_GESTOR")) is None
    assert usuario_do_papel(Papel.gestor, _projeto(tmp_path, "")) is None
    assert usuario_do_papel(Papel.comercial, _projeto(tmp_path, "U0REAL")) is None
    assert usuario_do_papel(None) is None
    assert usuario_do_papel(Papel.gestor, tmp_path / "nao_existe.json") is None


@pytest.mark.parametrize(
    "acao,esperado",
    [
        ("aprovar", "Aprovado por Joe às 11:32"),
        ("descartar", "Descartado por Joe às 11:32"),
        ("nao_e_desvio", "Marcado como não é desvio por Joe às 11:32"),
    ],
)
def test_atualizar_troca_botoes_por_linha_de_contexto(acao, esperado):
    cliente = ClienteFalso()
    alerta, registro = _alerta(), _registro()
    originais = montar_blocos(alerta, registro)
    decisao = Decisao(
        alerta_id="r1", acao=acao, quem="Joe", quando=datetime(2027, 1, 19, 14, 32, tzinfo=UTC)
    )

    atualizar_apos_decisao(cliente, "C1", "1.1", alerta, decisao, blocos_originais=originais)

    chamada = cliente.atualizadas[0]
    assert (chamada["channel"], chamada["ts"]) == ("C1", "1.1")
    blocos = chamada["blocks"]
    assert not _por_tipo(blocos, "actions")
    assert _por_tipo(blocos, "header") and _por_tipo(blocos, "section")
    ultimo = blocos[-1]
    assert ultimo["type"] == "context" and esperado in ultimo["elements"][0]["text"]
    assert esperado in chamada["text"]


def test_atualizar_sem_blocos_originais_reconstroi_do_alerta():
    cliente = ClienteFalso()
    decisao = Decisao(
        alerta_id="r1", acao="aprovar", quem="Joe", quando=datetime(2027, 1, 19, 14, 32, tzinfo=UTC)
    )
    atualizar_apos_decisao(cliente, "C1", "1.1", _alerta(), decisao)
    blocos = cliente.atualizadas[0]["blocks"]
    assert _por_tipo(blocos, "header") and not _por_tipo(blocos, "actions")
