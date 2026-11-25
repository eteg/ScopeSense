"""Tela do Streamlit (G-11), com `AppTest`: sem navegador, sem rede, sem chave.

`grafo.processar` e `grafo.retomar` são trocados por funções falsas (o modelo não é chamado).
O banco é um SQLite temporário. O `st.cache_resource` é limpo a cada teste, porque o
`AppTest` roda no mesmo processo e o cache sobreviveria de um teste para o outro.
"""

import importlib
from datetime import UTC, datetime
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from radar import config, db, grafo
from radar.core.models import Alerta, Origem, Papel, Registro, TipoDesvio
from radar.nos.rotear import notificador_padrao
from radar.ui import textos_app

rotear_mod = importlib.import_module("radar.nos.rotear")

APP = Path(__file__).parent.parent / "app.py"
TRECHO_CONTRATO = "Módulos extras dependem de aditivo contratual."
TRECHO_EVIDENCIA = "Pode incluir o módulo de relatórios sem custo?"


@pytest.fixture(autouse=True)
def ambiente(tmp_path, monkeypatch):
    caminho = str(tmp_path / "app.db")
    monkeypatch.setattr(config, "DATABASE_PATH", caminho)
    st.cache_resource.clear()
    yield caminho
    st.cache_resource.clear()
    grafo.configurar(notificador_padrao)


def _alerta(id_, tipo=TipoDesvio.escopo_extra, papel=Papel.gestor, clausula="2.2", conf=0.92):
    return Alerta(
        registro_id=id_,
        tipo=tipo,
        confianca=conf,
        clausula=clausula,
        trecho_contrato=TRECHO_CONTRATO,
        trecho_evidencia=TRECHO_EVIDENCIA,
        justificativa="Pedido fora do escopo contratado.",
        responsavel=papel,
    )


def _registro(id_="slack:abc"):
    return Registro(
        id=id_,
        origem=Origem.slack,
        data=datetime(2027, 1, 19, 14, 30, tzinfo=UTC),
        autor="Marcos Lima",
        texto=TRECHO_EVIDENCIA,
        metadados={"canal": "projeto-alfa-cliente"},
    )


def _guardar(caminho, alerta, status="pendente", acao="postar", registro=None):
    db.init_db(caminho)
    db.salvar_alerta(alerta, acao, status, caminho=caminho)
    if registro is not None:
        db.salvar_registro(registro, caminho=caminho)


def _tela(at) -> str:
    """Todo o texto visível, para checar conteúdo sem depender da estrutura."""
    elementos = [*at.markdown, *at.caption, *at.info, *at.success, *at.warning, *at.error, *at.text]
    return "\n".join(str(e.value) for e in elementos)


def _chaves_de_botoes(at) -> list[str]:
    return [b.key for b in at.button]


def _rodar() -> AppTest:
    return AppTest.from_file(str(APP), default_timeout=60).run()


class Falso:
    """Substitui `grafo.processar` e `grafo.retomar`, imitando o que o grafo real faz."""

    def __init__(self, monkeypatch, *, tipo=TipoDesvio.escopo_extra, acao="postar", erro=None):
        self.tipo, self.acao, self.erro = tipo, acao, erro
        self.erros_por_id: set[str] = set()
        self.processados: list[tuple[Registro, list[Registro]]] = []
        self.retomadas: list[tuple[str, object]] = []
        self.retorno_retomar: dict | None = {"decisao": "ok"}
        monkeypatch.setattr(grafo, "processar", self.processar)
        monkeypatch.setattr(grafo, "retomar", self.retomar)

    def processar(self, registro, contexto=()):
        self.processados.append((registro, list(contexto)))
        if self.erro is not None:
            raise self.erro
        if registro.id in self.erros_por_id:
            raise RuntimeError("falha de teste")
        alerta = _alerta(registro.id, tipo=self.tipo)
        if self.tipo is TipoDesvio.nenhum:
            return {"alerta": alerta}
        status = "pendente" if self.acao == "postar" else "em_resumo"
        db.salvar_alerta(alerta, self.acao, status, caminho=config.DATABASE_PATH)
        if self.acao == "postar":
            rotear_mod._notificador(alerta, registro)  # o que o nó `rotear` faz
        return {"alerta": alerta, "acao": self.acao}

    def retomar(self, registro_id, decisao):
        self.retomadas.append((registro_id, decisao))
        return self.retorno_retomar


def _enviar(at, texto=TRECHO_EVIDENCIA, autor="Marcos Lima", canal="projeto-alfa-cliente"):
    at.text_area(key="sim_texto").input(texto)
    at.selectbox(key="sim_autor").select(autor)
    at.selectbox(key="sim_canal").select(canal)
    at.button(key="sim_enviar").click()
    return at.run()


# --- subida e fila -----------------------------------------------------------------------


def test_app_sobe_com_tres_abas_e_sem_processar_nada(monkeypatch):
    falso = Falso(monkeypatch)
    at = _rodar()

    assert not at.exception
    assert [t.label for t in at.tabs] == [
        textos_app.ABA_FILA,
        textos_app.ABA_SIMULAR,
        textos_app.ABA_HISTORICO,
    ]
    assert "Nenhum alerta por enquanto." in _tela(at)
    assert falso.processados == []  # o histórico nunca roda sozinho


def test_fila_mostra_tipo_status_e_clausula(ambiente):
    _guardar(ambiente, _alerta("slack:a1"), registro=_registro("slack:a1"))
    at = _rodar()

    assert not at.exception
    tela = _tela(at)
    assert "Possível desvio de escopo" in tela
    assert "Status: Pendente" in tela
    assert "Cláusula 2.2" in tela
    assert TRECHO_CONTRATO in tela
    assert TRECHO_EVIDENCIA in tela
    assert "Marcos Lima" in tela and "Slack" in tela  # evidência buscada pelo registro_id
    assert "19/01/2027 11:30" in tela  # 14:30 UTC em America/Sao_Paulo
    assert "Responsável: Gestor" in tela
    assert "Confiança: 92%" in tela


def test_fila_respeita_os_filtros(ambiente):
    _guardar(ambiente, _alerta("slack:a1"))
    _guardar(
        ambiente, _alerta("slack:a2", TipoDesvio.prazo_sla, Papel.comercial, "3.1"), "pendente"
    )
    quando = datetime(2027, 1, 20, tzinfo=UTC)
    db.registrar_decisao(
        db.Decisao(alerta_id="slack:a2", acao="aprovar", quem="Teste", quando=quando),
        caminho=ambiente,
    )

    at = _rodar()
    tela = _tela(at)
    assert "Possível desvio de escopo" in tela and "Possível desvio de prazo" in tela
    assert "Status: Aprovado" in tela and "Decidido por Teste" in tela

    at.selectbox(key="filtro_status").select("aprovado").run()
    tela = _tela(at)
    assert "Possível desvio de prazo" in tela
    assert "Possível desvio de escopo" not in tela

    at.selectbox(key="filtro_status").select(None).run()
    at.selectbox(key="filtro_papel").select("gestor").run()
    tela = _tela(at)
    assert "Possível desvio de escopo" in tela
    assert "Possível desvio de prazo" not in tela

    at.selectbox(key="filtro_status").select("descartado").run()
    assert textos_app.FILA_VAZIA_FILTRADA in _tela(at)


def test_pendente_de_outro_processo_fica_so_leitura(ambiente):
    _guardar(ambiente, _alerta("slack:a1"))
    at = _rodar()

    assert not at.exception
    assert not [k for k in _chaves_de_botoes(at) if k.startswith("fila_")]
    assert textos_app.NOTA_SOMENTE_LEITURA in _tela(at)


# --- simular mensagem --------------------------------------------------------------------


def test_simular_cria_o_registro_e_mostra_o_alerta_com_botoes(monkeypatch):
    falso = Falso(monkeypatch)
    at = _enviar(_rodar())

    assert not at.exception
    assert len(falso.processados) == 1
    registro, contexto = falso.processados[0]
    assert registro.origem is Origem.slack
    assert registro.autor == "Marcos Lima"
    assert registro.texto == TRECHO_EVIDENCIA
    assert registro.canal == "projeto-alfa-cliente"
    assert registro.id.startswith("slack:")
    assert registro.data.utcoffset() is not None  # com fuso
    assert contexto == []

    assert textos_app.RESULTADO_ALERTA in _tela(at)
    chaves = _chaves_de_botoes(at)
    for acao in ("aprovar", "descartar", "nao_e_desvio"):
        assert f"sim_{acao}_{registro.id}" in chaves
        assert f"fila_{acao}_{registro.id}" in chaves  # o alerta também entrou na fila
    # o registro foi guardado: a fila mostra a evidência
    assert db.obter_registro(registro.id, caminho=config.DATABASE_PATH) is not None


def test_simular_sem_desvio(monkeypatch):
    Falso(monkeypatch, tipo=TipoDesvio.nenhum)
    at = _enviar(_rodar(), texto="Bom dia, tudo certo.")

    assert not at.exception
    assert textos_app.RESULTADO_SEM_DESVIO in _tela(at)
    assert not [k for k in _chaves_de_botoes(at) if k.startswith("sim_a")]


def test_simular_confianca_media_fica_em_resumo_sem_botoes(monkeypatch):
    Falso(monkeypatch, acao="resumo")
    at = _enviar(_rodar())

    assert not at.exception
    assert textos_app.RESULTADO_RESUMO in _tela(at)
    assert "Status: Em resumo" in _tela(at)
    assert not [k for k in _chaves_de_botoes(at) if "aprovar" in k]


def test_simular_mensagem_vazia_nao_chama_o_grafo(monkeypatch):
    falso = Falso(monkeypatch)
    at = _rodar()
    at.button(key="sim_enviar").click().run()

    assert [w.value for w in at.warning] == [textos_app.MENSAGEM_VAZIA]
    assert falso.processados == []


def test_erro_do_modelo_vira_st_error_e_nao_excecao(monkeypatch):
    Falso(
        monkeypatch,
        erro=TypeError("Could not resolve authentication method. Expected api_key to be set."),
    )
    at = _enviar(_rodar())

    assert not at.exception
    assert [e.value for e in at.error] == [textos_app.ERRO_SEM_CHAVE]
    assert "ANTHROPIC_API_KEY" in at.error[0].value


def test_erro_qualquer_tambem_nao_derruba_o_app(monkeypatch):
    Falso(monkeypatch, erro=RuntimeError("rede fora do ar"))
    at = _enviar(_rodar())

    assert not at.exception
    assert "RuntimeError" in at.error[0].value and "rede fora do ar" in at.error[0].value


# --- botões de decisão -------------------------------------------------------------------


def test_botao_chama_retomar_uma_vez_com_a_decisao_certa(monkeypatch):
    falso = Falso(monkeypatch)
    at = _enviar(_rodar())
    registro_id = falso.processados[0][0].id

    at.button(key=f"sim_descartar_{registro_id}").click().run()

    assert not at.exception
    assert len(falso.retomadas) == 1
    chamado_id, decisao = falso.retomadas[0]
    assert chamado_id == registro_id
    assert decisao.acao == "descartar"
    assert decisao.alerta_id == registro_id
    assert decisao.quem == textos_app.QUEM_DECIDE
    assert decisao.quando.utcoffset() is not None
    assert textos_app.DECISAO_REGISTRADA.format(rotulo="Descartar") in _tela(at)


def test_botao_na_fila_tambem_chama_retomar(monkeypatch):
    falso = Falso(monkeypatch)
    at = _enviar(_rodar())
    registro_id = falso.processados[0][0].id

    at.button(key=f"fila_nao_e_desvio_{registro_id}").click().run()

    assert [(i, d.acao) for i, d in falso.retomadas] == [(registro_id, "nao_e_desvio")]


def test_segundo_clique_nao_grava_e_mostra_mensagem_discreta(monkeypatch):
    falso = Falso(monkeypatch)
    falso.retorno_retomar = None  # o grafo real devolve None quando já foi decidido
    at = _enviar(_rodar())
    registro_id = falso.processados[0][0].id

    at.button(key=f"sim_aprovar_{registro_id}").click().run()

    assert not at.exception
    assert not at.error
    assert textos_app.DECISAO_JA_REGISTRADA in _tela(at)
    assert len(falso.retomadas) == 1


def test_erro_no_retomar_vira_mensagem(monkeypatch):
    falso = Falso(monkeypatch)
    at = _enviar(_rodar())
    registro_id = falso.processados[0][0].id

    def quebra(*_):
        raise RuntimeError("grafo caiu")

    monkeypatch.setattr(grafo, "retomar", quebra)
    at.button(key=f"sim_aprovar_{registro_id}").click().run()

    assert not at.exception
    assert "grafo caiu" in at.error[0].value


# --- histórico ---------------------------------------------------------------------------


def _fonte_falsa(monkeypatch, registros):
    arquivos = importlib.import_module("radar.fontes.arquivos")

    class FonteFalsa:
        def __init__(self, pasta):
            self.pasta = pasta

        def fetch(self, consulta=None):
            return registros

    monkeypatch.setattr(arquivos, "FileSource", FonteFalsa)


def _registros_do_historico():
    return [
        Registro(
            id=f"slack:h{i}",
            origem=Origem.slack,
            data=datetime(2027, 1, 10 + i, 12, 0, tzinfo=UTC),
            autor="Marcos Lima",
            texto=f"mensagem {i}",
            metadados={"canal": "projeto-alfa"},
        )
        for i in range(4)
    ]


def test_historico_processa_tolera_erro_e_resume(monkeypatch, ambiente):
    registros = _registros_do_historico()
    _fonte_falsa(monkeypatch, registros)
    falso = Falso(monkeypatch)
    falso.erros_por_id = {"slack:h1"}
    _guardar(ambiente, _alerta("slack:h3"))  # já na fila: não reprocessa

    at = _rodar()
    assert falso.processados == []
    at.button(key="historico_processar").click().run()

    assert not at.exception
    assert [r.id for r, _ in falso.processados] == ["slack:h0", "slack:h1", "slack:h2"]
    assert "4 registro(s) lido(s): 2 alerta(s), 0 em resumo, 1 já na fila" in _tela(at)
    assert "1 erro(s)" in _tela(at)
    # o contexto são as mensagens anteriores do mesmo canal
    assert [r.id for r in falso.processados[2][1]] == ["slack:h0", "slack:h1"]
    # e os alertas novos aparecem na fila, já na mesma execução
    assert "Possível desvio de escopo" in _tela(at)
    assert any(k == "fila_aprovar_slack:h0" for k in _chaves_de_botoes(at))


def test_historico_para_depois_de_erros_seguidos(monkeypatch):
    registros = _registros_do_historico() * 3
    registros = [r.model_copy(update={"id": f"slack:x{i}"}) for i, r in enumerate(registros)]
    _fonte_falsa(monkeypatch, registros)
    Falso(monkeypatch, erro=TypeError("api_key ausente"))

    at = _rodar()
    at.button(key="historico_processar").click().run()

    assert not at.exception
    assert "5 erro(s)" in _tela(at)
    assert [w.value for w in at.warning] == [textos_app.HISTORICO_INTERROMPIDO.format(n=5)]
