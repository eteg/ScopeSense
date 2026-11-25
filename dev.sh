#!/usr/bin/env bash
# Sobe a API (porta 8000) e a tela (porta 5173) juntas. Ctrl+C para as duas.
# Uso: ./dev.sh            (usa os dados que já estão no banco)
#      ./dev.sh --demo     (recria o banco com os 4 desvios do gabarito, sem o modelo)
#
# Python: usa o .venv do projeto se existir (crie com: python3 -m venv .venv &&
# .venv/bin/pip install -e ".[dev]"); senão, o ambiente ativo (ex.: conda).
# Node: usa ~/.local/node se existir; senão, o node do PATH.
set -euo pipefail
cd "$(dirname "$0")"

[[ -x .venv/bin/python ]] && export PATH="$PWD/.venv/bin:$PATH"
[[ -x "$HOME/.local/node/bin/node" ]] && export PATH="$HOME/.local/node/bin:$PATH"

command -v uvicorn >/dev/null || {
  echo "uvicorn não encontrado. Crie o ambiente: python3 -m venv .venv && .venv/bin/pip install -e '.[dev]'" >&2
  exit 1
}
command -v npm >/dev/null || { echo "npm não encontrado. Instale o Node 20+ (veja o README)." >&2; exit 1; }

[[ "${1:-}" == "--demo" ]] && python -m radar.demo --limpar
[[ -d web/node_modules ]] || (cd web && npm install)

trap 'kill 0' EXIT
uvicorn radar.api.app:app --port 8000 --reload &
(cd web && npm run dev) &
wait
