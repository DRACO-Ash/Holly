#!/bin/sh
# dev.sh :: run Holly locally with the dashboard: `sh scripts/dev.sh`.
# 1. Starts the local PostgreSQL (infra/docker-compose.yml) when Docker is available.
# 2. Applies the migrations, as the container does at start.
# 3. Runs the API on PORT or 8080 and the dashboard's dev server on http://127.0.0.1:3000,
#    which sends /api to the API. Ctrl-C stops both.
# Settings come from your shell or a local .env (docs/developer/setup.md lists them). The
# database password is read from the environment and never written anywhere by this script.
set -eu
cd "$(dirname "$0")/.."
BIN="${VENV:-.venv}/bin"

[ -x "$BIN/python" ] || { echo "No virtualenv: run the install command in CLAUDE.md first."; exit 1; }
[ -d frontend/node_modules ] || (cd frontend && npm ci --ignore-scripts --no-audit --no-fund)

# Procedures go under the checkout unless a store is configured; data/ is ignored by git.
export PROCEDURE_STORAGE_PATH="${PROCEDURE_STORAGE_PATH:-$(pwd)/data/procedures}"

if command -v docker >/dev/null 2>&1 && [ -n "${POSTGRES_PASSWORD:-}" ]; then
  docker compose -f infra/docker-compose.yml up -d --wait db
fi

PYTHONPATH=src "$BIN/python" -c "from app.migrate import run_migrations; run_migrations()"

PYTHONPATH=src "$BIN/python" -m app &
api=$!
trap 'kill "$api" 2>/dev/null || true' EXIT INT TERM
(cd frontend && npm run dev)
