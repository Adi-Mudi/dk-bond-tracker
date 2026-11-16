import json
import re
from datetime import date, datetime, timedelta, timezone

from src.bond_master import transport
from src.prefs import get_pref, set_pref
from src.version import APP_VERSION

RELEASE_URL = transport.RELEASE_LATEST_URL
AUTO_CHECK_INTERVAL_SECONDS = 24 * 60 * 60

_SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?$")


def _now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _release_result(error=None):
    return {
        "tag_name": None,
        "html_url": None,
        "apk_download_url": None,
        "body": None,
        "error": error,
    }


def fetch_latest_release():
    try:
        status, raw = transport.github_release_json(RELEASE_URL)
    except ConnectionError:
        return _release_result("network_error")
    if status == 404:
        return _release_result("no_releases")
    if status in (403, 429):
        return _release_result("rate_limited")
    if status != 200:
        return _release_result("network_error")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return _release_result("parse_error")
    if not isinstance(payload, dict) or not payload.get("tag_name"):
        return _release_result("parse_error")
    apk_url = None
    for asset in payload.get("assets") or []:
        if str(asset.get("name") or "").lower().endswith(".apk"):
            apk_url = asset.get("browser_download_url")
            break
    return {
        "tag_name": payload.get("tag_name"),
        "html_url": payload.get("html_url"),
        "apk_download_url": apk_url,
        "body": payload.get("body") or "",
        "error": None,
    }


def parse_release(release_json):
    tag = str(release_json.get("tag_name") or "").strip()
    version = tag[1:] if tag[:1] in ("v", "V") else tag
    if version.endswith("-release"):
        version = version[: -len("-release")]
    apk_url = release_json.get("apk_download_url")
    error = None
    if not apk_url and release_json.get("error") is None:
        error = "no_apk_asset"
    return {
        "version": version,
        "html_url": release_json.get("html_url"),
        "apk_download_url": apk_url,
        "body": release_json.get("body") or "",
        "error": error,
    }


def _parse_version(text):
    match = _SEMVER.match(str(text or "").strip())
    if not match:
        return None
    major, minor, patch, pre = match.groups()
    return (int(major), int(minor), int(patch)), pre


def semver_compare(local, remote):
    left = _parse_version(local)
    right = _parse_version(remote)
    if left is None or right is None:
        return 0
    if left[0] != right[0]:
        return -1 if left[0] < right[0] else 1
    if left[1] == right[1]:
        return 0
    if left[1] is None:
        return -1 if right[1] is not None else 0
    if right[1] is None:
        return 1
    return 0


def check_for_updates(force=False):
    release = fetch_latest_release()
    checked_at = _now_iso()
    if release["error"]:
        status = "offline" if release["error"] == "network_error" else "error"
        return {"status": status, "error": release["error"], "checked_at": checked_at}
    parsed = parse_release(release)
    if parsed["error"]:
        return {"status": "error", "error": parsed["error"], "checked_at": checked_at}
    if _parse_version(parsed["version"]) is None:
        return {"status": "error", "error": "parse_error", "checked_at": checked_at}
    if semver_compare(APP_VERSION, parsed["version"]) < 0:
        return {
            "status": "newer",
            "version": parsed["version"],
            "url": parsed["apk_download_url"] or parsed["html_url"],
            "checked_at": checked_at,
        }
    return {"status": "current", "version": parsed["version"], "checked_at": checked_at}


def store_update_result(conn, result):
    if result.get("status") not in ("newer", "current"):
        set_pref(conn, "update_error", result.get("error") or result.get("status"))
        return
    newer = result["status"] == "newer"
    set_pref(conn, "update_checked_at", result["checked_at"])
    set_pref(conn, "update_last_checked", date.today().isoformat())
    set_pref(conn, "update_last_release_json", json.dumps(result))
    set_pref(conn, "update_available", "1" if newer else "0")
    set_pref(conn, "update_version", result.get("version") or "")
    set_pref(conn, "update_url", result.get("url") or "")
    set_pref(conn, "update_error", "")


def auto_check_due(checked_at, now):
    if not checked_at:
        return True
    try:
        last = datetime.fromisoformat(checked_at)
    except ValueError:
        return True
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return now - last >= timedelta(seconds=AUTO_CHECK_INTERVAL_SECONDS)


def update_popup_state(conn):
    if get_pref(conn, "update_available", "0") != "1":
        return None
    version = get_pref(conn, "update_version", "")
    if not version or get_pref(conn, "update_dismissed_session", "") == version:
        return None
    return {
        "version": version,
        "url": get_pref(conn, "update_url", "") or None,
    }
