"""eval/rodar_eval.py com um `analisar` falso: sem rede e sem chave."""

import json
from datetime import datetime

import pytest

from eval import rodar_eval as ev
from radar import config, db, llm
from radar.core.models import Alerta, Origem, Papel, Registro, TipoDesvio

DATA = datetime(2027, 1, 10, 9, 0, tzinfo=ev.FUSO)


def _gab(rid, e_desvio=False, tipo="nenhum", resp=None, clausula=None, aceitas=None, nota=""):
    linha = {
        "registro_id": rid, "e_desvio": e_desvio, "tipo": tipo, "responsavel": resp,
        "clausula": clausula, "nota": nota,
    }  # fmt: skip
    if aceitas:
        linha["clausulas_aceitas"] = aceitas
    return linha


def _alerta(rid, tipo=TipoDesvio.escopo_extra, clausula="2.2", resp=Papel.gestor, conf=0.9):
    return Alerta(
        registro_id=rid, tipo=tipo, confianca=conf, clausula=clausula, trecho_contrato="c",
        trecho_evidencia="e", justificativa="j", responsavel=resp,
    )  # fmt: skip


GABARITO = [
    _gab("d1", True, "escopo_extra", "gestor", "2.2", ["2.2"], "DESVIO 1"),
    _gab("d2", True, "prazo_sla", "comercial", "3", ["3"], "DESVIO 2"),
    _gab("n1"),
    _gab("i1", nota="ISCA 1: parece desvio"),
]


def _tudo_certo():
    return {
        "d1": _alerta("d1"),
        "d2": _alerta("d2", TipoDesvio.prazo_sla, "3", Papel.comercial),
        "n1": None,
        "i1": None,
    }


def test_tudo_certo():
    m = ev.calcular_metricas(GABARITO, _tudo_certo())
    assert m["precisao"] == 1.0 and m["recall"] == 1.0
    assert m["acerto_tipo"] == m["acerto_responsavel"] == m["acerto_clausula"] == 1.0
    assert m["alarmes_falsos_iscas"] == 0 and m["alarmes_falsos_gerais"] == 0
    assert (m["desvios"], m["iscas"], m["alertas"]) == (2, 1, 2)


def test_desvio_perdido():
    alertas = _tudo_certo() | {"d2": None}
    m = ev.calcular_metricas(GABARITO, alertas)
    assert m["recall"] == 0.5
    assert m["precisao"] == 1.0
    assert m["desvios_detectados"] == 1


def test_isca_que_alerta():
    alertas = _tudo_certo() | {"i1": _alerta("i1")}
    m = ev.calcular_metricas(GABARITO, alertas)
    assert m["alarmes_falsos_iscas"] == 1
    assert m["alarmes_falsos_gerais"] == 1
    assert m["precisao"] == pytest.approx(2 / 3)
    assert m["recall"] == 1.0


def test_alarme_falso_fora_das_iscas():
    m = ev.calcular_metricas(GABARITO, _tudo_certo() | {"n1": _alerta("n1")})
    assert m["alarmes_falsos_gerais"] == 1
    assert m["alarmes_falsos_iscas"] == 0


def test_nenhum_alerta_nao_divide_por_zero():
    m = ev.calcular_metricas(GABARITO, dict.fromkeys(["d1", "d2", "n1", "i1"]))
    assert m["precisao"] == 0.0 and m["recall"] == 0.0
    assert m["acerto_tipo"] == m["acerto_responsavel"] == m["acerto_clausula"] == 0.0


def test_sem_desvios_no_gabarito():
    m = ev.calcular_metricas([_gab("n1")], {"n1": None})
    assert m["recall"] == 0.0 and m["desvios"] == 0


def test_so_conta_alerta_postado():
    """Confiança entre 0,5 e 0,8 é resumo; abaixo de 0,5 é descarte: nenhum vira alerta."""
    alertas = _tudo_certo() | {"d1": _alerta("d1", conf=0.6), "d2": _alerta("d2", conf=0.3)}
    m = ev.calcular_metricas(GABARITO, alertas)
    assert m["alertas"] == 0 and m["recall"] == 0.0


def test_clausula_aceita_alternativa_conta_como_acerto():
    gab = [_gab("d1", True, "promessa_fora_do_contrato", "administrativo_contratos", "7",
                ["7", "2.2"], "DESVIO 4")]  # fmt: skip
    alerta = _alerta("d1", TipoDesvio.promessa_fora_do_contrato, "2.2",
                     Papel.administrativo_contratos)  # fmt: skip
    m = ev.calcular_metricas(gab, {"d1": alerta})
    assert m["acerto_clausula"] == 1.0
    errada = _alerta("d1", TipoDesvio.promessa_fora_do_contrato, "9",
                     Papel.administrativo_contratos)  # fmt: skip
    assert ev.calcular_metricas(gab, {"d1": errada})["acerto_clausula"] == 0.0


def test_clausula_sem_lista_usa_a_clausula_e_ignora_a_palavra():
    gab = [_gab("d1", True, "escopo_extra", "gestor", "2.2")]
    m = ev.calcular_metricas(gab, {"d1": _alerta("d1", clausula="Cláusula 2.2")})
    assert m["acerto_clausula"] == 1.0


def test_tipo_e_responsavel_errados():
    errado = _alerta("d1", TipoDesvio.prazo_sla, "2.2", Papel.comercial)
    m = ev.calcular_metricas(GABARITO[:1], {"d1": errado})
    assert m["recall"] == 1.0
    assert m["acerto_tipo"] == 0.0 and m["acerto_responsavel"] == 0.0
    assert m["acerto_clausula"] == 1.0


def test_erros_contados():
    m = ev.calcular_metricas(GABARITO, _tudo_certo() | {"d2": None}, erros=["d2"])
    assert m["erros"] == 1
    assert next(d for d in m["detalhes"] if d["registro_id"] == "d2")["erro"] is True


def test_metricas_do_modelo():
    antes = {"chamadas": 5, "invalidas": 1, "retentativas": 1}
    depois = {"chamadas": 15, "invalidas": 3, "retentativas": 2}
    m = ev.metricas_do_modelo(antes, depois)
    assert m["chamadas_modelo"] == 10 and m["saidas_validas"] == 8
    assert m["taxa_saidas_validas"] == 0.8 and m["novas_tentativas"] == 1
    zero = ev.metricas_do_modelo(antes, antes)
    assert zero["taxa_saidas_validas"] == 0.0


# --- rodar / main ----------------------------------------------------------------------------


def _registros():
    return [
        Registro(id=rid, origem=Origem.slack, data=DATA.replace(minute=i), autor="Ana",
                 texto=f"texto {rid}", metadados={"canal": "C1"})
        for i, rid in enumerate(["d1", "d2", "n1", "i1"])
    ]  # fmt: skip


@pytest.fixture
def gabarito_arq(tmp_path):
    caminho = tmp_path / "gabarito.json"
    caminho.write_text(json.dumps(GABARITO, ensure_ascii=False), encoding="utf-8")
    return caminho


@pytest.fixture(autouse=True)
def isolado(monkeypatch):
    monkeypatch.setattr(llm, "CONTADORES", {"chamadas": 0, "invalidas": 0, "retentativas": 0})
    monkeypatch.setattr(config, "MODO_DEMO", True)  # o eval tem que desligar sozinho


def _fonte_falsa(monkeypatch):
    fonte = type("F", (), {"fetch": lambda self: _registros()})
    monkeypatch.setattr(ev, "FileSource", lambda _pasta: fonte())


def _analisar_falso(visto):
    certos = _tudo_certo()

    def analisar(registro, contexto):
        visto.append((registro.id, config.MODO_DEMO, len(contexto)))
        llm.CONTADORES["chamadas"] += 2
        llm.CONTADORES["invalidas"] += 1
        llm.CONTADORES["retentativas"] += 1
        return certos[registro.id]

    return analisar


def test_rodar_forca_modo_demo_off_e_restaura(gabarito_arq):
    visto = []
    m = ev.rodar(
        "unused", analisar=_analisar_falso(visto), gabarito=gabarito_arq, registros=_registros(),
        versao="v1",
    )  # fmt: skip
    assert all(demo is False for _, demo, _ in visto)
    assert config.MODO_DEMO is True  # restaurado
    assert m["recall"] == 1.0 and m["precisao"] == 1.0 and m["versao"] == "v1"
    assert m["chamadas_modelo"] == 8 and m["novas_tentativas"] == 4
    assert [v[0] for v in visto] == ["d1", "d2", "n1", "i1"]
    assert visto[2][2] == 2  # contexto: os 2 registros anteriores do canal


def test_rodar_limite_e_erro_nao_derruba(gabarito_arq):
    def analisar(registro, contexto):
        if registro.id == "d1":
            raise RuntimeError("falhou")
        return _tudo_certo()[registro.id]

    m = ev.rodar("x", analisar=analisar, gabarito=gabarito_arq, registros=_registros())
    assert m["erros"] == 1 and m["recall"] == 0.5
    limitado = ev.rodar("x", analisar=analisar, gabarito=gabarito_arq, registros=_registros(),
                        limite=2)  # fmt: skip
    assert limitado["registros_avaliados"] == 2


def test_rodar_ignora_registro_sem_gabarito(gabarito_arq):
    extra = _registros() + [
        Registro(id="x9", origem=Origem.slack, data=DATA, autor="A", texto="t")
    ]
    visto = []
    m = ev.rodar("x", analisar=_analisar_falso(visto), gabarito=gabarito_arq, registros=extra)
    assert m["registros_avaliados"] == 4 and m["sem_gabarito"] == 1


def test_main_escreve_json_md_e_banco(tmp_path, monkeypatch, capsys):
    banco = tmp_path / "radar.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(banco))
    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / "gabarito.json").write_text(json.dumps(GABARITO), encoding="utf-8")
    _fonte_falsa(monkeypatch)
    saida = tmp_path / "resultados"

    codigo = ev.main(
        ["--versao", "v1-teste", "--pasta", str(dados), "--saida", str(saida)],
        analisar=_analisar_falso([]),
    )
    assert codigo == 0
    arquivos = sorted(p.suffix for p in saida.iterdir())
    assert arquivos == [".json", ".md"]
    dados_json = json.loads(next(saida.glob("*.json")).read_text(encoding="utf-8"))
    assert dados_json["versao"] == "v1-teste" and dados_json["recall"] == 1.0
    md = next(saida.glob("*.md")).read_text(encoding="utf-8")
    assert "| Recall (desvios detectados) | 100% (2/2) | 4 de 4 |" in md
    out = capsys.readouterr().out
    assert "Recall" in out and "Alarmes falsos nas iscas" in out

    con = db.conectar(banco)
    try:
        linha = con.execute("SELECT versao, metricas FROM eval_execucoes").fetchone()
    finally:
        con.close()
    assert linha["versao"] == "v1-teste"
    assert json.loads(linha["metricas"])["precisao"] == 1.0
    assert "detalhes" not in json.loads(linha["metricas"])


def test_main_sem_db(tmp_path, monkeypatch):
    banco = tmp_path / "radar.db"
    monkeypatch.setattr(config, "DATABASE_PATH", str(banco))
    dados = tmp_path / "dados"
    dados.mkdir()
    (dados / "gabarito.json").write_text(json.dumps(GABARITO), encoding="utf-8")
    _fonte_falsa(monkeypatch)
    ev.main(["--sem-db", "--limite", "1", "--pasta", str(dados), "--saida", str(tmp_path / "r")],
            analisar=_analisar_falso([]))  # fmt: skip
    assert not banco.exists()


def test_nome_do_relatorio_nao_sobrescreve(tmp_path):
    agora = datetime(2026, 11, 25, 14, 30, tzinfo=ev.FUSO)
    m = ev.rodar("x", analisar=_analisar_falso([]), gabarito=_gab_arq(tmp_path),
                 registros=_registros())  # fmt: skip
    j1, _ = ev.salvar_relatorio(m, tmp_path / "r", agora)
    j2, _ = ev.salvar_relatorio(m, tmp_path / "r", agora)
    assert j1.name == "2026-11-25_1430.json" and j2.name == "2026-11-25_1430-2.json"


def _gab_arq(tmp_path):
    caminho = tmp_path / "g.json"
    caminho.write_text(json.dumps(GABARITO), encoding="utf-8")
    return caminho


def test_comparar(tmp_path, capsys):
    pior = ev.calcular_metricas(GABARITO, _tudo_certo() | {"d2": None, "i1": _alerta("i1")})
    pior.update(versao="v1-prompt-a", novas_tentativas=3, tempo_total_s=10.0)
    melhor = ev.calcular_metricas(GABARITO, _tudo_certo())
    melhor.update(versao="v2-prompt-b", novas_tentativas=0, tempo_total_s=8.0)
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    a.write_text(json.dumps(pior), encoding="utf-8")
    b.write_text(json.dumps(melhor), encoding="utf-8")

    assert ev.main(["--comparar", str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "v1-prompt-a" in out and "v2-prompt-b" in out
    recall = next(linha for linha in out.splitlines() if linha.startswith("Recall"))
    assert "50%" in recall and "100%" in recall and "+50 pp" in recall
    iscas = next(linha for linha in out.splitlines() if linha.startswith("Alarmes falsos nas"))
    assert "-1" in iscas


def test_help_avisa_que_custa(capsys):
    with pytest.raises(SystemExit):
        ev.main(["--help"])
    assert "custa" in capsys.readouterr().out
