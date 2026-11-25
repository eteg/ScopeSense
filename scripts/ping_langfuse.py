"""Teste de fumaça do Langfuse: cria o traço "teste" com uma generation de exemplo e envia.

Uso: python scripts/ping_langfuse.py   (precisa das chaves LANGFUSE_* no .env)
"""

import sys

from dotenv import load_dotenv

load_dotenv()

from radar import observabilidade as obs  # noqa: E402


@obs.observar("teste")
def traco_de_teste() -> str:
    obs._observador_llm({
        "modelo": "claude-haiku-5-5", "schema": "ping", "cache": False,
        "system": "Responda apenas ok.", "user": "ping", "saida": {"resposta": "ok"},
        "usage": {"input_tokens": 12, "output_tokens": 2}, "segundos": 0.4, "tentativa": 1,
    })  # fmt: skip
    obs.marcar_traco("teste", origem="ping_langfuse")
    return obs.url_do_traco() or ""


def main() -> int:
    if not obs.ativar_langfuse():
        print("Langfuse desligado. Preencha no .env: " + ", ".join(obs.variaveis_faltando()))
        return 1
    url = traco_de_teste()
    obs.flush()
    print("traço enviado" + (f": {url}" if url else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
