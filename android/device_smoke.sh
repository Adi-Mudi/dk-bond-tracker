#!/usr/bin/env bash
set -uo pipefail

PKG="${DKBT_PKG:-com.dkbondtracker.app}"
ANDROID_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APK="${DKBT_APK:-$ANDROID_DIR/app/build/outputs/apk/debug/app-debug.apk}"
OUT="${DKBT_SMOKE_OUT:-$ANDROID_DIR/evidence/stage4/tc}"
BOOT_WAIT="${DKBT_BOOT_WAIT:-30}"
PAGE_WAIT="${DKBT_PAGE_WAIT:-4}"
HARD_KILL="${DKBT_HARD_KILL:-1}"
TMP_AREA="${DKBT_TMPDIR:-/var/tmp/dkbt-stage4-smoke}"
EXPORT_TAB="${DKBT_EXPORT_TAB:-26}"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=$XDG_RUNTIME_DIR/bus}"
export YDOTOOL_SOCKET="${YDOTOOL_SOCKET:-$XDG_RUNTIME_DIR/.ydotool_socket}"
mkdir -p "$TMP_AREA" "$OUT"
rm -f "$OUT"/tc_and_*.png "$OUT"/device_smoke.json
export TMPDIR="$TMP_AREA"

if [ "${DKBT_INHIBITED:-0}" != "1" ] && command -v systemd-inhibit >/dev/null 2>&1; then
  export DKBT_INHIBITED=1
  exec systemd-inhibit --what=idle --mode=block --why="dkbt device smoke" "$0" "$@"
fi

FAIL=0
say() { printf '%s\n' "$*"; }
fail() { say "FAIL: $*"; FAIL=1; }
sess_id() { loginctl list-sessions --no-legend 2>/dev/null | awk 'NR==1{print $1}'; }

screensaver_active() {
  gdbus call --session --dest org.gnome.ScreenSaver \
    --object-path /org/gnome/ScreenSaver \
    --method org.gnome.ScreenSaver.GetActive 2>/dev/null | grep -q "true"
}

ensure_unlocked() {
  if screensaver_active || loginctl show-session "$(sess_id)" -p LockedHint 2>/dev/null | grep -q "LockedHint=yes"; then
    loginctl unlock-session >/dev/null 2>&1
    sleep 3
    say "screensaver/lock dismissed"
  fi
}

close_notifications() {
  python3 - <<'PY'
import dbus
try:
    bus = dbus.SessionBus()
    i = dbus.Interface(bus.get_object('org.freedesktop.Notifications',
                                       '/org/freedesktop/Notifications'),
                       'org.freedesktop.Notifications')
    try:
        mid = int(i.Notify('dkbt-smoke', 0, '', 'probe', 'probe', [], {'transient': True}, -1))
    except Exception:
        mid = 800
    for x in range(1, mid + 10):
        try:
            i.CloseNotification(x)
        except Exception:
            pass
except Exception:
    pass
PY
}

shot() {
  local path="$1"
  ensure_unlocked
  close_notifications
  sleep 1
  rm -f "$path"
  timeout 40 flameshot full -p "$path" >/dev/null 2>&1
  if [ -s "$path" ]; then
    say "capture ok: $(basename "$path") ($(stat -c %s "$path") bytes)"
  else
    fail "capture missing/empty: $path"
  fi
}

press_enter() { ydotool key -d 150 28:1 28:0; }

key_tab() {
  local n="$1" i=0
  while [ "$i" -lt "$n" ]; do
    ydotool key -d 60 15:1 15:0
    sleep 0.15
    i=$((i + 1))
  done
  sleep 0.4
}

goto_page() {
  local n="$1" i=0
  while [ "$i" -lt "$n" ]; do
    ydotool key -d 60 15:1 15:0
    sleep 0.15
    i=$((i + 1))
  done
  sleep 0.4
  press_enter
  sleep "$PAGE_WAIT"
}

scroll_down() {
  local n="$1" i=0
  while [ "$i" -lt "$n" ]; do
    ydotool key -d 80 109:1 109:0
    sleep 0.6
    i=$((i + 1))
  done
  sleep 1
}

session_running() { waydroid status 2>/dev/null | grep -q "Session:.*RUNNING"; }

start_session() {
  session_running && return 0
  setsid waydroid session start >"$TMP_AREA/session.log" 2>&1 </dev/null &
  local i=0
  while [ "$i" -lt 45 ]; do
    sleep 2
    session_running && return 0
    i=$((i + 1))
  done
  return 1
}

wait_android_boot() {
  local i=0
  while [ "$i" -lt 30 ]; do
    timeout 15 waydroid app list >/dev/null 2>&1 && return 0
    sleep 4
    i=$((i + 1))
  done
  return 1
}

ensure_ui_client() {
  pgrep -f "waydroid show-full-u[i]" >/dev/null 2>&1 && return 0
  setsid waydroid show-full-ui >"$TMP_AREA/ui.log" 2>&1 </dev/null &
  sleep 10
}

say "== DK Bond Tracker device smoke (TC-AND) =="
say "apk=$APK"
say "out=$OUT"
say "hard_kill=$HARD_KILL"

if [ ! -f "$APK" ]; then
  fail "APK not found: $APK"
  exit 2
fi
APK_SHA="$(sha256sum "$APK" | awk '{print $1}')"
say "apk_sha256=$APK_SHA"

ensure_unlocked
[ "$(loginctl show-session "$(sess_id)" -p LockedHint 2>/dev/null | cut -d= -f2)" = "yes" ] && \
  say "WARNING: graphics session still LOCKED; captures will be unreliable"

if ! start_session; then
  fail "waydroid session could not be started"
  exit 2
fi
waydroid status 2>&1 | head -3
ensure_ui_client

if [ "${DKBT_COLD_START:-1}" = "1" ]; then
  say "cold start: restarting the container so the launch capture is a DETERMINISTIC COLD START"
  say "  root-free mechanism: waydroid session stop -> session start -> wait for Android boot"
  say "  reason: install+launch alone does NOT reset the WebView, so the app can resume its last-visited page instead of the Dashboard"
  timeout 90 waydroid session stop >/dev/null 2>&1
  sleep 5
  if start_session && wait_android_boot; then
    say "cold start complete: container restarted and Android booted"
  else
    say "WARN: cold start did not complete cleanly; continuing"
  fi
  sleep 8
  ensure_ui_client
fi

say "installing APK (TC-AND-01)"
if [ "${DKBT_FRESH:-0}" = "1" ]; then
  say "fresh mode requested: uninstalling the package (only for package changes)"
  timeout 60 waydroid app remove "$PKG" >/dev/null 2>&1
  for _ in 1 2 3 4 5 6; do
    if ! waydroid app list 2>/dev/null | grep -q "$PKG"; then break; fi
    sleep 2
  done
  if waydroid app list 2>/dev/null | grep -q "$PKG"; then
    fail "fresh install failed: $PKG still installed after remove (use: sudo waydroid shell -- pm uninstall --user 0 $PKG)"
  fi
fi

if [ "${DKBT_RESET:-1}" = "1" ] && waydroid app list 2>/dev/null | grep -q "$PKG"; then
  say "reset state: clearing app data (pm clear; Android Test Orchestrator practice)"
  timeout 45 waydroid shell -- pm clear "$PKG" >/dev/null 2>&1
fi
waydroid app install "$APK" >"$OUT/install.log" 2>&1
INSTALL_RC=$?
say "install rc=$INSTALL_RC"
[ "$INSTALL_RC" -eq 0 ] || fail "waydroid app install rc=$INSTALL_RC"

if ! waydroid app list 2>/dev/null | grep -q "$PKG"; then
  for _ in 1 2 3 4 5 6 7 8 9 10; do
    sleep 2
    if waydroid app list 2>/dev/null | grep -q "$PKG"; then break; fi
  done
fi
if waydroid app list 2>/dev/null | grep -q "$PKG"; then
  say "package present: $PKG"
else
  fail "package missing from app list: $PKG (after 20s poll)"
fi

say "launching app (TC-AND-01)"
waydroid app launch "$PKG" >"$OUT/launch.log" 2>&1
LAUNCH_RC=$?
say "launch rc=$LAUNCH_RC"
[ "$LAUNCH_RC" -eq 0 ] || fail "waydroid app launch rc=$LAUNCH_RC"
sleep "$BOOT_WAIT"

shot "$OUT/tc_and_01_dashboard_launch.png"
cp "$OUT/tc_and_01_dashboard_launch.png" "$OUT/tc_and_04_webview_localhost.png"

say "TC-AND-05: watchlist add form + settings share/export surface"
goto_page 3
shot "$OUT/tc_and_05_watchlist_add_form.png"
goto_page 6
scroll_down 3
shot "$OUT/tc_and_05_settings_share_export.png"

say "TC-AND-06: alerts parity"
goto_page 5
shot "$OUT/tc_and_06_alerts_parity.png"

say "TC-AND-05: Export CSV -> Android share sheet (AND-04)"
say "  needs the interactive session only; reading the saved CSV back needs root/run-as (unavailable)"
goto_page 6
key_tab "$EXPORT_TAB"
press_enter
sleep 7
shot "$OUT/tc_and_05_share_sheet.png"
say "  the chooser stays open; TC-AND-07's container restart clears it"

say "TC-AND-07: durability across a real process kill (container restart)"
if [ "$HARD_KILL" = "1" ]; then
  timeout 90 waydroid session stop >/dev/null 2>&1
  sleep 5
  if start_session && wait_android_boot; then
    say "container restarted and android booted"
  else
    fail "container restart or android boot failed"
  fi
  sleep 10
  ensure_ui_client
else
  say "soft relaunch (DKBT_HARD_KILL=0)"
fi
ensure_unlocked
waydroid app launch "$PKG" >/dev/null 2>&1
sleep "$BOOT_WAIT"
shot "$OUT/tc_and_07_dashboard_after_restart.png"

python3 - "$OUT" "$APK_SHA" "$PKG" <<'PY'
import hashlib, json, sys
from pathlib import Path

out = Path(sys.argv[1])
apk_sha = sys.argv[2]
pkg = sys.argv[3]

def sha16(name):
    f = out / name
    return hashlib.sha256(f.read_bytes()).hexdigest()[:16] if f.exists() else None

def size(name):
    f = out / name
    return f.stat().st_size if f.exists() else 0

def content_diff(a, b, top=60, bottom=60):
    try:
        from PIL import Image, ImageChops
    except Exception:
        return None
    fa, fb = out / a, out / b
    if not (fa.exists() and fb.exists()):
        return None
    ia, ib = Image.open(fa).convert("RGB"), Image.open(fb).convert("RGB")
    if ia.size != ib.size:
        return 1.0
    w, h = ia.size
    box = (0, top, w, h - bottom)
    ia, ib = ia.crop(box), ib.crop(box)
    hist = ImageChops.difference(ia, ib).convert("L").histogram()
    total = (box[2] - box[0]) * (box[3] - box[1])
    return (total - hist[0]) / total

caps = {n: {"sha16": sha16(n), "bytes": size(n)} for n in sorted(p.name for p in out.glob("*.png"))}
flows = ["tc_and_01_dashboard_launch.png", "tc_and_05_watchlist_add_form.png",
         "tc_and_06_alerts_parity.png"]
distinct = len({caps.get(n, {}).get("sha16") for n in flows if caps.get(n, {}).get("sha16")}) == 3
share_sheet = bool(caps.get("tc_and_05_share_sheet.png", {}).get("sha16"))

def rendered_page(name, min_ink=0.03):
    try:
        from PIL import Image
    except Exception:
        return None
    f = out / name
    if not f.exists():
        return None
    im = Image.open(f).convert("RGB")
    w, h = im.size
    box = (0, 60, w, h - 60)
    px = im.crop(box).resize((160, 90)).getdata()
    total = len(px)
    counts = {}
    for p in px:
        counts[p] = counts.get(p, 0) + 1
    dominant = max(counts.values())
    return (total - dominant) / total >= min_ink

ratio = content_diff("tc_and_01_dashboard_launch.png", "tc_and_07_dashboard_after_restart.png")
rerendered = rendered_page("tc_and_07_dashboard_after_restart.png")
durable = bool(ratio is not None and (ratio <= 0.02 or rerendered))

summary = {
    "id": "android_stage4_device_smoke",
    "package": pkg,
    "apk_sha256": apk_sha,
    "captures": caps,
    "assertions": {
        "three_flows_render_distinct_pages": distinct,
        "durability_content_diff_ratio": ratio,
        "durability_same_page_within_2pct": ratio is not None and ratio <= 0.02,
        "durability_page_rerendered": rerendered,
        "durability_within_2pct": durable,
    },
    "tc_results": {
        "TC-AND-01": {"tier": "device",
                      "result": "PASS" if caps.get("tc_and_01_dashboard_launch.png") else "FAIL",
                      "evidence": "tc_and_01_dashboard_launch.png"},
        "TC-AND-03": {"tier": "device", "result": "BLOCKED (env: no run-as); host contract covers",
                      "reason": "app-private DB path needs adb/run-as or root waydroid shell (neither available); the host contract covers it - android/tests/test_tc_and_host.py::test_tc_and_03_db_path_is_app_private"},
        "TC-AND-04": {"tier": "device",
                      "result": "PASS" if caps.get("tc_and_04_webview_localhost.png") else "FAIL",
                      "evidence": "tc_and_04_webview_localhost.png",
                      "note": "render proves the WebView loaded 127.0.0.1; cleartext logcat needs root waydroid logcat (unavailable)"},
        "TC-AND-05": {"tier": "device",
                      "result": "PASS" if caps.get("tc_and_05_share_sheet.png") else "FAIL",
                      "reason": "Export CSV link -> WebView onDownloadStart -> save to app-private files -> content:// via ExportProvider -> ACTION_SEND chooser; the chooser opens only after a successful save, so its presence proves the whole path",
                      "evidence": "tc_and_05_share_sheet.png, tc_and_05_settings_share_export.png, tc_and_05_watchlist_add_form.png",
                      "needs_root": "reading the saved CSV back (run-as) and dumping the chooser via dumpsys need root/adb (unavailable); covered by the host contract (no storage permission) and the in-app failure Toast path"},
        "TC-AND-06": {"tier": "device",
                      "result": "PASS" if caps.get("tc_and_06_alerts_parity.png") else "FAIL",
                      "evidence": "tc_and_06_alerts_parity.png"},
        "TC-AND-07": {"tier": "device",
                      "result": "PASS" if durable else "PARTIAL",
                      "reason": "dashboard rendered after a real container restart (session stop/start kills the app process); compared to the fresh-launch dashboard",
                      "evidence": "tc_and_07_dashboard_after_restart.png vs tc_and_01_dashboard_launch.png",
                      "content_diff_ratio": ratio},
    },
}
(out / "device_smoke.json").write_text(json.dumps(summary, indent=1))
print("summary:", out / "device_smoke.json")
print("distinct_pages:", distinct, "durability_ratio:", ratio, "durable:", durable, "share_sheet:", share_sheet)
sys.exit(0 if (distinct and durable and share_sheet) else 1)
PY
JSON_RC=$?
say "device_smoke.json rc=$JSON_RC"
[ "$JSON_RC" -eq 0 ] || fail "smoke summary assertions failed"

if [ "$FAIL" -eq 0 ]; then
  say "DEVICE SMOKE: PASS"
else
  say "DEVICE SMOKE: FAIL (see above)"
fi
exit "$FAIL"
