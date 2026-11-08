#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")"

OUT="${1:-evidence/_probe2.png}"
APP_PKG="${2:-com.dkbondtracker.spike}"

UI_RE='python3? /usr/bin/waydroid show-full-ui'

pkill -f "$UI_RE" 2>/dev/null
sleep 3
pgrep -af "$UI_RE" >/dev/null 2>&1 && echo "WARN: ui still present" || echo "ui not running"

setsid waydroid show-full-ui >/dev/null 2>&1 </dev/null &
sleep 12

if pgrep -af "$UI_RE" >/dev/null 2>&1; then
    echo "ui running"
else
    echo "ui NOT running"
fi

if pgrep -af "$APP_PKG" >/dev/null 2>&1; then
    echo "app process alive: $(pgrep -af "$APP_PKG" | head -1)"
else
    echo "app process NOT found"
fi

timeout 30 flameshot full -p "$OUT" 2>&1 | head -3
ls -la "$OUT" 2>&1
