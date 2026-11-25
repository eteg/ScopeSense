"""API local do Radar.

Carrega o .env no ambiente ANTES de qualquer `radar.*`: `radar.config` lê
DATABASE_PATH na importação, e o SDK da Anthropic lê ANTHROPIC_API_KEY do ambiente.
"""

from dotenv import load_dotenv

load_dotenv()
