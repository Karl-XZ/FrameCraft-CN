#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

./scripts/setup-deps.sh
HOST="${FRAMECRAFT_BACKEND_HOST:-0.0.0.0}"
PORT="${FRAMECRAFT_BACKEND_PORT:-8022}"

echo "[FrameCraft] Starting single-agent backend on http://${HOST}:${PORT}"
UVICORN_ARGS=(app.main:app --host "$HOST" --port "$PORT")
if [[ "${FRAMECRAFT_BACKEND_RELOAD:-0}" == "1" ]]; then
  UVICORN_ARGS+=(--reload --reload-exclude 'uploads/*' --reload-exclude 'outputs/*')
  UVICORN_ARGS+=(--reload-exclude "${FRAMECRAFT_RUNTIME_DIR:-/tmp/framecraft-agent-runtime}/*")
fi
PYTHONPATH=backend exec backend/venv/bin/python -m uvicorn "${UVICORN_ARGS[@]}"
