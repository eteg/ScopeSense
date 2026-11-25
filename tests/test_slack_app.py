"""G-06/G-08: escuta do canal, deduplicação, botões e `slack_bot.py` (sem rede, sem tokens)."""

from datetime import UTC, datetime

import pytest

import slack_bot
from radar import config, db
from radar.core.models import Acao, Alerta, Papel, TipoDesvio
from radar.slack_alertas import montar_blocos
from radar.slack_app import Estado, handler_botao, handler_mensagem, tratar_clique, tratar_mensagem

CANAL_ID = "C0CANAL"
TS_ATUAL = "1768827600.000100"  # 19/01/2026 em America/Sao_Paulo
TS_ANTES = ["1768827000.000100", "1768827200.000100", "1768827400.000100", "1768827500.000100"]


class ClienteFalso:
    def __init__(self, falhar: set[str] | None = None):
        self.falhar = falhar or set()
        self.chamadas: list[tuple[str, dict]] = []
        self.historico: list[dict] = []
        self.respostas_thread: list[dict] = []

    def _registrar(self, nome: str, **kwargs):
        self.chamadas.append((nome, kwargs))
        if nome in self.falhar:
            raise RuntimeError(f"{nome} falhou")

    def chamadas_de(self, nome: str) -> list[dict]:
        return [kw for n, kw in self.chamadas if n == nome]

    def auth_test(self):
        self._registrar("auth_test")
        return {"user_id": "UBOT"}

    def conversations_info(self, **kw):
        self._registrar("conversations_info", **kw)
        return {"channel": {"name": "projeto-alfa"}}

    def users_info(self, **kw):
        self._registrar("users_info", **kw)
        return {"user": {"name": "joe", "real_name": "Joe Teste"}}

    def chat_getPermalink(self, **kw):  # noqa: N802
        self._registrar("chat_getPermalink", **kw)
        return {"permalink": "https://teste.slack.com/archives/C0CANAL/p1768827600000100"}

    def conversations_history(self, **kw):
        self._registrar("conversations_history", **kw)
        return {"messages": self.historico}

    def conversations_replies(self, **kw):
        self._registrar("conversations_replies", **kw)
        return {"messages": self.respostas_thread}

    def chat_update(self, **kw):
        self._registrar("chat_update", **kw)
        return {"ok": True}

    def chat_postEphemeral(self, **kw):  # noqa: N802
        self._registrar("chat_postEphemeral", **kw)
        return {"ok": True}


def _estado(**extra) -> tuple[Estado, list]:
    chamadas: list = []
    estado = Estado(
        processar=lambda registro, contexto: chamadas.append((registro, list(contexto))),
        retomar=extra.pop("retomar", lambda registro_id, decisao: {}),
        agora=lambda: datetime(2027, 1, 19, 14, 32, tzinfo=UTC),
        em_segundo_plano=lambda funcao, *args: funcao(*args),  # síncrono nos testes
        pessoas={"U1": "Marcos Lima"},
        **extra,
    )
    return estado, chamadas


def _evento(**extra) -> dict:
    evento = {
        "type": "message",
        "channel": CANAL_ID,
        "user": "U1",
        "text": "Pode incluir o módulo de relatórios sem custo?",
        "ts": TS_ATUAL,
    }
    evento.update(extra)
    return evento


# --- G-06 -------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"bot_id": "B1"},
        {"subtype": "message_changed"},
        {"subtype": "channel_join"},
        {"user": "UBOT"},
        {"text": ""},
        {"text": "   "},
    ],
)
def test_mensagens_que_nao_devem_ser_processadas(extra):
    estado, chamadas = _estado()
    assert tratar_mensagem(_evento(**extra), ClienteFalso(), estado) is None
    assert chamadas == []


def test_evento_duplicado_so_processa_uma_vez():
    estado, chamadas = _estado()
    cliente = ClienteFalso()
    assert tratar_mensagem(_evento(), cliente, estado) is not None
    assert tratar_mensagem(_evento(), cliente, estado) is None
    assert len(chamadas) == 1


def test_mensagem_valida_vira_registro_e_chama_o_grafo_com_contexto():
    estado, chamadas = _estado()
    cliente = ClienteFalso()
    # histórico em ordem do Slack (mais nova primeiro), com ruído que deve ser ignorado
    cliente.historico = [
        {"ts": TS_ATUAL, "user": "U1", "text": "a própria mensagem"},
        {"ts": TS_ANTES[3], "user": "U1", "text": "quarta"},
        {"ts": TS_ANTES[2], "bot_id": "B1", "text": "de bot"},
        {"ts": TS_ANTES[1], "user": "U1", "text": "segunda"},
        {"ts": TS_ANTES[0], "user": "U1", "text": "primeira"},
    ]

    registro = tratar_mensagem(_evento(), cliente, estado)

    assert len(chamadas) == 1
    processado, contexto = chamadas[0]
    assert processado == registro
    assert registro.autor == "Marcos Lima"
    assert registro.origem == "slack"
    assert registro.canal == "projeto-alfa"  # nome descoberto por conversations_info
    assert registro.link.startswith("https://")  # permalink real
    assert [r.texto for r in contexto] == ["primeira", "segunda", "quarta"]  # só anteriores, 3
    assert all(r.data < registro.data for r in contexto)
    assert cliente.chamadas_de("conversations_history")[0]["limit"] == 4


def test_contexto_de_thread_usa_conversations_replies():
    estado, chamadas = _estado()
    cliente = ClienteFalso()
    cliente.respostas_thread = [
        {"ts": TS_ANTES[0], "user": "U1", "text": "pai"},
        {"ts": TS_ANTES[1], "user": "U1", "text": "resposta 1"},
        {"ts": TS_ATUAL, "user": "U1", "text": "a atual"},
    ]
    tratar_mensagem(_evento(thread_ts=TS_ANTES[0]), cliente, estado)
    assert cliente.chamadas_de("conversations_replies")
    assert not cliente.chamadas_de("conversations_history")
    assert [r.texto for r in chamadas[0][1]] == ["pai", "resposta 1"]


def test_falhas_do_slack_nao_impedem_o_processamento():
    estado, chamadas = _estado()
    cliente = ClienteFalso(
        falhar={"auth_test", "conversations_info", "chat_getPermalink", "conversations_history"}
    )
    registro = tratar_mensagem(_evento(), cliente, estado)
    assert len(chamadas) == 1
    assert registro.canal == CANAL_ID  # caiu no ID
    assert registro.link.startswith("slack://")  # sem permalink, ficou o padrão
    assert chamadas[0][1] == []  # sem contexto


def test_auth_test_e_chamado_uma_vez_e_o_nome_do_canal_fica_em_cache():
    estado, _ = _estado()
    cliente = ClienteFalso()
    tratar_mensagem(_evento(ts="1768827600.000200", text="um"), cliente, estado)
    tratar_mensagem(_evento(ts="1768827600.000300", text="dois"), cliente, estado)
    assert len(cliente.chamadas_de("auth_test")) == 1
    assert len(cliente.chamadas_de("conversations_info")) == 1


def test_erro_no_grafo_nao_derruba_o_bot():
    def quebrado(registro, contexto):
        raise RuntimeError("falha de teste")

    estado, _ = _estado()
    estado.processar = quebrado
    assert tratar_mensagem(_evento(), ClienteFalso(), estado) is not None  # só registra no log


def test_handler_de_mensagem_nao_propaga_erro():
    estado, _ = _estado()
    handler_mensagem(estado)({}, ClienteFalso())  # evento sem canal/ts: ignorado, sem exceção


# --- G-08 -------------------------------------------------------------------------------


def _alerta() -> Alerta:
    return Alerta(
        tipo=TipoDesvio.escopo_extra,
        confianca=0.92,
        clausula="2.2",
        trecho_contrato="Fora do escopo.",
        trecho_evidencia="Pode incluir?",
        justificativa="x",
        registro_id="r1",
        responsavel=Papel.gestor,
    )


def _corpo(acao="aprovar") -> dict:
    from datetime import datetime as dt

    from radar.core.models import Origem, Registro

    registro = Registro(
        id="r1", origem=Origem.slack, data=dt(2027, 1, 19, tzinfo=UTC), autor="Marcos", texto="t"
    )
    return {
        "actions": [{"action_id": acao, "value": "r1"}],
        "user": {"id": "UCLICK", "name": "joe.handle"},
        "channel": {"id": "CALERTAS"},
        "message": {"ts": "1700000000.000100", "blocks": montar_blocos(_alerta(), registro)},
    }


def test_ack_vem_antes_de_qualquer_outra_coisa():
    ordem: list[str] = []
    cliente = ClienteFalso()
    original = cliente._registrar
    cliente._registrar = lambda nome, **kw: (ordem.append(nome), original(nome, **kw))[1]
    estado, _ = _estado(
        retomar=lambda registro_id, decisao: (ordem.append("retomar"), {"alerta": _alerta()})[1]
    )

    handler_botao("aprovar", estado)(lambda: ordem.append("ack"), _corpo(), cliente)

    assert ordem[0] == "ack"
    assert "retomar" in ordem and "chat_update" in ordem
    assert ordem.index("retomar") < ordem.index("chat_update")


@pytest.mark.parametrize(
    "acao,esperado",
    [
        ("aprovar", "Aprovado por Joe Teste às 11:32"),
        ("descartar", "Descartado por Joe Teste às 11:32"),
        ("nao_e_desvio", "Marcado como não é desvio por Joe Teste às 11:32"),
    ],
)
def test_clique_retoma_e_atualiza_a_mensagem(acao, esperado):
    decisoes = []

    def retomar(registro_id, decisao):
        decisoes.append((registro_id, decisao))
        return {"alerta": _alerta()}

    estado, _ = _estado(retomar=retomar)
    cliente = ClienteFalso()

    assert tratar_clique(acao, _corpo(acao), cliente, estado) is True

    registro_id, decisao = decisoes[0]
    assert registro_id == "r1"
    assert (decisao.alerta_id, decisao.acao, decisao.quem) == ("r1", acao, "Joe Teste")
    assert decisao.quando == datetime(2027, 1, 19, 14, 32, tzinfo=UTC)
    update = cliente.chamadas_de("chat_update")[0]
    assert (update["channel"], update["ts"]) == ("CALERTAS", "1700000000.000100")
    assert not [b for b in update["blocks"] if b["type"] == "actions"]
    assert esperado in update["blocks"][-1]["elements"][0]["text"]


def test_nome_cai_para_o_name_do_corpo_se_users_info_falhar():
    decisoes = []
    estado, _ = _estado(
        retomar=lambda rid, d: (decisoes.append(d), {"alerta": _alerta()})[1],
    )
    tratar_clique("aprovar", _corpo(), ClienteFalso(falhar={"users_info"}), estado)
    assert decisoes[0].quem == "joe.handle"


def test_segundo_clique_nao_atualiza_como_decisao_nova():
    estado, _ = _estado(retomar=lambda registro_id, decisao: None)
    cliente = ClienteFalso()

    assert tratar_clique("aprovar", _corpo(), cliente, estado) is False

    assert not cliente.chamadas_de("chat_update")
    aviso = cliente.chamadas_de("chat_postEphemeral")[0]
    assert aviso["user"] == "UCLICK"


def test_falha_no_retomar_nao_estoura_nem_atualiza():
    def quebrado(registro_id, decisao):
        raise RuntimeError("falha de teste")

    estado, _ = _estado(retomar=quebrado)
    cliente = ClienteFalso()
    assert tratar_clique("aprovar", _corpo(), cliente, estado) is False
    assert not cliente.chamadas_de("chat_update")


def test_clique_de_ponta_a_ponta_com_o_grafo_real(tmp_path, monkeypatch):
    """Grafo pausado de verdade: o primeiro clique grava uma decisão, o segundo não."""
    from radar import grafo
    from radar.nos.rotear import notificador_padrao

    caminho = str(tmp_path / "t.db")
    monkeypatch.setattr(config, "DATABASE_PATH", caminho)
    grafo.configurar(lambda alerta, registro: None)
    try:
        estado = Estado(
            agora=lambda: datetime(2027, 1, 19, 14, 32, tzinfo=UTC),
            em_segundo_plano=lambda funcao, *args: funcao(*args),
        )
        from radar.core.models import Origem, Registro

        registro = Registro(
            id="t:ponta",
            origem=Origem.slack,
            data=datetime(2027, 1, 19, tzinfo=UTC),
            autor="cliente",
            texto="Pode incluir o módulo de relatórios sem custo?",
        )
        resultado = grafo.processar(registro)
        if "__interrupt__" not in resultado:
            pytest.skip("o grafo de teste não pausou para aprovação neste ambiente")
        corpo = _corpo()
        corpo["actions"][0]["value"] = "t:ponta"
        cliente = ClienteFalso()

        assert tratar_clique("aprovar", corpo, cliente, estado) is True
        assert tratar_clique("descartar", corpo, cliente, estado) is False

        alertas = db.listar_alertas(caminho=caminho)
        assert alertas[0].decisao.acao == "aprovar"
        assert alertas[0].status == "aprovado"
        assert len(cliente.chamadas_de("chat_update")) == 1
    finally:
        grafo.configurar(notificador_padrao)


# --- slack_bot.py -----------------------------------------------------------------------

COMPLETO = {
    "SLACK_BOT_TOKEN": "xoxb-real",
    "SLACK_APP_TOKEN": "xapp-real",
    "SLACK_ALERT_CHANNEL_ID": "C01ABCDEF",
    "ANTHROPIC_API_KEY": "sk-ant-real",
}


def test_validacao_aceita_ambiente_completo():
    assert slack_bot.variaveis_faltantes(COMPLETO) == []


def test_validacao_lista_so_os_nomes_que_faltam_ou_tem_valor_de_exemplo():
    env = {
        **COMPLETO,
        "SLACK_BOT_TOKEN": "xoxb-...",
        "SLACK_ALERT_CHANNEL_ID": "C0000000000",
        "ANTHROPIC_API_KEY": "",
    }
    del env["SLACK_APP_TOKEN"]
    assert slack_bot.variaveis_faltantes(env) == [
        "SLACK_BOT_TOKEN",
        "SLACK_APP_TOKEN",
        "SLACK_ALERT_CHANNEL_ID",
        "ANTHROPIC_API_KEY",
    ]


def test_main_sai_com_erro_claro_sem_imprimir_valores(monkeypatch, capsys):
    monkeypatch.setattr(slack_bot, "load_dotenv", lambda *a, **k: None)
    for nome, valor in COMPLETO.items():
        monkeypatch.setenv(nome, valor)
    monkeypatch.setenv("SLACK_APP_TOKEN", "xapp-...")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-segredo")

    assert slack_bot.main() == 1

    erro = capsys.readouterr().err
    assert "SLACK_APP_TOKEN" in erro
    assert "SLACK_BOT_TOKEN" not in erro
    assert "xoxb-real" not in erro and "sk-ant-segredo" not in erro


def test_notificador_posta_no_canal_com_a_mencao_do_papel(tmp_path, monkeypatch):
    from radar import slack_alertas
    from radar.core.models import Origem, Registro

    caminho = str(tmp_path / "t.db")
    monkeypatch.setattr(config, "DATABASE_PATH", caminho)
    db.init_db(caminho)
    db.salvar_alerta(_alerta(), Acao.postar, "pendente", caminho=caminho)
    monkeypatch.setattr(slack_alertas, "usuario_do_papel", lambda papel: "UGESTOR")

    class Cliente:
        def __init__(self):
            self.postadas = []

        def chat_postMessage(self, **kw):  # noqa: N802
            self.postadas.append(kw)
            return {"channel": kw["channel"], "ts": "1.1"}

    cliente = Cliente()
    registro = Registro(
        id="r1", origem=Origem.slack, data=datetime(2027, 1, 19, tzinfo=UTC), autor="M", texto="t"
    )
    slack_bot.criar_notificador(cliente, "CALERTAS")(_alerta(), registro)

    assert cliente.postadas[0]["channel"] == "CALERTAS"
    assert "<@UGESTOR>" in cliente.postadas[0]["text"]
