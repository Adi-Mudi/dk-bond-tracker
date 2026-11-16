import json
from unittest import mock

from src import updater
from src.bond_master import transport
from src.app import create_app
from src.db import get_conn
from src.prefs import get_pref, set_pref
from src.version import APP_VERSION


def release_payload(tag="v1.0.10-release", apk="DK-Bond-Tracker-1.0.10.apk"):
    assets = [{"name": apk, "browser_download_url": f"https://example.test/{apk}"}] if apk else []
    return {
        "tag_name": tag,
        "html_url": "https://github.com/Adi-Mudi/dk-bond-tracker/releases/tag/" + tag,
        "body": "notes",
        "assets": assets,
    }


def fake_release(payload):
    body = json.dumps(payload).encode("utf-8")
    return mock.patch.object(transport, "github_release_json", return_value=(200, body))


def fake_status(status):
    return mock.patch.object(transport, "github_release_json", return_value=(status, b""))


def fake_network_down():
    return mock.patch.object(transport, "github_release_json", side_effect=ConnectionError("down"))


def test_parse_release_strips_v_and_release_suffix():
    parsed = updater.parse_release(
        {"tag_name": "v1.0.10-beta.1-release", "html_url": "u", "apk_download_url": "a", "body": "b", "error": None}
    )
    assert parsed["version"] == "1.0.10-beta.1"
    assert parsed["apk_download_url"] == "a"
    assert parsed["error"] is None


def test_parse_release_without_apk_reports_no_apk_asset():
    parsed = updater.parse_release({"tag_name": "v1.0.10-release", "html_url": "u", "apk_download_url": None, "body": ""})
    assert parsed["apk_download_url"] is None
    assert parsed["error"] == "no_apk_asset"


def test_semver_compare_orders_versions():
    assert updater.semver_compare("1.0.9", "1.0.10") == -1
    assert updater.semver_compare("1.0.10", "1.0.9") == 1
    assert updater.semver_compare("1.0.9", "1.0.9") == 0
    assert updater.semver_compare("1.0.9", "1.0.10-beta.1") == -1


def test_check_reports_newer(monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    with fake_release(release_payload()):
        result = updater.check_for_updates(force=True)
    assert result["status"] == "newer"
    assert result["version"] == "1.0.10"
    assert result["url"] == "https://example.test/DK-Bond-Tracker-1.0.10.apk"
    assert result["checked_at"]


def test_check_reports_current_when_equal(monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.10")
    with fake_release(release_payload()):
        result = updater.check_for_updates(force=True)
    assert result["status"] == "current"
    assert result["version"] == "1.0.10"


def test_check_reports_offline_on_network_error():
    with fake_network_down():
        result = updater.check_for_updates(force=True)
    assert result["status"] == "offline"
    assert result["error"] == "network_error"


def test_check_reports_error_when_no_releases():
    with fake_status(404):
        result = updater.check_for_updates(force=True)
    assert result["status"] == "error"
    assert result["error"] == "no_releases"


def test_check_reports_rate_limited():
    with fake_status(403):
        result = updater.check_for_updates(force=True)
    assert result["status"] == "error"
    assert result["error"] == "rate_limited"


def test_store_result_stamps_only_on_success(db_path):
    with get_conn(db_path) as conn:
        updater.store_update_result(conn, {"status": "offline", "error": "network_error", "checked_at": "2026-11-16T00:00:00+00:00"})
        assert get_pref(conn, "update_checked_at") is None
        updater.store_update_result(conn, {"status": "current", "version": "1.0.9", "checked_at": "2026-11-16T00:00:00+00:00"})
        assert get_pref(conn, "update_checked_at") == "2026-11-16T00:00:00+00:00"
        assert get_pref(conn, "update_available") == "0"


def test_about_post_check_renders_banner(db_path, monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    with fake_release(release_payload()):
        html = client.post("/about", data={"action": "check"}).get_data(as_text=True)
    assert "v1.0.10 available" in html
    assert 'id="update-download"' in html
    assert 'id="check-updates"' in html


def test_about_post_check_offline_banner(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    with fake_network_down():
        html = client.post("/about", data={"action": "check"}).get_data(as_text=True)
    assert "Couldn't reach GitHub" in html
    assert "newest" not in html
