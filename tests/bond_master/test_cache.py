import pytest

from src.bond_master.cache import BondMasterCache, CooldownActive
from src.db import init_db
from src.validators import AppError

ASOF_AT_1700000000 = "2023-11-14T22:13:20+00:00"
ASOF_AT_1700000120 = "2023-11-14T22:15:20+00:00"


def test_refresh_blocked_inside_cooldown_and_allowed_after(tmp_path):
    now = [1000.0]
    cache = BondMasterCache(tmp_path / "bonds.db", clock=lambda: now[0])
    assert cache.refresh_allowed()
    cache.begin_refresh()
    assert not cache.refresh_allowed()
    with pytest.raises(CooldownActive):
        cache.begin_refresh()
    now[0] += 59.0
    assert not cache.refresh_allowed()
    with pytest.raises(CooldownActive):
        cache.begin_refresh()
    now[0] += 1.0
    assert cache.refresh_allowed()
    cache.begin_refresh()


def test_cooldown_blocks_many_taps_until_interval_passes(tmp_path):
    now = [500.0]
    cache = BondMasterCache(tmp_path / "bonds.db", clock=lambda: now[0])
    cache.begin_refresh()
    blocked = 0
    for _ in range(3):
        now[0] += 10.0
        if not cache.refresh_allowed():
            blocked += 1
    assert blocked == 3
    assert not cache.refresh_allowed()
    now[0] += 30.0
    assert cache.refresh_allowed()


def test_same_source_and_isin_served_from_session_result(db_path):
    calls = []

    def fetcher():
        calls.append(len(calls) + 1)
        return {"company": "Fetched"}

    cache = BondMasterCache(db_path)
    first = cache.fetch_session("nsdl", "INE0000000001", fetcher)
    second = cache.fetch_session("nsdl", "INE0000000001", fetcher)
    assert first is second
    assert calls == [1]
    cache.fetch_session("rbi", "INE0000000001", fetcher)
    assert calls == [1, 2]


def test_session_result_is_per_cache_instance(db_path):
    calls = []

    def fetcher():
        calls.append(len(calls) + 1)
        return {"company": "Fetched"}

    BondMasterCache(db_path).fetch_session("nsdl", "INE0000000001", fetcher)
    BondMasterCache(db_path).fetch_session("nsdl", "INE0000000001", fetcher)
    assert calls == [1, 2]


def test_session_result_lookup_does_not_fetch(db_path):
    cache = BondMasterCache(db_path)
    assert cache.session_result("nsdl", "INE0000000001") is None
    cache.fetch_session("nsdl", "INE0000000001", lambda: {"company": "Acme"})
    assert cache.session_result("nsdl", "INE0000000001") == {"company": "Acme"}


def test_save_persists_provenance_and_asof(tmp_path):
    now = [1_700_000_000.0]
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    cache = BondMasterCache(db_path, clock=lambda: now[0])
    cache.save(
        {
            "isin": "INE0000000001",
            "company": "Acme",
            "payout_cycle": "quarterly",
            "rating": "AA",
            "rating_agency": "CRISIL",
            "issuer_type": "ncd",
            "secured": 1,
            "listing_status": "listed",
            "maturity": "2030-01-01",
            "source": "nsdl",
        }
    )
    row = cache.lookup("INE0000000001")
    assert row["source"] == "nsdl"
    assert row["fetched_at"] == ASOF_AT_1700000000
    assert row["listing_status"] == "listed"
    assert row["rating_agency"] == "CRISIL"
    assert row["maturity"] == "2030-01-01"


def test_refresh_updates_provenance_and_asof(tmp_path):
    now = [1_700_000_000.0]
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    cache = BondMasterCache(db_path, clock=lambda: now[0])
    cache.save({"isin": "INE0000000001", "company": "Acme", "source": "nsdl", "listing_status": "listed"})
    now[0] += 120.0
    cache.save({"isin": "INE0000000001", "company": "Acme Ltd", "source": "rbi", "listing_status": "unlisted"})
    row = cache.lookup("INE0000000001")
    assert row["source"] == "rbi"
    assert row["company"] == "Acme Ltd"
    assert row["listing_status"] == "unlisted"
    assert row["fetched_at"] == ASOF_AT_1700000120


def test_lookup_returns_none_for_missing_isin(db_path):
    cache = BondMasterCache(db_path)
    assert cache.lookup("INE0000000000") is None


def test_listing_status_never_overloads_issuer_type(db_path):
    cache = BondMasterCache(db_path)
    cache.save({"isin": "INE0000000001", "issuer_type": "ncd", "listing_status": "unlisted"})
    row = cache.lookup("INE0000000001")
    assert row["issuer_type"] == "ncd"
    assert row["listing_status"] == "unlisted"


def test_save_requires_an_isin(db_path):
    cache = BondMasterCache(db_path)
    with pytest.raises(AppError):
        cache.save({"company": "No ISIN"})
