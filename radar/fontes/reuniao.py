"""G-09: parser da reunião (`.vtt`) -> `Registro`.

Formato lido (J-09):

    WEBVTT
    NOTE data: 2027-01-21

    00:00:05.000 --> 00:00:12.000
    <v Marcos Lima>Texto da fala.

- Data de cada fala = `NOTE data: AAAA-MM-DD` + horário de início do trecho, em
  America/Sao_Paulo. Sem a linha `NOTE data:`, usa a data de modificação do arquivo.
- Autor = prefixo `<v Nome>` (ou `Nome:`). Trecho sem autor fica como "Desconhecido".
- Trechos seguidos da mesma pessoa viram UM registro (uma frase partida entre dois trechos
  não pode sumir da análise). A data e o `inicio` são os do primeiro trecho.
"""

import re
from datetime import date, datetime, time
from pathlib import Path

from radar.core.models import Origem, Registro
from radar.fontes.arquivos import FUSO, gerar_id

_NOTE_DATA = re.compile(r"^NOTE\s+data:\s*(\d{4}-\d{2}-\d{2})\s*$", re.IGNORECASE)
_TEMPO = re.compile(
    r"^(?:(\d{1,2}):)?(\d{2}):(\d{2})(?:[.,](\d{1,3}))?\s*-->\s*(?:(?:\d{1,2}:)?\d{2}:\d{2}(?:[.,]\d{1,3})?)"
)
_VOZ = re.compile(r"^<v(?:\.[^\s>]+)?\s+([^>]+)>")
_TAG = re.compile(r"</?[^>]+>")
_NOME_DOIS_PONTOS = re.compile(r"^([^\W\d_][^:\n]{0,60}?):\s+(.+)$", re.DOTALL)

AUTOR_PADRAO = "Desconhecido"


def _inicio(m: re.Match[str]) -> time:
    horas, minutos, segundos, fracao = m.groups()
    micro = int((fracao or "0").ljust(3, "0")) * 1000
    return time(int(horas or 0), int(minutos), int(segundos), micro)


def _autor_e_texto(linhas: list[str]) -> tuple[str, str]:
    bruto = " ".join(linha.strip() for linha in linhas if linha.strip())
    voz = _VOZ.match(bruto)
    if voz:
        autor = voz.group(1).strip()
        resto = bruto[voz.end() :]
    else:
        dois_pontos = _NOME_DOIS_PONTOS.match(bruto)
        if dois_pontos:
            autor, resto = dois_pontos.group(1).strip(), dois_pontos.group(2)
        else:
            autor, resto = AUTOR_PADRAO, bruto
    return autor, " ".join(_TAG.sub("", resto).split())


def ler_vtt(caminho: str | Path) -> list[Registro]:
    """Lê uma transcrição `.vtt` e devolve um `Registro` por fala (falas seguidas da mesma
    pessoa são juntadas), em ordem cronológica."""
    caminho = Path(caminho)
    texto = caminho.read_text(encoding="utf-8-sig")
    blocos = re.split(r"\r?\n\s*\r?\n", texto.strip())

    dia: date | None = None
    falas: list[tuple[time, str, str]] = []  # (início, autor, texto)
    for bloco in blocos:
        linhas = bloco.splitlines()
        # a data vem no cabeçalho ou em um bloco NOTE
        for linha in linhas:
            nota = _NOTE_DATA.match(linha.strip())
            if nota and dia is None:
                dia = date.fromisoformat(nota.group(1))
        idx = next((i for i, linha in enumerate(linhas) if _TEMPO.match(linha.strip())), None)
        if idx is None:
            continue
        tempo = _TEMPO.match(linhas[idx].strip())
        assert tempo is not None
        autor, fala = _autor_e_texto(linhas[idx + 1 :])
        if fala:
            falas.append((_inicio(tempo), autor, fala))

    if dia is None:
        dia = datetime.fromtimestamp(caminho.stat().st_mtime, tz=FUSO).date()

    juntas: list[tuple[time, str, list[str]]] = []
    for inicio, autor, fala in falas:
        if juntas and juntas[-1][1] == autor:
            juntas[-1][2].append(fala)
        else:
            juntas.append((inicio, autor, [fala]))

    registros: list[Registro] = []
    for inicio, autor, partes in juntas:
        data = datetime.combine(dia, inicio, tzinfo=FUSO)
        fala = " ".join(partes)
        registros.append(
            Registro(
                id=gerar_id(Origem.reuniao, fala, data),
                origem=Origem.reuniao,
                data=data,
                autor=autor,
                texto=fala,
                link=None,
                metadados={"canal": caminho.stem, "inicio": inicio.strftime("%H:%M:%S")},
            )
        )
    registros.sort(key=lambda r: r.data)
    return registros
