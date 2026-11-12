from src.bond_master.base import (
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_UNREACHABLE,
    SOURCE_PRIORITY,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService

ISIN = "INE205A07DV2"
ASOF_AT_1700000000 = "2023-11-14T22:13:20+00:00"


class FakeAdapter:
    def __init__(self, name, results):
        self.name = name
        self._results = list(results)
        self.calls = []

    def fetch(self, isin):
        self.calls.append(isin)
        outcome = self._results[min(len(self.calls) - 1, len(self._results) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def make_service(tmp_path, adapters, **kwargs):
    cache = BondMasterCache(
        tmp_path / "bonds.db",
        cooldown_seconds=kwargs.pop("cooldown_seconds", 0.0),
    )
    service = BondMasterService(
        adapters,
        cache,
        sleep=lambda _delay: None,
        throttle_seconds=kwargs.pop("throttle_seconds", 0.0),
        **kwargs,
    )
    return service, cache


def test_every_adapter_raising_never_reaches_the_caller(tmp_path):
    adapters = {name: FakeAdapter(name, [RuntimeError("boom")]) for name in SOURCE_PRIORITY}
    service, _ = make_service(tmp_path, adapters, retries=1)
    result = service.lookup(ISIN)
    assert isinstance(result, FetchResult)
    assert result.has_facts() is False


def test_a_not_found_fetch_does_not_block_a_typed_save(db_path):
    adapters = {
        name: FakeAdapter(name, [FetchResult(isin=ISIN, failure_code=FAILURE_NOT_FOUND)])
        for name in SOURCE_PRIORITY
    }
    cache = BondMasterCache(db_path)
    service = BondMasterService(
        adapters, cache, sleep=lambda _delay: None, throttle_seconds=0.0, retries=0
    )
    result = service.lookup(ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND
    cache.save({"isin": ISIN, "company": "Typed Co", "coupon": 7.5, "source": "user"})
    row = cache.lookup(ISIN)
    assert row["company"] == "Typed Co"
    assert row["coupon"] == 7.5


def test_all_sources_unreachable_is_reported_offline(tmp_path):
    adapters = {name: FakeAdapter(name, [OSError("no route to host")]) for name in SOURCE_PRIORITY}
    service, _ = make_service(tmp_path, adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.failure_code == FAILURE_OFFLINE
    assert result.has_facts() is False


def test_a_mixed_failure_is_not_reported_offline(tmp_path):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [FetchResult(isin=ISIN, failure_code=FAILURE_NOT_FOUND)]),
        "RBI": FakeAdapter("RBI", [OSError("no route")]),
    }
    service, _ = make_service(tmp_path, adapters, retries=0)
    assert service.lookup(ISIN).failure_code == FAILURE_UNREACHABLE


def test_offline_offer_returns_cached_values_with_the_as_of_date(db_path):
    now = [1_700_000_000.0]
    cache = BondMasterCache(db_path, clock=lambda: now[0])
    cache.save({"isin": ISIN, "company": "Acme Ltd", "coupon": 8.75, "source": "nsdl"})
    adapters = {name: FakeAdapter(name, [OSError("offline")]) for name in SOURCE_PRIORITY}
    service = BondMasterService(
        adapters,
        cache,
        clock=lambda: now[0],
        sleep=lambda _delay: None,
        throttle_seconds=0.0,
        retries=0,
    )
    assert service.lookup(ISIN).failure_code == FAILURE_OFFLINE
    offer = cache.offer(ISIN)
    assert offer["company"] == "Acme Ltd"
    assert offer["coupon"] == 8.75
    assert offer["as_of"] == ASOF_AT_1700000000
