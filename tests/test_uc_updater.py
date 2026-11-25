import pytest
import json
import time
from datetime import datetime, timedelta, timezone
from unittest import mock

from src import updater
from src.bond_master import transport
from src.app import create_app
from src.db import get_conn
from src.prefs import get_pref, set_pref
from src.version import APP_VERSION
from src.views import about as about_view


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
    assert updater.semver_compare("1.0.9", "1.0.10") == 1
    assert updater.semver_compare("1.0.10", "1.0.9") == -1
    assert updater.semver_compare("1.0.9", "1.0.9") == 0
    assert updater.semver_compare("1.0.9", "1.0.10-beta.1") == 1


def test_semver_compare_prerelease_ordering_on_same_core():
    assert updater.semver_compare("1.0.10", "1.0.10-beta.1") == -1
    assert updater.semver_compare("1.0.10-beta.1", "1.0.10") == 1
    assert updater.semver_compare("1.0.10-beta.1", "1.0.10-beta.2") == 1
    assert updater.semver_compare("1.0.10-beta.2", "1.0.10-beta.1") == -1
    assert updater.semver_compare("1.0.10-beta.2", "1.0.10-beta.2") == 0


def test_check_does_not_offer_prerelease_to_final_user(monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.10")
    with fake_release(release_payload(tag="v1.0.10-beta.1-release", apk="beta.apk")):
        result = updater.check_for_updates()
    assert result["status"] == "current"


def test_check_reports_newer(monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    with fake_release(release_payload()):
        result = updater.check_for_updates()
    assert result["status"] == "newer"
    assert result["version"] == "1.0.10"
    assert result["url"] == "https://github.com/Adi-Mudi/dk-bond-tracker/releases/tag/v1.0.10-release"
    assert result["checked_at"]


def test_check_reports_current_when_equal(monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.10")
    with fake_release(release_payload()):
        result = updater.check_for_updates()
    assert result["status"] == "current"
    assert result["version"] == "1.0.10"


def test_check_reports_offline_on_network_error():
    with fake_network_down():
        result = updater.check_for_updates()
    assert result["status"] == "offline"
    assert result["error"] == "offline"


def test_check_reports_error_on_server_failure():
    with fake_status(500):
        result = updater.check_for_updates()
    assert result["status"] == "error"
    assert result["error"] == "parse_error"


def test_check_reports_error_when_no_releases():
    with fake_status(404):
        result = updater.check_for_updates()
    assert result["status"] == "error"
    assert result["error"] == "no_releases"


def test_check_reports_rate_limited():
    with fake_status(403):
        result = updater.check_for_updates()
    assert result["status"] == "error"
    assert result["error"] == "rate_limited"


def test_store_result_stamps_only_on_success(db_path):
    with get_conn(db_path) as conn:
        set_pref(conn, "update_available", "1")
        updater.store_update_result(conn, {"status": "offline", "error": "offline", "checked_at": "2026-11-16T00:00:00+00:00"})
        assert get_pref(conn, "update_checked_at") is None
        assert get_pref(conn, "update_available") == "0"
        updater.store_update_result(conn, {"status": "current", "version": "1.0.9", "checked_at": "2026-11-16T00:00:00+00:00"})
        assert get_pref(conn, "update_checked_at") == "2026-11-16T00:00:00+00:00"
        assert get_pref(conn, "update_available") == "0"


def test_store_result_saves_html_url_and_release_payload(db_path, monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    with fake_release(release_payload()):
        result = updater.check_for_updates()
    with get_conn(db_path) as conn:
        updater.store_update_result(conn, result)
        assert get_pref(conn, "update_url") == "https://github.com/Adi-Mudi/dk-bond-tracker/releases/tag/v1.0.10-release"
        stored = json.loads(get_pref(conn, "update_last_release_json"))
        assert stored["tag_name"] == "v1.0.10-release"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_about_post_check_renders_banner_and_redirects(db_path, monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    with fake_release(release_payload()):
        response = client.post("/about", data={"action": "check"})
    assert response.status_code == 302
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Update available: v1.0.10" in html
    assert 'id="update-download"' in html
    assert 'id="check-updates"' in html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_about_post_check_local_ahead_has_no_newest_claim(db_path, monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.11")
    monkeypatch.setattr(about_view, "APP_VERSION", "1.0.11")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    with fake_release(release_payload(tag="v1.0.9-release", apk="DK-Bond-Tracker-1.0.9.apk")):
        response = client.post("/about", data={"action": "check"})
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "You are on v1.0.11" in html
    assert "newest release" not in html
    assert 'id="update-download"' not in html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_about_post_check_offline_banner(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    with fake_network_down():
        response = client.post("/about", data={"action": "check"})
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    assert "Offline. Try again later." in html
    assert "newest release" not in html


def stamp_recent_check(db_path):
    with get_conn(db_path) as conn:
        set_pref(conn, "update_checked_at", datetime.now(timezone.utc).isoformat())


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_popup_is_shown_when_update_available(db_path):
    stamp_recent_check(db_path)
    with get_conn(db_path) as conn:
        set_pref(conn, "update_available", "1")
        set_pref(conn, "update_version", "1.0.10")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/").get_data(as_text=True)
    assert 'id="update-popup"' in html
    assert "v1.0.10" in html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_popup_dismiss_hides_popup_and_is_not_persisted(db_path):
    stamp_recent_check(db_path)
    with get_conn(db_path) as conn:
        set_pref(conn, "update_available", "1")
        set_pref(conn, "update_version", "1.0.10")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    assert client.post("/update/dismiss", data={"version": "1.0.10"}).status_code == 204
    html = client.get("/").get_data(as_text=True)
    assert 'id="update-popup"' not in html
    with get_conn(db_path) as conn:
        assert get_pref(conn, "update_dismissed_session", "") == ""
    restarted = create_app(str(db_path))
    restarted.config["TESTING"] = True
    assert 'id="update-popup"' in restarted.test_client().get("/").get_data(as_text=True)


def set_check_age(db_path, hours):
    stamp = datetime.now(timezone.utc) - timedelta(hours=hours)
    with get_conn(db_path) as conn:
        set_pref(conn, "update_checked_at", stamp.isoformat())


def auto_app(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app


def wait_auto_idle(app):
    deadline = time.monotonic() + 5
    while app.config.get("UPDATE_CHECK_RUNNING") and time.monotonic() < deadline:
        time.sleep(0.01)


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_auto_check_skipped_when_disabled(db_path):
    set_check_age(db_path, 25)
    with get_conn(db_path) as conn:
        set_pref(conn, "update_auto_check", "0")
    app = auto_app(db_path)
    with fake_release(release_payload()) as fetch:
        app.test_client().get("/about")
        wait_auto_idle(app)
    fetch.assert_not_called()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_auto_check_skipped_within_24h(db_path):
    set_check_age(db_path, 12)
    app = auto_app(db_path)
    with fake_release(release_payload()) as fetch:
        app.test_client().get("/about")
        wait_auto_idle(app)
    fetch.assert_not_called()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_auto_check_runs_past_24h(db_path, monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    set_check_age(db_path, 25)
    app = auto_app(db_path)
    with fake_release(release_payload()) as fetch:
        app.test_client().get("/about")
        wait_auto_idle(app)
    fetch.assert_called_once()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_auto_check_failure_keeps_gate_open_for_next_request(db_path):
    app = auto_app(db_path)
    with fake_network_down():
        app.test_client().get("/about")
        wait_auto_idle(app)
    with get_conn(db_path) as conn:
        assert get_pref(conn, "update_checked_at") is None
    with fake_release(release_payload()) as fetch_ok:
        app.test_client().get("/about")
        wait_auto_idle(app)
    fetch_ok.assert_called_once()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_auto_check_in_flight_guard_blocks_second_auto_check(db_path):
    app = auto_app(db_path)
    app.config["UPDATE_CHECK_RUNNING"] = True
    with fake_release(release_payload()) as fetch:
        app.test_client().get("/about")
    fetch.assert_not_called()


def test_manual_check_runs_while_auto_check_in_flight(db_path, monkeypatch):
    monkeypatch.setattr(updater, "APP_VERSION", "1.0.9")
    app = auto_app(db_path)
    app.config["UPDATE_CHECK_RUNNING"] = True
    with fake_release(release_payload()) as fetch:
        response = app.test_client().post("/about", data={"action": "check"})
    assert response.status_code == 302
    fetch.assert_called_once()
    with get_conn(db_path) as conn:
        assert get_pref(conn, "update_version") == "1.0.10"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_popup_css_hides_backdrop_when_hidden_attribute_set(db_path):
    stamp_recent_check(db_path)
    with get_conn(db_path) as conn:
        set_pref(conn, "update_available", "1")
        set_pref(conn, "update_version", "1.0.10")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/").get_data(as_text=True)
    assert ".update-popup-backdrop[hidden] { display: none; }" in html
