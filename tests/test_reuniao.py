"""J-09 / G-09: reunião .vtt e parser."""

import os
from datetime import datetime
from pathlib import Path

from radar.core.models import Origem
from radar.fontes import arquivos
from radar.fontes.arquivos import FUSO, FileSource
from radar.fontes.reuniao import ler_vtt

DATA = Path(__file__).resolve().parent.parent / "data"
REUNIAO = DATA / "reuniao_alfa.vtt"
PROMESSA = "a gente inclui um treinamento presencial pra equipe de vocês, sem custo"

VTT = """WEBVTT
NOTE data: 2027-01-21

00:00:05.000 --> 00:00:12.000
<v Marcos Lima>Primeira fala.

00:01:02.500 --> 00:01:08.000
<v Ana Souza>Segunda fala, de outra pessoa.

00:01:10.000 --> 00:01:15.000
<v Bruno Siqueira>A gente inclui um treinamento presencial

00:01:15.500 --> 00:01:20.000
<v Bruno Siqueira>pra equipe de vocês, sem custo.
"""


def escrever(tmp_path: Path, conteudo: str, nome: str = "reuniao_teste.vtt") -> Path:
    caminho = tmp_path / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def test_data_com_fuso_autor_e_metadados(tmp_path: Path) -> None:
    primeiro, segundo, *_ = ler_vtt(escrever(tmp_path, VTT))
    assert primeiro.data == datetime(2027, 1, 21, 0, 0, 5, tzinfo=FUSO)
    assert primeiro.data.utcoffset().total_seconds() == -3 * 3600
    assert segundo.data == datetime(2027, 1, 21, 0, 1, 2, 500000, tzinfo=FUSO)
    assert primeiro.autor == "Marcos Lima"
    assert primeiro.texto == "Primeira fala."
    assert primeiro.origem == Origem.reuniao
    assert primeiro.link is None
    assert primeiro.metadados == {"canal": "reuniao_teste", "inicio": "00:00:05"}


def test_junta_falas_seguidas_da_mesma_pessoa(tmp_path: Path) -> None:
    registros = ler_vtt(escrever(tmp_path, VTT))
    assert [r.autor for r in registros] == ["Marcos Lima", "Ana Souza", "Bruno Siqueira"]
    ultimo = registros[-1]
    assert ultimo.texto == (
        "A gente inclui um treinamento presencial pra equipe de vocês, sem custo."
    )
    assert ultimo.metadados["inicio"] == "00:01:10"
    assert ultimo.data == datetime(2027, 1, 21, 0, 1, 10, tzinfo=FUSO)


def test_autor_no_formato_nome_dois_pontos(tmp_path: Path) -> None:
    conteudo = (
        "WEBVTT\nNOTE data: 2027-01-21\n\n"
        "00:00:01.000 --> 00:00:03.000\nHelena Prado: Vamos começar.\n\n"
        "00:00:04.000 --> 00:00:06.000\nHelena Prado: Primeiro ponto.\n\n"
        "00:00:07.000 --> 00:00:09.000\nMarcos Lima: Certo.\n"
    )
    registros = ler_vtt(escrever(tmp_path, conteudo))
    assert [(r.autor, r.texto) for r in registros] == [
        ("Helena Prado", "Vamos começar. Primeiro ponto."),
        ("Marcos Lima", "Certo."),
    ]


def test_ids_deterministicos_e_ordenados(tmp_path: Path) -> None:
    caminho = escrever(tmp_path, VTT)
    a, b = ler_vtt(caminho), ler_vtt(caminho)
    assert [r.id for r in a] == [r.id for r in b]
    assert len({r.id for r in a}) == len(a)
    assert all(r.id.startswith("reuniao:") for r in a)
    assert [r.data for r in a] == sorted(r.data for r in a)


def test_sem_note_usa_data_de_modificacao_do_arquivo(tmp_path: Path) -> None:
    conteudo = "WEBVTT\n\n00:00:10.000 --> 00:00:12.000\n<v Marcos Lima>Oi.\n"
    caminho = escrever(tmp_path, conteudo)
    os.utime(caminho, (0, datetime(2027, 3, 4, 15, 0, tzinfo=FUSO).timestamp()))
    (registro,) = ler_vtt(caminho)
    assert registro.data == datetime(2027, 3, 4, 0, 0, 10, tzinfo=FUSO)


def test_arquivo_real_tem_a_promessa_inteira_em_um_registro() -> None:
    registros = ler_vtt(REUNIAO)
    com_promessa = [r for r in registros if PROMESSA in r.texto]
    assert len(com_promessa) == 1
    promessa = com_promessa[0]
    assert promessa.autor == "Bruno Siqueira"
    assert promessa.data.date().isoformat() == "2027-01-21"
    assert promessa.origem == Origem.reuniao
    assert promessa.metadados["canal"] == "reuniao_alfa"


def test_arquivo_real_sem_palavras_proibidas_e_com_falas_neutras() -> None:
    registros = ler_vtt(REUNIAO)
    assert len(registros) >= 10
    for r in registros:
        texto = r.texto.lower()
        assert not any(p in texto for p in ("desvio", "contrato", "cláusula", "clausula"))
    assert {"Marcos Lima", "Patrícia Souza", "Helena Prado", "Bruno Siqueira"} == {
        r.autor for r in registros
    }
    assert any("registrar a ata" in r.texto for r in registros if r.autor == "Helena Prado")


def test_file_source_na_pasta_data_devolve_a_reuniao() -> None:
    assert arquivos.PARSERS[".vtt"] is not arquivos._vazio
    registros = FileSource(DATA).fetch()
    da_reuniao = [r for r in registros if r.origem == Origem.reuniao]
    assert da_reuniao == ler_vtt(REUNIAO)
    assert [r.data for r in registros] == sorted(r.data for r in registros)
