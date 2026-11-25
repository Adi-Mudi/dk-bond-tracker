import pytest
import re
from datetime import datetime

from src.app import create_app
from src.bond_master import service as svc
from src.bond_master.base import FetchResult
from src.bond_master.service import (
    AUTO_FETCH_ENABLED_KEY,
    AUTO_FETCH_PROMPTED_KEY,
    LAST_REAL_PASS_KEY,
)
from src.db import get_conn
from src.prefs import get_pref
from src.views.settings import SYNC_NOTHING_TO_SYNC_KEY, last_synced_label

WATCHLIST_ISIN = "INE002A01018"


class FactAdapter:
    def __init__(self):
        self.calls = []

    def fetch(self, isin):
        self.calls.append(isin)
        return FetchResult(isin=isin, company="Acme Ltd", sources={"company": "NSDL"})


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


def _label_from_page(client):
    html = client.get("/settings?section=data").get_data(as_text=True)
    match = re.search(r"Last synced: ([^<]+)</p>", html)
    assert match is not None
    return match.group(1).strip()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_s1_fresh_never_synced_shows_never(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    assert _label_from_page(client) == "Never"
    assert _pref(db_path, LAST_REAL_PASS_KEY) is None
    assert _pref(db_path, SYNC_NOTHING_TO_SYNC_KEY) is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_s2_sync_now_on_empty_db_shows_nothing_to_sync_yet(db_path, monkeypatch):
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(FactAdapter()))
    app = create_app(str(db_path))
    client = app.test_client()
    assert client.post("/settings/auto-fetch/sync").status_code == 302
    assert _pref(db_path, LAST_REAL_PASS_KEY) is None
    assert _pref(db_path, SYNC_NOTHING_TO_SYNC_KEY) == "1"
    assert _label_from_page(client) == "Nothing to sync yet"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_s3_real_sync_shows_actual_timestamp(db_path, monkeypatch):
    _seed_watch(db_path)
    adapter = FactAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    app = create_app(str(db_path))
    client = app.test_client()
    assert client.post("/settings/auto-fetch/sync").status_code == 302
    assert adapter.calls == [WATCHLIST_ISIN]
    stamp = _pref(db_path, LAST_REAL_PASS_KEY)
    assert stamp is not None
    expected = datetime.fromtimestamp(float(stamp)).strftime("%Y-%m-%d %H:%M")
    assert _label_from_page(client) == expected
    assert _pref(db_path, SYNC_NOTHING_TO_SYNC_KEY) is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_s4_u6_toggle_and_consent_unchanged(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    assert client.post("/settings/auto-fetch/consent", data={"choice": "later"}).status_code == 200
    assert _pref(db_path, AUTO_FETCH_PROMPTED_KEY) == "1"
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "0"
    html = client.get("/settings?section=data").get_data(as_text=True)
    assert 'name="auto_fetch_enabled"' in html
    assert 'id="auto-fetch-sync"' in html
    client.post("/settings?section=data", data={"section": "data", "auto_fetch_enabled": "1"})
    assert _pref(db_path, AUTO_FETCH_ENABLED_KEY) == "1"
    assert _pref(db_path, SYNC_NOTHING_TO_SYNC_KEY) is None


def test_state_matrix_never_then_empty_sync_then_real_sync(db_path, monkeypatch):
    monkeypatch.setattr(svc, "_CACHES", {})
    app = create_app(str(db_path))
    client = app.test_client()

    assert last_synced_label(db_path) == "Never"

    client.post("/settings/auto-fetch/sync")
    assert last_synced_label(db_path) == "Nothing to sync yet"

    _seed_watch(db_path)
    adapter = FactAdapter()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", _builder(adapter))
    client.post("/settings/auto-fetch/sync")
    label = last_synced_label(db_path)
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", label)
    assert adapter.calls == [WATCHLIST_ISIN]
