"""Lógica pura da tela (radar/ui/app_logica.py): sem Streamlit."""

from datetime import UTC, datetime
from pathlib import Path

from radar.core.models import Alerta, Origem, TipoDesvio
from radar.ui import app_logica as logica
from radar.ui import textos_app

PROJETO = Path(__file__).parent.parent / "data" / "projeto_alfa.json"


def _alerta(tipo=TipoDesvio.escopo_extra):
    return Alerta(
        registro_id="slack:x",
        tipo=tipo,
        confianca=0.9,
        clausula="2.2",
        trecho_contrato="a",
        trecho_evidencia="b",
        justificativa="c",
    )


def test_registro_simulado_tem_origem_slack_canal_e_id_deterministico():
    agora = datetime(2027, 1, 19, 10, 0, tzinfo=UTC)
    r1 = logica.criar_registro_simulado("  oi  ", "Helena Prado", "projeto-alfa", agora)
    r2 = logica.criar_registro_simulado("oi", "Helena Prado", "projeto-alfa", agora)

    assert r1.origem is Origem.slack
    assert r1.texto == "oi"
    assert r1.canal == "projeto-alfa"
    assert r1.id == r2.id and r1.id.startswith("slack:")
    assert r1.data == agora


def test_classificar_resultado():
    assert logica.classificar_resultado(None) == "sem_desvio"
    assert logica.classificar_resultado({"alerta": _alerta(TipoDesvio.nenhum)}) == "sem_desvio"
    assert logica.classificar_resultado({"alerta": _alerta(), "acao": "postar"}) == "alerta"
    assert logica.classificar_resultado({"alerta": _alerta(), "acao": "resumo"}) == "resumo"
    assert logica.classificar_resultado({"alerta": _alerta(), "acao": "descartar"}) == "sem_desvio"
    assert logica.classificar_resultado({"alerta": _alerta()}) == "sem_desvio"


def test_mensagem_de_erro_distingue_chave_ausente():
    assert logica.mensagem_de_erro(TypeError("Could not resolve ... api_key")) == (
        textos_app.ERRO_SEM_CHAVE
    )
    assert "RuntimeError" in logica.mensagem_de_erro(RuntimeError("x"))


def test_formatar_data_usa_o_fuso_de_sao_paulo():
    assert logica.formatar_data(datetime(2027, 1, 19, 14, 30, tzinfo=UTC)) == "19/01/2027 11:30"
    assert logica.formatar_data(datetime(2027, 1, 19, 14, 30)) == "19/01/2027 14:30"
    assert logica.formatar_data("2027-01-19T14:30:00+00:00") == "19/01/2027 11:30"


def test_rotulos():
    assert logica.titulo_do_tipo(TipoDesvio.terceiro_sem_documento).startswith("Possível")
    assert logica.emoji_do_tipo("prazo_sla") == ":hourglass_flowing_sand:"
    assert logica.rotulo_status("nao_e_desvio") == "Não é desvio"
    assert logica.rotulo_papel(None) == textos_app.SEM_RESPONSAVEL
    assert logica.como_citacao("a\nb") == "> a\n> b"


def test_autores_e_canais_vem_do_projeto():
    autores = logica.autores_do_projeto(PROJETO)
    assert {"Helena Prado", "Marcos Lima"} <= set(autores)
    assert logica.canais_do_projeto(PROJETO) == ["projeto-alfa", "projeto-alfa-cliente"]
    # arquivo ausente: cai nos padrões em vez de quebrar
    assert logica.autores_do_projeto(PROJETO.with_name("nao_existe.json"))
    assert logica.canais_do_projeto(PROJETO.with_name("nao_existe.json"))


def test_pode_decidir_exige_pendente_e_processo_de_origem():
    assert logica.pode_decidir("pendente", "a", {"a": 1})
    assert not logica.pode_decidir("pendente", "b", {"a": 1})
    assert not logica.pode_decidir("aprovado", "a", {"a": 1})


def test_resumo_do_historico_para_apos_erros_seguidos_e_zera_com_sucesso():
    resumo = logica.ResumoHistorico(registros=10)
    for _ in range(logica.MAX_ERROS_SEGUIDOS - 1):
        assert not resumo.contar_erro("x", RuntimeError("e"))
    resumo.contar({"alerta": _alerta(), "acao": "postar"})  # sucesso zera a sequência
    assert not resumo.contar_erro("y", RuntimeError("e"))
    assert resumo.alertas == 1 and len(resumo.erros) == logica.MAX_ERROS_SEGUIDOS
    for _ in range(logica.MAX_ERROS_SEGUIDOS - 2):
        resumo.contar_erro("z", RuntimeError("e"))
    assert resumo.contar_erro("z", RuntimeError("e")) and resumo.interrompido
