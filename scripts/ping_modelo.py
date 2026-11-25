"""Teste de fumaça: chama o modelo de triagem e imprime a resposta e os tokens.

Uso: python scripts/ping_modelo.py   (precisa de ANTHROPIC_API_KEY no .env)
"""

from dotenv import load_dotenv

load_dotenv()

import anthropic  # noqa: E402

from radar.config import MODELO_TRIAGEM  # noqa: E402


def main() -> None:
    resposta = anthropic.Anthropic().messages.create(
        model=MODELO_TRIAGEM,
        max_tokens=20,
        messages=[{"role": "user", "content": "responda apenas ok"}],
    )
    print(resposta.content[0].text)
    print(f"tokens de entrada: {resposta.usage.input_tokens}")
    print(f"tokens de saída: {resposta.usage.output_tokens}")


if __name__ == "__main__":
    main()