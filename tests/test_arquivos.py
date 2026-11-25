"""G-02: FileSource, ids determinísticos, fuso e contexto_de."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from radar.core.models import Consulta, Origem, Registro
from radar.core.ports import Fonte
from radar.fontes import arquivos
from radar.fontes.arquivos import FUSO, FileSource, contexto_de, gerar_id

BASE = datetime(2026, 11, 25, 12, 0, tzinfo=FUSO)


def reg(minuto: int, texto: str, canal: str = "C1", thread: str | None = None) -> Registro:
    data = BASE + timedelta(minutes=minuto)
    meta = {"canal": canal}
    if thread:
        meta["thread_id"] = thread
    return Registro(
        id=gerar_id("slack", texto, data),
        origem=Origem.slack,
        data=data,
        autor="ana",
        texto=texto,
        metadados=meta,
    )


def parser_de_teste(caminho: Path) -> list[Registro]:
    # propositalmente fora de ordem
    return [reg(30, "c"), reg(0, "a"), reg(10, "b")]


@pytest.fixture
def pasta(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "slack_export.json").write_text("[]", encoding="utf-8")
    (tmp_path / "gabarito.json").write_text("{}", encoding="utf-8")
    (tmp_path / "contrato_alfa.md").write_text("# contrato", encoding="utf-8")
    (tmp_path / "cache").mkdir()
    (tmp_path / "cache" / "x.vtt").write_text("WEBVTT", encoding="utf-8")
    monkeypatch.setitem(arquivos.PARSERS, "slack_export.json", parser_de_teste)
    return tmp_path


def test_cumpre_a_porta_fonte(pasta: Path) -> None:
    fonte = FileSource(pasta)
    assert isinstance(fonte, Fonte)
    assert fonte.status()["existe"] is True


def test_parsers_vazios_por_padrao(tmp_path: Path) -> None:
    (tmp_path / "reuniao.vtt").write_text("WEBVTT", encoding="utf-8")
    (tmp_path / "emails").mkdir()
    (tmp_path / "emails" / "a.eml").write_text("x", encoding="utf-8")
    assert FileSource(tmp_path).fetch(Consulta()) == []


def test_ordena_por_data(pasta: Path) -> None:
    textos = [r.texto for r in FileSource(pasta).fetch(Consulta())]
    assert textos == ["a", "b", "c"]


def test_ids_estaveis_em_duas_execucoes(pasta: Path) -> None:
    fonte = FileSource(pasta)
    ids1 = [r.id for r in fonte.fetch(Consulta())]
    ids2 = [r.id for r in FileSource(pasta).fetch(Consulta())]
    assert ids1 == ids2
    assert len(set(ids1)) == 3
    assert gerar_id("slack", "oi", BASE) == gerar_id("slack", "oi", BASE)
    assert gerar_id("slack", "oi", BASE).startswith("slack:")
    assert len(gerar_id("slack", "oi", BASE).split(":")[1]) == 12


def test_filtros_desde_ate_limite(pasta: Path) -> None:
    fonte = FileSource(pasta)
    desde = BASE + timedelta(minutes=5)
    assert [r.texto for r in fonte.fetch(Consulta(desde=desde))] == ["b", "c"]
    ate = BASE + timedelta(minutes=10)
    assert [r.texto for r in fonte.fetch(Consulta(ate=ate))] == ["a", "b"]
    assert [r.texto for r in fonte.fetch(Consulta(limite=2))] == ["b", "c"]
    janela = Consulta(desde=desde, ate=ate)
    assert [r.texto for r in fonte.fetch(janela)] == ["b"]


def test_escopo_filtra_por_canal(tmp_path: Path) -> None:
    (tmp_path / "slack_export.json").write_text("[]", encoding="utf-8")
    parsers = {"slack_export.json": lambda p: [reg(0, "a", "C1"), reg(1, "b", "C2")]}
    fonte = FileSource(tmp_path, parsers=parsers)
    assert [r.texto for r in fonte.fetch(Consulta(escopo="C2"))] == ["b"]


def test_parsers_sao_plugaveis_por_extensao(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "reuniao.vtt").write_text("WEBVTT", encoding="utf-8")
    monkeypatch.setitem(arquivos.PARSERS, ".vtt", lambda p: [reg(0, p.name)])
    assert [r.texto for r in FileSource(tmp_path).fetch(Consulta())] == ["reuniao.vtt"]


def test_ignora_arquivos_sem_parser_e_cache(pasta: Path) -> None:
    # `cache/x.vtt` teria parser, mas a pasta cache/ é ignorada; gabarito/contrato não têm
    chamados: list[str] = []

    def espiao(caminho: Path) -> list[Registro]:
        chamados.append(caminho.name)
        return []

    FileSource(pasta, parsers={".vtt": espiao, ".md": espiao, "gabarito.json": espiao}).fetch(
        Consulta()
    )
    assert chamados == []


def test_datas_saem_com_fuso_sao_paulo(tmp_path: Path) -> None:
    (tmp_path / "slack_export.json").write_text("[]", encoding="utf-8")
    utc = Registro(
        id="x:1",
        origem=Origem.slack,
        data=datetime(2026, 11, 25, 15, 0, tzinfo=UTC),
        autor="a",
        texto="t",
    )
    ingenuo = utc.model_copy(update={"id": "x:2", "data": datetime(2026, 11, 25, 9, 0)})
    fonte = FileSource(tmp_path, parsers={"slack_export.json": lambda p: [utc, ingenuo]})
    r_ingenuo, r_utc = fonte.fetch(Consulta())
    assert r_ingenuo.id == "x:2" and r_utc.id == "x:1"
    assert r_ingenuo.data.tzinfo == FUSO and r_utc.data.tzinfo == FUSO
    assert r_ingenuo.data.hour == 9  # sem fuso: assume São Paulo
    assert r_utc.data.hour == 12  # 15h UTC = 12h em São Paulo
    assert r_utc.data == utc.data  # mesmo instante


def test_contexto_de_sem_thread_usa_o_canal() -> None:
    regs = [
        reg(0, "a"),
        reg(1, "x", canal="C2"),
        reg(2, "b"),
        reg(3, "c"),
        reg(4, "d"),
        reg(5, "e"),
    ]
    alvo = regs[-1]
    assert [r.texto for r in contexto_de(regs, alvo)] == ["b", "c", "d"]  # 3 anteriores, em ordem
    assert [r.texto for r in contexto_de(regs, alvo, n=10)] == ["a", "b", "c", "d"]
    assert alvo not in contexto_de(regs, alvo)
    assert contexto_de(regs, regs[0]) == []  # nada antes


def test_contexto_de_com_thread_so_da_mesma_thread() -> None:
    regs = [
        reg(0, "solto"),
        reg(1, "pai", thread="T1"),
        reg(2, "outra", thread="T2"),
        reg(3, "resp1", thread="T1"),
        reg(4, "resp2", thread="T1"),
    ]
    assert [r.texto for r in contexto_de(regs, regs[-1])] == ["pai", "resp1"]
    assert [r.texto for r in contexto_de(regs, regs[-1], n=1)] == ["resp1"]
