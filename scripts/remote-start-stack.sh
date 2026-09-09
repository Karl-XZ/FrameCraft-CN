#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNTIME_DIR="$ROOT/.runtime"
LOG_DIR="$RUNTIME_DIR/logs"
PID_DIR="$RUNTIME_DIR/pids"

mkdir -p "$LOG_DIR" "$PID_DIR"

BACKEND_HOST="${FRAMECRAFT_BACKEND_HOST:-127.0.0.1}"
BACKEND_PORT="${FRAMECRAFT_BACKEND_PORT:-8022}"
FRONTEND_HOST="${FRAMECRAFT_FRONTEND_HOST:-127.0.0.1}"
FRONTEND_PORT="${FRAMECRAFT_FRONTEND_PORT:-4174}"

stop_pid_file() {
  local file="$1"
  if [[ -f "$file" ]]; then
    local pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
      sleep 1
    fi
    rm -f "$file"
  fi
}

stop_pid_file "$PID_DIR/backend.pid"
stop_pid_file "$PID_DIR/frontend.pid"

(
  cd "$ROOT"
  nohup env \
    FRAMECRAFT_BACKEND_HOST="$BACKEND_HOST" \
    FRAMECRAFT_BACKEND_PORT="$BACKEND_PORT" \
    ./scripts/start-backend.sh \
    >"$LOG_DIR/backend.log" 2>&1 &
  echo $! >"$PID_DIR/backend.pid"
)

(
  cd "$ROOT"
  nohup env \
    FRAMECRAFT_FRONTEND_HOST="$FRONTEND_HOST" \
    FRAMECRAFT_FRONTEND_PORT="$FRONTEND_PORT" \
    ./scripts/start-frontend-preview.sh \
    >"$LOG_DIR/frontend.log" 2>&1 &
  echo $! >"$PID_DIR/frontend.pid"
)

echo "backend pid: $(cat "$PID_DIR/backend.pid")"
echo "frontend pid: $(cat "$PID_DIR/frontend.pid")"
echo "backend log: $LOG_DIR/backend.log"
echo "frontend log: $LOG_DIR/frontend.log"
