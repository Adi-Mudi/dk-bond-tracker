import time
from types import SimpleNamespace

from src.bond_master import service as svc
from src.bond_master.base import SOURCE_PRIORITY, FAILURE_UNREACHABLE, FetchResult
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService, refresh_all
from src.db import get_conn


class OfflineAdapter:
    def __init__(self, name):
        self.name = name

    def fetch(self, isin):
        raise OSError("offline")


def offline_builder(calls):
    def _build(cache, transport):
        calls.append(1)
        adapters = {name: OfflineAdapter(name) for name in SOURCE_PRIORITY}
        return BondMasterService(
            adapters, cache, sleep=lambda _delay: None, throttle_seconds=0.0, retries=0
        )

    return _build


def recording_builder_counting(calls):
    def _build(cache, transport):
        calls.append(1)
        return BondMasterService(
            {"NSDL": FactAdapter()}, cache, sleep=lambda _delay: None, throttle_seconds=0.0, retries=0
        )

    return _build


class FactAdapter:
    def fetch(self, isin):
        return FetchResult(isin=isin, company="Acme Ltd", sources={"company": "NSDL"})


def test_af10_1_auto_refresh_runs_at_most_once_per_twelve_hours(db_path, monkeypatch):
    seed_known_isin(db_path, WATCHLIST_ISIN, "watching")
    enable_auto_fetch(db_path)
    calls = []
    clock = [1000.0]
    cache = BondMasterCache(db_path, clock=lambda: clock[0])
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder_counting(calls))
    monkeypatch.setattr(svc, "time", SimpleNamespace(time=lambda: clock[0]))
    refresh_all(str(db_path), "auto")
    clock[0] += 61.0
    refresh_all(str(db_path), "auto")
    assert len(calls) == 1
    clock[0] += svc.AUTO_WINDOW_SECONDS
    refresh_all(str(db_path), "auto")
    assert len(calls) == 2


def test_fix2_auto_inside_a_cooldown_does_not_record_the_twelve_hour_stamp(db_path, monkeypatch):
    seed_known_isin(db_path, WATCHLIST_ISIN, "watching")
    enable_auto_fetch(db_path)
    calls = []
    clock = [1000.0]
    cache = BondMasterCache(db_path, clock=lambda: clock[0])
    cache.begin_refresh()
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", offline_builder(calls))
    monkeypatch.setattr(svc, "time", SimpleNamespace(time=lambda: clock[0]))
    refresh_all(str(db_path), "auto")
    assert calls == []
    assert svc.auto_refresh_due(str(db_path), clock[0])
    clock[0] += 61.0
    refresh_all(str(db_path), "auto")
    assert len(calls) == 1


def test_af10_2_manual_refresh_honours_the_sixty_second_cooldown(db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", offline_builder(calls))
    refresh_all(str(db_path), "manual")
    refresh_all(str(db_path), "manual")
    refresh_all(str(db_path), "manual")
    assert len(calls) == 1


def test_af10_3_offline_refresh_reports_offline_and_keeps_the_as_of(db_path, monkeypatch):
    BondMasterCache(db_path).save(
        {"isin": "INE123456789", "company": "Acme Ltd", "source": "NSDL"}
    )
    calls = []
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", offline_builder(calls))
    summary = refresh_all(str(db_path), "manual")
    assert set(summary) == set(SOURCE_PRIORITY)
    nsdl = summary["NSDL"]
    assert nsdl["status"] == "offline"
    assert nsdl["failure_code"] == FAILURE_UNREACHABLE
    assert nsdl["as_of"]


def test_refresh_all_never_raises_on_a_broken_db(tmp_path, monkeypatch):
    monkeypatch.setattr(svc, "_CACHES", {})
    broken = tmp_path / "missing" / "bonds.db"
    summary = refresh_all(str(broken), "manual")
    assert isinstance(summary, dict)


def test_refresh_all_summary_shape_is_per_source(db_path, monkeypatch):
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", offline_builder([]))
    summary = refresh_all(str(db_path), "manual")
    for source in SOURCE_PRIORITY:
        assert set(summary[source]) == {"status", "failure_code", "as_of"}


PORTFOLIO_ISIN = "INE0ABC01011"
WATCHLIST_ISIN = "INE002A01018"


class RecordingAdapter:
    def __init__(self, budget=None):
        self._budget = budget
        self.calls = []

    def fetch(self, isin):
        if self._budget is not None and len(self.calls) >= self._budget:
            raise OSError("pass budget exhausted")
        self.calls.append(isin)
        return FetchResult(isin=isin, company="Acme Ltd", sources={"company": "NSDL"})


def recording_builder(adapter):
    def _build(cache, transport):
        return BondMasterService(
            {"NSDL": adapter},
            cache,
            sleep=lambda _delay: None,
            throttle_seconds=0.0,
            retries=0,
        )

    return _build


def enable_auto_fetch(db_path):
    from src.prefs import set_pref

    with get_conn(db_path) as conn:
        set_pref(conn, svc.AUTO_FETCH_ENABLED_KEY, "1")


def seed_known_isin(db_path, isin, watch_state):
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO bond_master (isin) VALUES (?)", (isin,))
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, watch_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("Acme Ltd", isin, "Acme Ltd", 100000.0, "2025-01-05", "2026-01-05", 12, 5, watch_state),
        )


def test_tc_af17_refresh_pass_requests_portfolio_isins_before_watchlist(db_path, monkeypatch):
    seed_known_isin(db_path, WATCHLIST_ISIN, "watching")
    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    adapter = RecordingAdapter()
    cache = BondMasterCache(db_path)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    refresh_all(str(db_path), "manual")
    assert adapter.calls == [PORTFOLIO_ISIN, WATCHLIST_ISIN]


def test_tc_af17_budget_exhaustion_covers_portfolio_and_defers_watchlist(db_path, monkeypatch):
    seed_known_isin(db_path, WATCHLIST_ISIN, "watching")
    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    adapter = RecordingAdapter(budget=1)
    cache = BondMasterCache(db_path)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    refresh_all(str(db_path), "manual")
    assert adapter.calls == [PORTFOLIO_ISIN]
    store = BondMasterCache(db_path)
    assert store.lookup(PORTFOLIO_ISIN)["company"] == "Acme Ltd"
    assert store.lookup(WATCHLIST_ISIN)["company"] is None


def test_tc_af17_pacing_caps_stay_inside_the_existing_limits(db_path, monkeypatch):
    from src.bond_master import cache as cache_module

    assert svc.DEFAULT_THROTTLE_SECONDS == 1.0
    assert svc.DEFAULT_RETRIES == 2
    assert svc.DEFAULT_RETRY_BACKOFF == 0.5
    assert cache_module.COOLDOWN_SECONDS == 60

    seed_known_isin(db_path, WATCHLIST_ISIN, "watching")
    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    adapter = RecordingAdapter()
    cache = BondMasterCache(db_path)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    refresh_all(str(db_path), "manual")
    assert adapter.calls == [PORTFOLIO_ISIN, WATCHLIST_ISIN]
    assert set(cache._session_results) == {("NSDL", PORTFOLIO_ISIN), ("NSDL", WATCHLIST_ISIN)}

    served = list(adapter.calls)
    refresh_all(str(db_path), "manual")
    assert adapter.calls == served


def _portfolio_bond(db_path, isin, watch_state="holding"):
    seed_known_isin(db_path, isin, watch_state)
    with get_conn(db_path) as conn:
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def _refresh_client(db_path, adapter):
    from src.app import create_app

    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.extensions["bond_master_cache"] = BondMasterCache(db_path)
    app.extensions["bond_master_service"] = BondMasterService(
        {"NSDL": adapter}, app.extensions["bond_master_cache"], sleep=lambda _d: None,
        throttle_seconds=0.0, retries=0,
    )
    return app.test_client(), app


def test_tc_afr_04_portfolio_manual_refresh_returns_429_during_cooldown(db_path):
    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    client, app = _refresh_client(db_path, RecordingAdapter())
    app.extensions["bond_master_cache"]._last_refresh_at = time.time()
    response = client.post(f"/portfolio/{bond_id}/refresh")
    assert response.status_code == 429
    assert response.get_json()["status"] == "cooldown"


def test_tc_afr_05_portfolio_refresh_is_409_while_facts_are_fresh(db_path):
    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    adapter = RecordingAdapter()
    client, _app = _refresh_client(db_path, adapter)
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bond_master SET fetched_at = ? WHERE isin = ?",
            ("2099-01-01T00:00:00+00:00", PORTFOLIO_ISIN),
        )
    response = client.post(f"/portfolio/{bond_id}/refresh")
    assert response.status_code == 409
    assert response.get_json()["status"] == "already_fetched"
    assert adapter.calls == []


def test_tc_afr_05_portfolio_refresh_with_force_runs_and_returns_200(db_path, monkeypatch):
    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    adapter = RecordingAdapter()
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    client, _app = _refresh_client(db_path, adapter)
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bond_master SET fetched_at = ? WHERE isin = ?",
            ("2099-01-01T00:00:00+00:00", PORTFOLIO_ISIN),
        )
    response = client.post(f"/portfolio/{bond_id}/refresh?force=1")
    assert response.status_code == 200
    assert response.get_json()["status"] == "refreshed"
    assert adapter.calls == [PORTFOLIO_ISIN]


def test_tc_afr_08_invalid_holding_remove_marks_isin_and_readd_unmarks(db_path):
    from src.bond_master.service import _deleted_isins, unmark_isin_deleted

    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    client, _app = _refresh_client(db_path, RecordingAdapter())
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bonds SET start_date = NULL, end_date = NULL WHERE id = ?", (bond_id,)
        )
    client.post(f"/portfolio/invalid/{bond_id}/remove")
    with get_conn(db_path) as conn:
        assert PORTFOLIO_ISIN in _deleted_isins(conn)
        unmark_isin_deleted(conn, PORTFOLIO_ISIN)
        assert PORTFOLIO_ISIN not in _deleted_isins(conn)


def test_tc_afr_09_auto_pass_skips_deleted_isin(db_path, monkeypatch):
    from src.bond_master.service import mark_isin_deleted

    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    enable_auto_fetch(db_path)
    with get_conn(db_path) as conn:
        mark_isin_deleted(conn, PORTFOLIO_ISIN)
    monkeypatch.setattr(svc, "_auto_due", lambda _db, _now: True)
    adapter = RecordingAdapter()
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    refresh_all(db_path, trigger="auto")
    assert PORTFOLIO_ISIN not in adapter.calls


def test_tc_afr_04_manual_refresh_does_not_reset_the_auto_twelve_hour_stamp(db_path, monkeypatch):
    from src.bond_master.service import LAST_AUTO_FETCH_KEY
    from src.prefs import get_pref, set_pref

    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    adapter = RecordingAdapter()
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    client, _app = _refresh_client(db_path, adapter)
    recent = repr(time.time() - 60)
    with get_conn(db_path) as conn:
        set_pref(conn, LAST_AUTO_FETCH_KEY, recent)
    ran = client.post(f"/portfolio/{bond_id}/refresh?force=1")
    assert ran.status_code == 200
    assert adapter.calls == [PORTFOLIO_ISIN]
    with get_conn(db_path) as conn:
        assert get_pref(conn, LAST_AUTO_FETCH_KEY) == recent


def test_tc_afr_08_watchlist_candidate_delete_marks_the_isin_deleted(db_path):
    from src.bond_master.service import _deleted_isins

    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN, watch_state="watching")
    client, _app = _refresh_client(db_path, RecordingAdapter())
    response = client.post(f"/watch/{bond_id}/delete")
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM bonds WHERE id = ?", (bond_id,)).fetchone()["n"] == 0
        assert PORTFOLIO_ISIN in _deleted_isins(conn)


def test_tc_afr_08_stale_facts_without_force_refresh_returns_200(db_path, monkeypatch):
    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    adapter = RecordingAdapter()
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    client, _app = _refresh_client(db_path, adapter)
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bond_master SET fetched_at = ? WHERE isin = ?",
            ("2020-01-01T00:00:00+00:00", PORTFOLIO_ISIN),
        )
    response = client.post(f"/portfolio/{bond_id}/refresh")
    assert response.status_code == 200
    assert response.get_json()["status"] == "refreshed"
    assert adapter.calls == [PORTFOLIO_ISIN]


def test_tc_afr_08_watch_insert_and_backup_restore_clear_the_deleted_mark(db_path):
    from src.bond_master.service import _deleted_isins, mark_isin_deleted
    from src.db import init_db
    from src.app import create_app
    from src.import_csv import import_backup_csv
    from src.views.watch import watch_form_values, watch_insert_candidate
    from tests.conftest import add_bond

    form = {
        "company": "Test Co",
        "isin": PORTFOLIO_ISIN,
        "rating": "AAA",
        "source_note": "test",
        "coupon_pct": "7.5",
        "expected_yield_pct": "7.5",
    }
    with get_conn(db_path) as conn:
        mark_isin_deleted(conn, PORTFOLIO_ISIN)
        watch_insert_candidate(conn, watch_form_values(form))
        assert PORTFOLIO_ISIN not in _deleted_isins(conn)
        mark_isin_deleted(conn, PORTFOLIO_ISIN)

    source = db_path.parent / "restore_source.db"
    init_db(source)
    with get_conn(source) as conn:
        add_bond(conn, "Restore Co", PORTFOLIO_ISIN, "2026-01-01", 60)
    text = create_app(str(source)).test_client().get("/export.csv?scope=backup").get_data(as_text=True)
    target = db_path.parent / "restore_target.db"
    init_db(target)
    with get_conn(target) as conn:
        mark_isin_deleted(conn, PORTFOLIO_ISIN)
    with get_conn(target) as conn:
        counts = import_backup_csv(conn, text)
        assert counts["bonds"] == 1
        assert PORTFOLIO_ISIN not in _deleted_isins(conn)


def test_fix1_auto_pass_with_no_isins_does_not_record_the_stamp(db_path, monkeypatch):
    monkeypatch.setattr(svc, "_auto_due", lambda _db, _now: True)
    stamped = []
    monkeypatch.setattr(svc, "_record_auto_fetch", lambda *a, **k: stamped.append(a))
    refresh_all(db_path, trigger="auto")
    assert stamped == []


def test_tc_afr_03_auto_pass_covers_portfolio_and_watchlist_in_one_pass(db_path, monkeypatch):
    seed_known_isin(db_path, WATCHLIST_ISIN, "watching")
    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    enable_auto_fetch(db_path)
    monkeypatch.setattr(svc, "_auto_due", lambda _db, _now: True)
    adapter = RecordingAdapter()
    cache = BondMasterCache(db_path)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    refresh_all(str(db_path), trigger="auto")
    assert adapter.calls == [PORTFOLIO_ISIN, WATCHLIST_ISIN]
    assert len(adapter.calls) == len(set(adapter.calls))


def test_tc_afr_01_first_run_auto_fetch_fires_when_never_stamped(db_path, monkeypatch):
    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    enable_auto_fetch(db_path)
    adapter = RecordingAdapter()
    cache = BondMasterCache(db_path)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    assert svc._auto_due(str(db_path), time.time()) is True
    refresh_all(str(db_path), trigger="auto")
    assert adapter.calls == [PORTFOLIO_ISIN]


def test_tc_afr_02_auto_window_blocks_a_run_inside_twelve_hours(db_path, monkeypatch):
    seed_known_isin(db_path, PORTFOLIO_ISIN, "holding")
    enable_auto_fetch(db_path)
    adapter = RecordingAdapter()
    cache = BondMasterCache(db_path)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "shared_cache", lambda db_path: cache)
    monkeypatch.setattr(svc, "build_default_service", recording_builder(adapter))
    refresh_all(str(db_path), trigger="auto")
    assert adapter.calls == [PORTFOLIO_ISIN]
    refresh_all(str(db_path), trigger="auto")
    assert adapter.calls == [PORTFOLIO_ISIN]


def test_tc_afr_07_portfolio_refresh_mirrors_the_watchlist_contract(db_path, monkeypatch):
    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    client, app = _refresh_client(db_path, RecordingAdapter())
    cache = app.extensions["bond_master_cache"]
    cache._last_refresh_at = time.time()
    cooled = client.post(f"/portfolio/{bond_id}/refresh")
    watch_cooled = client.post("/watch/refresh")
    assert cooled.status_code == watch_cooled.status_code == 429
    assert cooled.get_json()["status"] == watch_cooled.get_json()["status"] == "cooldown"
    assert cooled.get_json()["trigger"] == watch_cooled.get_json()["trigger"] == "manual"

    cache._last_refresh_at = 0.0
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bond_master SET fetched_at = ? WHERE isin = ?",
            ("2099-01-01T00:00:00+00:00", PORTFOLIO_ISIN),
        )
    blocked = client.post(f"/portfolio/{bond_id}/refresh")
    assert blocked.status_code == 409
    assert blocked.get_json()["status"] == "already_fetched"

    cache._last_refresh_at = 0.0
    ran = client.post(f"/portfolio/{bond_id}/refresh?force=1")
    assert ran.status_code == 200
    assert ran.get_json()["status"] == "refreshed"
    assert ran.get_json()["trigger"] == "manual"
    assert "summary" in ran.get_json()


def test_tc_afr_10_staleness_cue_renders_on_portfolio_and_detail(db_path):
    from datetime import datetime, timedelta, timezone

    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    client, _app = _refresh_client(db_path, RecordingAdapter())
    old = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bond_master SET source = ?, fetched_at = ? WHERE isin = ?",
            ("NSDL", old, PORTFOLIO_ISIN),
        )
    listing = client.get("/portfolio").get_data(as_text=True)
    assert 'class="co-stale" data-stale="1"' in listing
    assert 'data-fetch-source="NSDL"' in listing
    assert 'data-refresh-url="/portfolio/' in listing
    detail = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert 'id="detail-provenance"' in detail
    assert 'class="co-stale" data-stale="1"' in detail
    assert old[:10] in detail
    assert 'id="detail-refresh"' in detail
    assert f'data-refresh-url="/portfolio/{bond_id}/refresh"' in detail


def test_tc_afr_10_fresh_facts_show_no_staleness_cue(db_path):
    from datetime import datetime, timezone

    bond_id = _portfolio_bond(db_path, PORTFOLIO_ISIN)
    client, _app = _refresh_client(db_path, RecordingAdapter())
    now = datetime.now(timezone.utc).isoformat()
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bond_master SET source = ?, fetched_at = ? WHERE isin = ?",
            ("NSDL", now, PORTFOLIO_ISIN),
        )
    listing = client.get("/portfolio").get_data(as_text=True)
    assert 'data-stale="1"' not in listing
    detail = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert 'data-stale="1"' not in detail
