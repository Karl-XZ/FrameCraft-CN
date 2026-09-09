#!/usr/bin/env bash
# FrameCraft openJiuwen 多 Agent 依赖安装（macOS/Linux）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

say() {
  printf '\n=== %s ===\n' "$1"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

ensure_node_pm() {
  if command -v npm >/dev/null 2>&1; then
    echo "npm"
    return
  fi
  if command -v bun >/dev/null 2>&1; then
    echo "bun"
    return
  fi
  echo "Neither npm nor bun is available" >&2
  exit 1
}

PM="$(ensure_node_pm)"
PYTHON_BIN="${FRAMECRAFT_PYTHON:-python3.11}"
need_cmd "$PYTHON_BIN"

say "Backend Python venv"
if [[ ! -x backend/venv-openjiuwen/bin/python ]]; then
  "$PYTHON_BIN" -m venv backend/venv-openjiuwen
fi
backend/venv-openjiuwen/bin/python -m pip install -q --upgrade pip
backend/venv-openjiuwen/bin/python -m pip install -q -r backend/requirements.txt
if [[ "${FRAMECRAFT_SKIP_PLAYWRIGHT_INSTALL:-0}" != "1" ]]; then
  backend/venv-openjiuwen/bin/python -m playwright install chromium
fi
PYTHONPATH=backend backend/venv-openjiuwen/bin/python -c "import app.main; print('OK openJiuwen multi-agent backend deps')"

say "Frontend deps"
if [[ "$PM" == "npm" ]]; then
  npm install
  (cd framecraft-agent && npm install)
else
  bun install
  (cd framecraft-agent && bun install)
fi

say "HyperFrames doctor"
if [[ "${FRAMECRAFT_SKIP_HYPERFRAMES_DOCTOR:-0}" == "1" ]]; then
  echo "SKIP hyperframes doctor"
elif [[ -x "$ROOT/node_modules/.bin/hyperframes" ]]; then
  (cd "$ROOT/../hyperframes" && "$ROOT/node_modules/.bin/hyperframes" doctor --json || true)
elif command -v npx >/dev/null 2>&1; then
  (cd "$ROOT/../hyperframes" && npx hyperframes doctor --json || true)
else
  echo "WARN npx not found; skip hyperframes doctor" >&2
fi

say "DeepSeek config"
if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "DEEPSEEK_API_KEY detected"
else
  echo "WARN DEEPSEEK_API_KEY not set. You can still save the key later in the web UI." >&2
fi

say "Done"
echo "Run scripts/verify-env.sh to check all components."
