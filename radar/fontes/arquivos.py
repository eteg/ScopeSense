"""Fonte de arquivos (plano B e base do eval): lê a pasta de dados e devolve `Registro`.

Implementa a porta `Fonte` de `radar/core/ports.py`. Como a pasta mistura origens
(Slack, reunião, e-mail, PDF), a `FileSource` expõe `origem = Origem.documento`; a origem
real de cada registro vem dentro do próprio `Registro`.

Para plugar um parser real (G-03, G-09, G-10, G-14), basta trocar a entrada em `PARSERS`:
a chave é o nome do arquivo (`"slack_export.json"`) ou a extensão (`".vtt"`), o valor é
`(caminho: Path) -> list[Registro]`. O nome do arquivo tem prioridade sobre a extensão.
Arquivos sem parser (contrato, projeto, gabarito, banco, cache) são simplesmente ignorados.
"""

import hashlib
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from radar.core.errors import FalhaNaFonte
from radar.core.models import Consulta, Origem, Registro
from radar.fontes.slack_export import ler_export

FUSO = ZoneInfo("America/Sao_Paulo")

Parser = Callable[[Path], list[Registro]]


def _vazio(caminho: Path) -> list[Registro]:
    """Stub: o parser real entra na issue indicada."""
    return []


# Os outros devs só trocam a entrada (ex.: PARSERS["slack_export.json"] = parse_slack).
PARSERS: dict[str, Parser] = {
    "slack_export.json": ler_export,  # G-03
    ".vtt": _vazio,  # G-09
    ".eml": _vazio,  # G-14
    ".pdf": _vazio,  # G-10
}

# Nunca viram evidência, mesmo que um dia exista um parser para a extensão.
IGNORADOS = frozenset({"contrato_alfa.md", "projeto_alfa.json", "gabarito.json", "radar.db"})
PASTAS_IGNORADAS = frozenset({"cache"})


def gerar_id(origem: str, texto: str, data: datetime) -> str:
    """Id determinístico (nunca aleatório: o gabarito do eval depende dele)."""
    origem = str(origem)
    digest = hashlib.sha1((origem + texto + data.isoformat()).encode("utf-8")).hexdigest()
    return f"{origem}:{digest[:12]}"


def para_fuso(data: datetime) -> datetime:
    """Converte para America/Sao_Paulo; data sem fuso é tratada como já estando nele."""
    if data.tzinfo is None:
        return data.replace(tzinfo=FUSO)
    return data.astimezone(FUSO)


class FileSource:
    """Lê uma pasta de dados e devolve os registros em ordem cronológica."""

    origem = Origem.documento

    def __init__(self, pasta: str | Path, parsers: dict[str, Parser] | None = None) -> None:
        self.pasta = Path(pasta)
        self._parsers = parsers  # None = usa o PARSERS do módulo (lido a cada fetch)

    def status(self) -> dict[str, Any]:
        parsers = PARSERS if self._parsers is None else self._parsers
        return {
            "pasta": str(self.pasta),
            "existe": self.pasta.is_dir(),
            "parsers": sorted(parsers),
        }

    def fetch(self, consulta: Consulta | None = None) -> list[Registro]:
        """Registros ordenados por data.

        Respeita `desde`, `ate` e `limite` (os `limite` mais recentes, como a fonte do Slack).
        `escopo`, se vier, filtra pelo canal (`registro.canal`).
        """
        consulta = consulta or Consulta()
        registros = [para_registro_no_fuso(r) for r in self._ler_tudo()]
        if consulta.escopo:
            registros = [r for r in registros if r.canal == consulta.escopo]
        if consulta.desde:
            registros = [r for r in registros if r.data >= para_fuso(consulta.desde)]
        if consulta.ate:
            registros = [r for r in registros if r.data <= para_fuso(consulta.ate)]
        registros.sort(key=lambda r: r.data)
        return registros[-consulta.limite :]

    # --- internos ---------------------------------------------------------

    def _ler_tudo(self) -> list[Registro]:
        if not self.pasta.is_dir():
            raise FalhaNaFonte(f"Pasta de dados não encontrada: {self.pasta}")
        parsers = PARSERS if self._parsers is None else self._parsers
        registros: list[Registro] = []
        for caminho in sorted(self.pasta.rglob("*")):
            if not caminho.is_file() or caminho.name in IGNORADOS:
                continue
            relativo = caminho.relative_to(self.pasta)
            if PASTAS_IGNORADAS.intersection(relativo.parts[:-1]):
                continue
            parser = parsers.get(caminho.name) or parsers.get(caminho.suffix.lower())
            if parser is not None:
                registros.extend(parser(caminho))
        return registros


def para_registro_no_fuso(registro: Registro) -> Registro:
    return registro.model_copy(update={"data": para_fuso(registro.data)})


def contexto_de(registros: list[Registro], registro: Registro, n: int = 3) -> list[Registro]:
    """Até `n` registros anteriores (por data) do mesmo canal, em ordem cronológica.

    Se `registro.thread_id` existir, só entram os da mesma thread. Não inclui o próprio.
    """
    anteriores = [
        r
        for r in registros
        if r.id != registro.id
        and r.data < registro.data
        and r.canal == registro.canal
        and (registro.thread_id is None or r.thread_id == registro.thread_id)
    ]
    anteriores.sort(key=lambda r: r.data)
    return anteriores[-n:] if n > 0 else []
