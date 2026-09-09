#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_DIR="$ROOT/.runtime/pids"

stop_pid_file() {
  local file="$1"
  if [[ ! -f "$file" ]]; then
    return
  fi
  local pid
  pid="$(cat "$file" 2>/dev/null || true)"
  if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
    kill "$pid" 2>/dev/null || true
  fi
  rm -f "$file"
}

stop_pid_file "$PID_DIR/frontend.pid"
stop_pid_file "$PID_DIR/backend.pid"

echo "stack stopped"
