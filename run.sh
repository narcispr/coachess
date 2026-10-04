#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"
if [[ ! -x .venv/bin/python ]]; then
    echo "Falta .venv. Segueix els passos d'instal·lació del README." >&2
    exit 1
fi
printf 'Obre http://127.0.0.1:5000 al navegador. Ctrl+C per aturar.\n'
exec .venv/bin/python -m flask --app coachess run "$@"
