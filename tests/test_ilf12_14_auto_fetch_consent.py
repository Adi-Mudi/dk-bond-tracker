import pytest
import time

from src.app import create_app
from src.bond_master import service as svc
from src.bond_master.service import (
    AUTO_FETCH_ENABLED_KEY,
    AUTO_FETCH_PROMPTED_KEY,
    LAST_AUTO_FETCH_KEY,
    LAST_REAL_PASS_KEY,
    refresh_all,
)
from src.db import get_conn
from src.prefs import get_pref, set_pref

WATCHLIST_ISIN = "INE002A01018"


class FactAdapter:
    def __init__(self):
        self.calls = []

    def fetch(self, isin):
        from src.bond_master.base import FetchResult

        self.calls.append(isin)
        return FetchResult(isin=isin, company="Acme Ltd", sources={"company": "NSDL"})


class OfflineAdapter:
    def __init__(self):
        self.calls = []

    def fetch(self, isin):
        self.calls.append(isin)
        raise OSError("offline")


def _builder(adapter):
    def _build(cache, transport):
        return svc.BondMasterService(
            {"NSDL": adapter},
            cache,
            sleep=lambda _delay: None,
            throttle_seconds=0.0,
            retries=0,
        )

    return _build


def _seed_watch(db_path, isin=WATCHLIST_ISIN):
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO bond_master (isin) VALUES (?)", (isin,))
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, watch_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Acme Ltd", isin, "Acme Ltd", 100000.0, "2025-01-05", "2026-01-05", 12, 5, "watching"),
        )


def _pref(db_path, key):
    with get_conn(db_path) as conn:
        return get_pref(conn, key)


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_ilf_12_consent_dialog_shows_once_then_never_again(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    assert b'id="auto-fetch-consent"' in client.get("/").data
    assert client.post("/settings/auto-fetch/consent", data={"choice": "later"}).status_code == 200
    assert b'id="auto-fetch-consent"' not in client.get("/").data
    assert b'id="auto-fetch-consent"' not in client.get("/").data


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_ilf_12_consent_dialog_never_again_after_auto_choice(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    client.post("/settings/auto-fetch/consent", data={"choice": "auto"})
    assert _pref(db_path, AUTO_FETCH_PROMPTED_KEY) == "1"
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "1"
    assert b'id="auto-fetch-consent"' not in client.get("/").data


def test_tc_ilf_12_consent_rejects_unknown_choice(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    assert client.post("/settings/auto-fetch/consent", data={"choice": "maybe"}).status_code == 400
    assert _pref(db_path, AUTO_FETCH_PROMPTED_KEY) is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_ilf_13_toggle_defaults_off_and_last_synced_never(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    page = client.get("/settings?section=data").data
    assert b'name="auto_fetch_enabled"' in page
    assert b'name="auto_fetch_enabled" value="1" checked' not in page
    assert b"Last synced: Never" in page
    assert b'id="auto-fetch-sync"' in page


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_ilf_13_sync_now_runs_a_pass_and_updates_last_synced(db_path, monkeypatch):
    _seed_watch(db_path)
    adapter = FactAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    app = create_app(str(db_path))
    client = app.test_client()
    assert client.post("/settings/auto-fetch/sync").status_code == 302
    assert adapter.calls == [WATCHLIST_ISIN]
    assert _pref(db_path, LAST_REAL_PASS_KEY) is not None
    assert b"Last synced: Never" not in client.get("/settings?section=data").data


def test_tc_ilf_13_saving_the_toggle_persists_it(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    client.post("/settings?section=data", data={"section": "data", "auto_fetch_enabled": "1"})
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "1"
    client.post("/settings?section=data", data={"section": "data"})
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "0"


def test_tc_ilf_14_off_skips_the_auto_pass_and_writes_no_stamp(db_path, monkeypatch):
    _seed_watch(db_path)
    adapter = FactAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    refresh_all(str(db_path), "auto")
    assert adapter.calls == []
    assert _pref(db_path, LAST_AUTO_FETCH_KEY) is None
    assert _pref(db_path, LAST_REAL_PASS_KEY) is None


def test_tc_ilf_14_opted_in_auto_pass_writes_stamp_after_real_pass(db_path, monkeypatch):
    _seed_watch(db_path)
    with get_conn(db_path) as conn:
        set_pref(conn, AUTO_FETCH_ENABLED_KEY, "1")
    adapter = FactAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    refresh_all(str(db_path), "auto")
    assert adapter.calls == [WATCHLIST_ISIN]
    assert _pref(db_path, LAST_AUTO_FETCH_KEY) is not None
    assert _pref(db_path, LAST_REAL_PASS_KEY) is not None


def test_tc_ilf_14_failed_auto_pass_writes_no_stamp(db_path, monkeypatch):
    _seed_watch(db_path)
    with get_conn(db_path) as conn:
        set_pref(conn, AUTO_FETCH_ENABLED_KEY, "1")
    adapter = OfflineAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    refresh_all(str(db_path), "auto")
    assert _pref(db_path, LAST_AUTO_FETCH_KEY) is None
    assert _pref(db_path, LAST_REAL_PASS_KEY) is None


def test_tc_ilf_14_stamp_older_than_twelve_hours_runs_again_when_opted_in(db_path, monkeypatch):
    _seed_watch(db_path)
    with get_conn(db_path) as conn:
        set_pref(conn, AUTO_FETCH_ENABLED_KEY, "1")
        set_pref(conn, LAST_AUTO_FETCH_KEY, repr(time.time() - svc.AUTO_WINDOW_SECONDS - 60))
    adapter = FactAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    refresh_all(str(db_path), "auto")
    assert adapter.calls == [WATCHLIST_ISIN]
