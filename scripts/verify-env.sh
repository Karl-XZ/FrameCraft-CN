#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== FrameCraft openJiuwen Env Check ==="
echo "Root: $ROOT"
echo

for cmd in python3 git; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "OK  $cmd -> $(command -v "$cmd")"
  else
    echo "MISS $cmd"
  fi
done

if command -v node >/dev/null 2>&1; then
  echo "OK  node $(node --version)"
else
  echo "MISS node"
fi

if command -v npm >/dev/null 2>&1; then
  echo "OK  npm $(npm --version)"
elif command -v bun >/dev/null 2>&1; then
  echo "OK  bun $(bun --version)"
else
  echo "MISS npm/bun"
fi

if [[ -x backend/venv-openjiuwen/bin/python ]]; then
  echo "OK  backend openJiuwen venv"
  backend/venv-openjiuwen/bin/python -c "import openjiuwen; print('OK  openJiuwen import')"
else
  echo "MISS backend/venv-openjiuwen"
fi

if [[ -d ../hyperframes ]]; then
  echo "OK  hyperframes repo -> $(cd ../hyperframes && pwd)"
else
  echo "MISS hyperframes repo"
fi

for cmd in ffmpeg ffprobe; do
  if command -v "$cmd" >/dev/null 2>&1; then
    echo "OK  $cmd -> $(command -v "$cmd")"
  else
    echo "WARN $cmd"
  fi
done

if [[ -n "${DEEPSEEK_API_KEY:-}" ]]; then
  echo "OK  DEEPSEEK_API_KEY is set"
else
  echo "WARN DEEPSEEK_API_KEY not set"
fi

echo
echo "=== Done ==="
