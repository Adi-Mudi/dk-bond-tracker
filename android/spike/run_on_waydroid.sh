#!/usr/bin/env bash
set -uo pipefail

SPIKE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APK="$1"
PKG="$2"
PREFIX="$3"

LOG="$SPIKE_DIR/logs/${PREFIX}_evidence.log"
LOGCAT="$SPIKE_DIR/logs/${PREFIX}_waydroid_logcat.log"
SHOT_DIR="$SPIKE_DIR/evidence"
mkdir -p "$SHOT_DIR"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/1000}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"

exec > >(tee "$LOG") 2>&1

echo "=== evidence run $(date -u +%Y-%m-%dT%H:%M:%SZ) ==="
echo "apk=$APK"
echo "pkg=$PKG"

if ! pgrep -f "waydroid show-full-ui" >/dev/null 2>&1; then
    echo "--- starting waydroid UI client (detached) ---"
    setsid waydroid show-full-ui >/dev/null 2>&1 </dev/null &
    sleep 10
fi

echo "--- waydroid status ---"
waydroid status 2>&1 | head -6

echo "--- removing any previous install ---"
waydroid app remove "$PKG" 2>&1 | head -3 || true

echo "--- installing ${APK} ---"
waydroid app install "$APK"
echo "install rc=$?"

echo "--- installed apps (filtered) ---"
waydroid app list 2>&1 | grep -iB1 -A2 "$PKG" || echo "(package not found in list)"

echo "--- launching $PKG ---"
waydroid app launch "$PKG"
echo "launch rc=$?"

echo "--- waiting 25s for app + flask server startup ---"
sleep 25

echo "--- screenshot ---"
if grim "$SHOT_DIR/${PREFIX}_screenshot.png" 2>&1; then
    echo "screenshot saved: $SHOT_DIR/${PREFIX}_screenshot.png"
    ls -la "$SHOT_DIR/${PREFIX}_screenshot.png"
else
    echo "grim failed"
fi

echo "--- capturing logcat (20s) ---"
timeout 20 waydroid logcat > "$LOGCAT" 2>&1
echo "logcat lines: $(wc -l < "$LOGCAT")"

echo "--- filtered logcat highlights ---"
grep -iE "DKBTSPIKE|chaquopy|python|flask|WebView|AndroidRuntime|FATAL|ActivityTaskManager|ActivityManager" "$LOGCAT" | tail -80

echo "=== evidence run end ==="
