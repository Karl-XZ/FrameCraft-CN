#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$ROOT/framecraft-agent"
HOST="${FRAMECRAFT_FRONTEND_HOST:-0.0.0.0}"
PORT="${FRAMECRAFT_FRONTEND_PORT:-4174}"

cd "$APP_DIR"
npm run build
exec npm run preview -- --host "$HOST" --port "$PORT"
