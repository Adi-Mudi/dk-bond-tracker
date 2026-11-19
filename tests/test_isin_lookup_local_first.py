from pathlib import Path

from src.bond_master.base import FAILURE_RATE_LIMITED, FetchResult
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService
from src.db import init_db
from src.views.watch import FETCH_FOUND, fetch_payload

ISIN_PERSISTED = "INE205A07DV2"
ISIN_SNAPSHOT = "IN0019790024"
COMPANY = "Acme Infrastructure Ltd"


def fresh_db(tmp_path):
    db_path = tmp_path / "app.db"
    init_db(db_path)
    return db_path


class CountingAdapter:
    name = "NSDL"

    def __init__(self):
        self.calls = 0

    def fetch(self, isin):
        self.calls += 1
        return FetchResult(isin=isin, failure_code="NOT_FOUND")


def seed_persisted(db_path):
    BondMasterCache(db_path).save(
        {
            "isin": ISIN_PERSISTED,
            "company": COMPANY,
            "rating": "AA+",
            "rating_agency": "CRISIL",
            "issuer_type": "ncd",
            "secured": 1,
            "source": "NSDL",
            "fetched_at": "11 Nov 2026, 09:42",
        }
    )


def test_persisted_answer_is_local_with_no_cooldown_and_no_official_call(tmp_path):
    db_path = fresh_db(tmp_path)
    seed_persisted(db_path)
    adapter = CountingAdapter()
    cache = BondMasterCache(db_path, cooldown_seconds=60)
    cache.begin_refresh()
    service = BondMasterService({"NSDL": adapter}, cache, sleep=lambda _s: None, retries=0)

    result = service.lookup(ISIN_PERSISTED)

    assert result.has_facts()
    assert result.company == COMPANY
    assert adapter.calls == 0
    assert cache.cooldown_remaining() > 0


def test_snapshot_only_isin_attempts_official_collect_and_keeps_snapshot_facts(tmp_path):
    db_path = fresh_db(tmp_path)
    adapter = CountingAdapter()
    cache = BondMasterCache(db_path, cooldown_seconds=60)
    service = BondMasterService({"NSDL": adapter}, cache, sleep=lambda _s: None, retries=0)

    result = service.lookup(ISIN_SNAPSHOT)

    assert result.has_facts()
    assert adapter.calls == 1
    assert result.source_of("rating") is None
    assert cache.cooldown_remaining() > 0


def test_local_hit_does_not_claim_the_cooldown(tmp_path):
    db_path = fresh_db(tmp_path)
    seed_persisted(db_path)
    cache = BondMasterCache(db_path, cooldown_seconds=60)
    service = BondMasterService({"NSDL": CountingAdapter()}, cache, sleep=lambda _s: None, retries=0)

    service.lookup(ISIN_PERSISTED)

    assert cache.cooldown_remaining() == 0.0


def test_local_miss_within_cooldown_is_rate_limited_with_countdown(tmp_path):
    db_path = fresh_db(tmp_path)
    cache = BondMasterCache(db_path, cooldown_seconds=60)
    cache.begin_refresh()
    service = BondMasterService({"NSDL": CountingAdapter()}, cache, sleep=lambda _s: None, retries=0)

    result = service.lookup("INE000Z01099")

    assert result.failure_code == FAILURE_RATE_LIMITED
    assert cache.cooldown_remaining() > 0


def test_local_answer_payload_shows_no_countdown(tmp_path):
    db_path = fresh_db(tmp_path)
    seed_persisted(db_path)
    cache = BondMasterCache(db_path, cooldown_seconds=60)
    cache.begin_refresh()
    service = BondMasterService({"NSDL": CountingAdapter()}, cache, sleep=lambda _s: None, retries=0)

    result = service.lookup(ISIN_PERSISTED)
    payload = fetch_payload(result, (), cached_row=cache.lookup(ISIN_PERSISTED))

    assert payload["state"] == FETCH_FOUND
    assert payload["failure_code"] != FAILURE_RATE_LIMITED


def test_rate_limited_payload_carries_failure_code_for_countdown(tmp_path):
    db_path = fresh_db(tmp_path)
    cache = BondMasterCache(db_path, cooldown_seconds=60)
    cache.begin_refresh()
    service = BondMasterService({"NSDL": CountingAdapter()}, cache, sleep=lambda _s: None, retries=0)

    result = service.lookup("INE000Z01099")
    payload = fetch_payload(result, ())

    assert payload["failure_code"] == FAILURE_RATE_LIMITED
