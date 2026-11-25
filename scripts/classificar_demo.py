"""Roda busca (ChromaDB) + classificação (modelo real) para um texto e imprime o resultado.

Uso: python scripts/classificar_demo.py "Oi Marcos! Claro, a gente faz o módulo de relatórios"
Precisa de ANTHROPIC_API_KEY no `.env`. Cada execução faz UMA chamada ao Sonnet.
"""

import os
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


def main() -> int:
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print('Uso: python scripts/classificar_demo.py "texto da mensagem"')
        return 2

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Falta ANTHROPIC_API_KEY. Copie .env.example para .env e preencha a chave.")
        return 1

    from radar import llm
    from radar.core.models import Origem, Registro
    from radar.nos.buscar import buscar_clausulas_do_registro
    from radar.nos.classificar import classificar_registro

    registro = Registro(
        id="demo:classificar",
        origem=Origem.slack,
        data=datetime.now(ZoneInfo("America/Sao_Paulo")),
        autor="Demo",
        texto=sys.argv[1],
    )
    clausulas = buscar_clausulas_do_registro(registro)
    print("Cláusulas recuperadas (RAG):")
    for c in clausulas:
        resumo = c["texto"][:90]
        print(f"  {c['numero']} ({c['tipo']}, distância {c['distancia']:.3f}): {resumo}...")

    alerta = classificar_registro(registro, clausulas)
    print("\nAlerta:")
    print(alerta.model_dump_json(indent=2))
    print(f"\nContadores do modelo: {llm.CONTADORES}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
