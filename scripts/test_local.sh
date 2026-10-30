#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
PY=".venv/bin/python"
if [ ! -x "$PY" ]; then
  PY="python3"
fi
exec "$PY" -m pytest tests -q -m "not remote"
