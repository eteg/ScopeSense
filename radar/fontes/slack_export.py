"""Parser do export do Slack (G-03): cada mensagem vira um `Registro`.

`mensagem_para_registro` é a MESMA função que a escuta ao vivo (G-06) deve reutilizar, para as
duas versões não divergirem. `pessoas` é um dicionário `id do Slack -> nome` (ver
`carregar_pessoas`); ID desconhecido mantém o próprio ID.

Este módulo não importa `radar.fontes.arquivos` no topo (que o importa para registrar o
parser em `PARSERS`): `gerar_id` é importado dentro da função, para evitar import circular.
"""

import json
import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from radar.core.models import Origem, Registro

FUSO = ZoneInfo("America/Sao_Paulo")

_MENCAO = re.compile(r"<@([A-Za-z0-9_]+)(?:\|[^>]*)?>")


def carregar_pessoas(projeto_json: str | Path) -> dict[str, str]:
    """`id do Slack -> nome`, a partir de `papeis[*].slack_id` e `pessoas_sinteticas`."""
    dados = json.loads(Path(projeto_json).read_text(encoding="utf-8"))
    pessoas: dict[str, str] = {}
    for info in (dados.get("papeis") or {}).values():
        if info.get("slack_id") and info.get("nome"):
            pessoas[info["slack_id"]] = info["nome"]
    for slack_id, info in (dados.get("pessoas_sinteticas") or {}).items():
        if info.get("nome"):
            pessoas[slack_id] = info["nome"]
    return pessoas


def _nome(pessoas: dict[str, Any], user_id: str) -> str:
    info = pessoas.get(user_id, user_id)
    if isinstance(info, dict):
        info = info.get("nome") or user_id
    return str(info)


def ts_para_data(ts: str) -> datetime:
    """`"1768827600.000100"` -> datetime em America/Sao_Paulo (sem erro de float)."""
    valor = Decimal(str(ts))
    segundos = int(valor)
    micro = int((valor - segundos) * 1_000_000)
    base = datetime(1970, 1, 1, tzinfo=UTC) + timedelta(seconds=segundos, microseconds=micro)
    return base.astimezone(FUSO)


def mensagem_para_registro(msg: dict[str, Any], pessoas: dict[str, Any]) -> Registro:
    from radar.fontes.arquivos import gerar_id

    ts = str(msg["ts"])
    canal = msg.get("channel") or ""
    data = ts_para_data(ts)
    user_id = msg.get("user")
    autor = _nome(pessoas, user_id) if user_id else (msg.get("username") or "desconhecido")
    texto = _MENCAO.sub(lambda m: _nome(pessoas, m.group(1)), msg.get("text") or "")
    return Registro(
        id=gerar_id(Origem.slack, texto, data),
        origem=Origem.slack,
        data=data,
        autor=autor,
        texto=texto,
        link=f"slack://{canal}/{ts}",
        metadados={"canal": canal, "thread_id": msg.get("thread_ts")},
    )


def ler_export(caminho: str | Path, projeto_json: str | Path | None = None) -> list[Registro]:
    """Lê o export e devolve os registros; ignora bots, `subtype` e mensagens vazias.

    Sem `projeto_json`, usa `projeto_alfa.json` ao lado do export, se existir.
    """
    caminho = Path(caminho)
    if projeto_json is None:
        candidato = caminho.parent / "projeto_alfa.json"
        projeto_json = candidato if candidato.is_file() else None
    pessoas = carregar_pessoas(projeto_json) if projeto_json else {}

    mensagens = json.loads(caminho.read_text(encoding="utf-8"))
    return [
        mensagem_para_registro(msg, pessoas)
        for msg in mensagens
        if not msg.get("bot_id") and not msg.get("subtype") and (msg.get("text") or "").strip()
    ]
