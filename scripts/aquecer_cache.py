"""G-12: roda o fluxo ensaiado uma vez para encher o cache das respostas do modelo.

Passa todas as mensagens do gabarito e as 3 frases da demo por `radar.pipeline.analisar`, com o
cache LIGADO (grava) e `MODO_DEMO` DESLIGADO (para chamar o modelo de verdade). Depois disso, com
`MODO_DEMO=1`, a demo roda igual mesmo sem chave da API ou com a API lenta.

ATENCAO: chama o modelo (custa). Rode uma vez, depois de o prompt estar final.

Uso: python scripts/aquecer_cache.py   (precisa de ANTHROPIC_API_KEY no .env)
"""

import json
import os
import sys
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from radar import cache_llm, config, llm  # noqa: E402
from radar.core.models import Origem, Registro  # noqa: E402
from radar.fontes.arquivos import FUSO, FileSource, contexto_de, gerar_id  # noqa: E402

FRASES_DEMO = [
    "pode incluir o módulo de relatórios sem custo, a gente resolve",
    "o João da Nimbus começa amanhã no cliente",
    "o aditivo do módulo de integração foi assinado, podemos seguir",
]


def registros_da_demo(base: list[Registro]) -> list[Registro]:
    """As 3 frases da demo como registros do Slack, no canal e depois da última mensagem da base."""
    slack = [r for r in base if r.origem == Origem.slack]
    canal = slack[-1].canal if slack else None
    ultima = max((r.data for r in base), default=datetime(2027, 1, 1, tzinfo=FUSO))
    registros = []
    for i, frase in enumerate(FRASES_DEMO, start=1):
        data = ultima.replace(microsecond=0) + timedelta(minutes=i)
        registros.append(
            Registro(
                id=gerar_id("slack", frase, data),
                origem=Origem.slack,
                data=data,
                autor="Demo",
                texto=frase,
                metadados={"canal": canal} if canal else {},
            )
        )
    return registros


def _ids_do_gabarito(pasta: Path) -> set[str]:
    texto = (pasta / "gabarito.json").read_text(encoding="utf-8")
    return {linha["registro_id"] for linha in json.loads(texto)}


def aquecer(
    analisar: Callable | None = None,
    pasta: str | Path = "data",
    caminho: str | Path | None = None,
) -> dict[str, int]:
    """Enche o cache. Devolve `{"registros", "erros", "chamadas", "no_cache"}`."""
    if analisar is None:
        from radar.pipeline import analisar  # import preguiçoso: carrega RAG e modelos

    pasta = Path(pasta)
    base = FileSource(pasta).fetch()
    no_gabarito = _ids_do_gabarito(pasta)
    registros = [r for r in base if r.id in no_gabarito] + registros_da_demo(base)

    cache_llm.ativar_cache_sqlite(caminho)
    antes = dict(llm.CONTADORES)
    demo_antes = config.MODO_DEMO
    config.MODO_DEMO = False  # o aquecimento tem que chamar o modelo, não ler o cache
    erros = 0
    try:
        for registro in registros:
            try:
                analisar(registro, contexto_de(base, registro))
            except Exception as erro:  # noqa: BLE001 - um registro ruim não derruba o aquecimento
                erros += 1
                print(f"  erro em {registro.id}: {erro}")
    finally:
        config.MODO_DEMO = demo_antes
    return {
        "registros": len(registros),
        "erros": erros,
        "chamadas": llm.CONTADORES["chamadas"] - antes["chamadas"],
        "no_cache": cache_llm.cache_cheio(caminho),
    }


def main() -> int:
    if not os.environ.get("ANTHROPIC_API_KEY", "").strip():
        print("ANTHROPIC_API_KEY não encontrada. Preencha o .env e rode de novo.", file=sys.stderr)
        return 1
    print("Aquecendo o cache: isto chama o modelo (custa).")
    resumo = aquecer()
    print(f"Registros processados: {resumo['registros']} (erros: {resumo['erros']})")
    print(f"Chamadas ao modelo nesta rodada: {resumo['chamadas']}")
    print(f"Respostas guardadas no cache: {resumo['no_cache']}")
    return 1 if resumo["erros"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
