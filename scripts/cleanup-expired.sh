#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -x backend/venv/bin/python ]]; then
  ./scripts/setup-deps.sh >/dev/null
fi

PYTHONPATH=backend exec backend/venv/bin/python -m app.retention "$@"
