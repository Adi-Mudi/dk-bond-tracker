#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

OUT="${1:-evidence/shot.png}"

if pgrep -f "waydroid show-full-u[i]" >/dev/null 2>&1; then
    echo "ui client already running"
else
    echo "starting ui client"
    setsid waydroid show-full-ui >/dev/null 2>&1 </dev/null &
fi

sleep 15

pgrep -f "waydroid show-full-u[i]" >/dev/null 2>&1 && echo "ui client up" || echo "ui client NOT up"

timeout 30 flameshot full -p "$OUT" 2>&1 | head -2
ls -la "$OUT" 2>&1
