"""G-03 (e dados J-07/J-08): parser do export do Slack e gabarito base."""

import importlib.util
import json
import unicodedata
from datetime import datetime
from pathlib import Path

import pytest

from radar.core.models import Origem
from radar.fontes import arquivos
from radar.fontes.arquivos import FUSO, FileSource, gerar_id
from radar.fontes.slack_export import (
    carregar_pessoas,
    ler_export,
    mensagem_para_registro,
    ts_para_data,
)

RAIZ = Path(__file__).resolve().parent.parent
DATA = RAIZ / "data"
PESSOAS = {"U_G": "Helena Prado", "U_B": "Bruno Siqueira"}


def msg(**extra) -> dict:
    base = {
        "ts": "1768827600.000100",
        "user": "U_G",
        "text": "Bom dia",
        "thread_ts": None,
        "channel": "projeto-alfa",
    }
    return {**base, **extra}


def sem_acento(texto: str) -> str:
    return unicodedata.normalize("NFD", texto).encode("ascii", "ignore").decode().lower()


# --- conversão ---------------------------------------------------------------


def test_ts_vira_data_no_fuso_de_sao_paulo():
    # 1768827600 = 2026-01-19 13:00:00 UTC = 10:00 em Sao Paulo (UTC-3)
    data = ts_para_data("1768827600.000100")
    assert data == datetime(2026, 1, 19, 10, 0, 0, 100, tzinfo=FUSO)
    assert data.tzinfo is not None and data.utcoffset().total_seconds() == -3 * 3600


def test_registro_basico():
    r = mensagem_para_registro(msg(), PESSOAS)
    assert r.origem == Origem.slack
    assert r.autor == "Helena Prado"
    assert r.texto == "Bom dia"
    assert r.canal == "projeto-alfa"
    assert r.thread_id is None
    assert r.link == "slack://projeto-alfa/1768827600.000100"
    assert r.data.hour == 10


def test_autor_desconhecido_mantem_o_id():
    assert mensagem_para_registro(msg(user="U_XYZ"), PESSOAS).autor == "U_XYZ"


def test_mencao_vira_nome_e_desconhecida_mantem_id():
    r = mensagem_para_registro(msg(text="<@U_B> vê isso com <@U_XYZ>?"), PESSOAS)
    assert r.texto == "Bruno Siqueira vê isso com U_XYZ?"


def test_thread_id_guardado():
    r = mensagem_para_registro(msg(thread_ts="1768827000.000050"), PESSOAS)
    assert r.thread_id == "1768827000.000050"
    assert r.metadados == {"canal": "projeto-alfa", "thread_id": "1768827000.000050"}


def test_id_deterministico_e_igual_ao_gerar_id():
    a = mensagem_para_registro(msg(), PESSOAS)
    b = mensagem_para_registro(msg(), PESSOAS)
    assert a.id == b.id == gerar_id(Origem.slack, a.texto, a.data)
    assert a.id.startswith("slack:")
    assert mensagem_para_registro(msg(text="outro"), PESSOAS).id != a.id


def test_ler_export_ignora_bot_subtype_e_vazias(tmp_path: Path):
    mensagens = [
        msg(),
        msg(ts="1768827700.000200", bot_id="B1"),
        msg(ts="1768827800.000300", subtype="channel_join"),
        msg(ts="1768827900.000400", text="   "),
        msg(ts="1768828000.000500", text=""),
        msg(ts="1768828100.000600", text="Segunda de verdade"),
    ]
    caminho = tmp_path / "slack_export.json"
    caminho.write_text(json.dumps(mensagens), encoding="utf-8")
    registros = ler_export(caminho)
    assert [r.texto for r in registros] == ["Bom dia", "Segunda de verdade"]


def test_ler_export_usa_projeto_json_quando_informado(tmp_path: Path):
    projeto = tmp_path / "outro.json"
    projeto.write_text(
        json.dumps({"papeis": {"gestor": {"nome": "Ana", "slack_id": "U_G"}}}), encoding="utf-8"
    )
    caminho = tmp_path / "slack_export.json"
    caminho.write_text(json.dumps([msg()]), encoding="utf-8")
    assert ler_export(caminho, projeto)[0].autor == "Ana"
    assert ler_export(caminho)[0].autor == "U_G"  # sem projeto_alfa.json ao lado


def test_parser_registrado_no_filesource():
    assert arquivos.PARSERS["slack_export.json"] is ler_export


# --- projeto_alfa.json (J-07) --------------------------------------------------


def test_projeto_alfa_json():
    dados = json.loads((DATA / "projeto_alfa.json").read_text(encoding="utf-8"))
    assert set(dados["papeis"]) == {"gestor", "comercial", "administrativo_contratos"}
    assert dados["papeis"]["gestor"]["nome"] == "Helena Prado"
    assert dados["roteamento"] == {
        "escopo_extra": "gestor",
        "prazo_sla": "comercial",
        "terceiro_sem_documento": "administrativo_contratos",
        "promessa_fora_do_contrato": "administrativo_contratos",
    }
    assert dados["terceiro"]["empresa"] == "Nimbus Serviços"
    assert "_aviso" in dados
    pessoas = carregar_pessoas(DATA / "projeto_alfa.json")
    assert pessoas["U_CLIENTE_01"] == "Marcos Lima"
    assert pessoas["U_CLIENTE_02"] == "Patrícia Souza"


# --- slack_export.json real (J-08) ---------------------------------------------


@pytest.fixture(scope="module")
def bruto() -> list[dict]:
    return json.loads((DATA / "slack_export.json").read_text(encoding="utf-8"))


def test_export_tem_22_a_25_mensagens_com_ts_crescente(bruto):
    assert 22 <= len(bruto) <= 25
    ts = [float(m["ts"]) for m in bruto]
    assert all(a < b for a, b in zip(ts, ts[1:], strict=False))
    assert {m["channel"] for m in bruto} == {"projeto-alfa", "projeto-alfa-cliente"}
    datas = [ts_para_data(m["ts"]) for m in bruto]
    assert datas[0].date() >= datetime(2027, 1, 18).date()
    assert datas[-1].date() <= datetime(2027, 2, 5).date()


def test_export_sem_palavras_proibidas(bruto):
    for m in bruto:
        texto = sem_acento(m["text"])
        for proibida in ("desvio", "contrato", "clausula"):
            assert proibida not in texto, (proibida, m["text"])


def test_desvios_nas_datas_da_biblia(bruto):
    registros = ler_export(DATA / "slack_export.json")
    por_texto = {r.texto: r for r in registros}

    def achar(trecho: str):
        achados = [r for t, r in por_texto.items() if trecho in t]
        assert len(achados) == 1, trecho
        return achados[0]

    assert achar("a gente faz, sem problema").data.date().isoformat() == "2027-01-19"
    assert achar("só fica pronta em 12/02").data.date().isoformat() == "2027-01-22"
    joao = achar("o João da Nimbus começa amanhã no cliente")
    assert joao.data.date().isoformat() == "2027-01-26"
    assert achar("A Carla da Nimbus começa amanhã")
    assert achar("o aditivo do módulo de integração foi assinado, podemos seguir")


def test_resposta_do_desvio_1_esta_na_thread_da_mae(bruto):
    resposta = next(m for m in bruto if "a gente faz, sem problema" in m["text"])
    mae = next(m for m in bruto if m["ts"] == resposta["thread_ts"])
    assert mae["channel"] == resposta["channel"] == "projeto-alfa-cliente"
    assert "módulo de relatórios" in mae["text"]
    assert mae["thread_ts"] is None
    assert float(mae["ts"]) < float(resposta["ts"])


def test_filesource_devolve_os_registros_ordenados(bruto):
    todos = FileSource(DATA).fetch()
    # A pasta data/ também tem a reunião (G-09) e os PDFs (G-10): aqui interessa só o Slack.
    registros = [r for r in todos if r.origem == Origem.slack]
    assert len(registros) == len(bruto)
    datas = [r.data for r in todos]
    assert datas == sorted(datas)
    assert len({r.id for r in todos}) == len(todos)
    autores = {r.autor for r in registros}
    assert {"Helena Prado", "Bruno Siqueira", "Marcos Lima", "Patrícia Souza"} <= autores
    assert any("Bruno Siqueira consegue me passar" in r.texto for r in registros)
    assert not any("<@" in r.texto for r in registros)


# --- script do gabarito base -----------------------------------------------------


@pytest.fixture(scope="module")
def script():
    spec = importlib.util.spec_from_file_location(
        "gerar_gabarito_base", RAIZ / "scripts" / "gerar_gabarito_base.py"
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_gabarito_base_cobre_todos_os_ids(script, tmp_path: Path):
    saida = tmp_path / "gab.json"
    assert script.main(["--pasta", str(DATA), "--saida", str(saida)]) == 0
    linhas = json.loads(saida.read_text(encoding="utf-8"))
    ids = [r.id for r in FileSource(DATA).fetch()]
    assert [linha["registro_id"] for linha in linhas] == ids
    assert all(
        linha
        == {
            "registro_id": linha["registro_id"],
            "e_desvio": False,
            "tipo": "nenhum",
            "responsavel": None,
            "clausula": None,
            "nota": "",
        }
        for linha in linhas
    )


def test_gabarito_rotulado_do_slack(script, tmp_path: Path):
    saida = tmp_path / "gab.json"
    script.main(["--pasta", str(DATA), "--saida", str(saida), "--rotular-slack"])
    linhas = json.loads(saida.read_text(encoding="utf-8"))
    registros = {r.id: r for r in FileSource(DATA).fetch()}
    desvios = [linha for linha in linhas if linha["e_desvio"]]
    assert {linha["tipo"] for linha in desvios} == {
        "escopo_extra",
        "prazo_sla",
        "terceiro_sem_documento",
    }
    assert len(desvios) == 3
    por_tipo = {linha["tipo"]: linha for linha in desvios}
    assert por_tipo["escopo_extra"]["responsavel"] == "gestor"
    assert por_tipo["prazo_sla"]["responsavel"] == "comercial"
    assert por_tipo["terceiro_sem_documento"]["responsavel"] == "administrativo_contratos"
    assert "a gente faz" in registros[por_tipo["escopo_extra"]["registro_id"]].texto
    iscas = [linha for linha in linhas if linha["nota"].startswith("ISCA")]
    assert len(iscas) == 5
    assert all(not linha["e_desvio"] and linha["tipo"] == "nenhum" for linha in iscas)
    assert len(linhas) == len(registros)


def test_gabarito_completo_tem_os_4_desvios_e_as_clausulas_do_indice(script, tmp_path: Path):
    saida = tmp_path / "gab.json"
    script.main(["--pasta", str(DATA), "--saida", str(saida), "--rotular-tudo"])
    linhas = json.loads(saida.read_text(encoding="utf-8"))
    registros = {r.id: r for r in FileSource(DATA).fetch()}
    assert len(linhas) == len(registros)
    desvios = [linha for linha in linhas if linha["e_desvio"]]
    assert len(desvios) == 4
    por_tipo = {linha["tipo"]: linha for linha in desvios}
    assert set(por_tipo) == {
        "escopo_extra",
        "prazo_sla",
        "terceiro_sem_documento",
        "promessa_fora_do_contrato",
    }
    # O desvio 4 vem da reunião e vai para o administrativo de contratos.
    promessa = por_tipo["promessa_fora_do_contrato"]
    assert registros[promessa["registro_id"]].origem.value == "reuniao"
    assert "treinamento presencial" in registros[promessa["registro_id"]].texto
    assert promessa["responsavel"] == "administrativo_contratos"
    # As cláusulas usam o número do título (`### N`), o mesmo do índice: nunca "3.1".
    assert por_tipo["prazo_sla"]["clausula"] == "3"
    for linha in desvios:
        assert linha["clausula"] in linha["clausulas_aceitas"]
    # Documentos são evidência: não são desvio e explicam o porquê.
    docs = [
        linha for linha in linhas if registros[linha["registro_id"]].origem.value == "documento"
    ]
    assert docs and all(not d["e_desvio"] and d["nota"] for d in docs)
