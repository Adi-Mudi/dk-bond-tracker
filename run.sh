#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ "${1:-}" = "--import" ]; then
  if [ ! -f data/bonds.db ] && [ -f "v5.5_40L_Project_Tracker.xlsm" ]; then
    .venv/bin/python src/app.py --import "v5.5_40L_Project_Tracker.xlsm" --db data/bonds.db
  else
    echo "import skipped: data/bonds.db already exists (delete it first to re-import)"
  fi
fi
exec .venv/bin/python src/app.py --db data/bonds.db
