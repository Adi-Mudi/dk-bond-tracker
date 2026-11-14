from src.bond_master import snapshot
from src.bond_master.base import (
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_RATE_LIMITED,
    FAILURE_UNREACHABLE,
    SOURCE_PRIORITY,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService

ISIN = "INE205A07DV2"
SNAPSHOT_ISIN = "IN8020B08012"
SNAPSHOT_COMPANY = "REC LIMITED"
UNKNOWN_ISIN = "INE205A07DW3"


class FakeClock:
    def __init__(self, start=1000.0):
        self.now = start
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, delay):
        self.sleeps.append(delay)
        self.now += delay


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


class TickingAdapter:
    def __init__(self, name, clock, results):
        self.name = name
        self._clock = clock
        self._results = list(results)
        self.times = []

    def fetch(self, isin):
        self.times.append(self._clock())
        outcome = self._results[min(len(self.times) - 1, len(self._results) - 1)]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def found(isin, source="NSDL"):
    return FetchResult(isin=isin, company="Acme Ltd", sources={"company": source})


def make_service(tmp_path, adapters, clock, **kwargs):
    cache = BondMasterCache(
        tmp_path / "bonds.db",
        clock=clock,
        cooldown_seconds=kwargs.pop("cooldown_seconds", 0.0),
    )
    service = BondMasterService(
        adapters,
        cache,
        clock=clock,
        sleep=clock.sleep,
        throttle_seconds=kwargs.pop("throttle_seconds", 0.0),
        **kwargs,
    )
    return service, cache


def test_retries_never_undercut_the_global_throttle(tmp_path):
    clock = FakeClock()
    adapter = TickingAdapter(
        "NSDL",
        clock,
        [
            FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE),
            FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE),
            found(ISIN),
        ],
    )
    service, _ = make_service(
        tmp_path,
        {"NSDL": adapter},
        clock,
        retries=2,
        retry_backoff=0.5,
        throttle_seconds=1.0,
    )
    result = service.lookup(ISIN)
    assert result.has_facts()
    assert len(adapter.times) == 3
    gaps = [later - earlier for earlier, later in zip(adapter.times, adapter.times[1:])]
    assert all(gap >= 1.0 for gap in gaps)
    assert clock.sleeps == [1.0, 1.0]


def test_retry_backoff_is_used_when_the_throttle_is_disabled(tmp_path):
    clock = FakeClock()
    adapter = TickingAdapter(
        "NSDL",
        clock,
        [
            FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE),
            found(ISIN),
        ],
    )
    service, _ = make_service(
        tmp_path,
        {"NSDL": adapter},
        clock,
        retries=1,
        retry_backoff=0.5,
        throttle_seconds=0.0,
    )
    service.lookup(ISIN)
    assert clock.sleeps == [0.5]


def test_all_sources_returning_empty_ok_report_not_found(tmp_path):
    clock = FakeClock()
    adapters = {
        name: FakeAdapter(name, [FetchResult(isin=ISIN, failure_code=FAILURE_OK)])
        for name in SOURCE_PRIORITY
    }
    service, _ = make_service(tmp_path, adapters, clock, retries=0)
    result = service.lookup(ISIN)
    assert result.has_facts() is False
    assert result.failure_code == FAILURE_NOT_FOUND


def test_a_single_source_returning_empty_ok_reports_not_found(tmp_path):
    clock = FakeClock()
    adapters = {"NSDL": FakeAdapter("NSDL", [FetchResult(isin=ISIN, failure_code=FAILURE_OK)])}
    service, _ = make_service(tmp_path, adapters, clock, retries=0)
    assert service.lookup(ISIN).failure_code == FAILURE_NOT_FOUND


def test_an_explicit_not_found_stays_not_found(tmp_path):
    clock = FakeClock()
    adapters = {
        "NSDL": FakeAdapter("NSDL", [FetchResult(isin=ISIN, failure_code=FAILURE_NOT_FOUND)])
    }
    service, _ = make_service(tmp_path, adapters, clock, retries=0)
    assert service.lookup(ISIN).failure_code == FAILURE_NOT_FOUND


def test_an_empty_result_is_recorded_as_not_found_not_ok(tmp_path):
    clock = FakeClock()
    adapters = {"NSDL": FakeAdapter("NSDL", [FetchResult(isin=ISIN, failure_code=FAILURE_OK)])}
    service, _ = make_service(tmp_path, adapters, clock, retries=0)
    service.lookup(ISIN)
    events = service.events()
    assert [(event.source, event.ok) for event in events] == [("NSDL", False)]
    assert events[0].failure_code == FAILURE_NOT_FOUND


def _warming_service(tmp_path, clock, cooldown_seconds=60.0):
    adapters = {name: FakeAdapter(name, [found(ISIN)]) for name in SOURCE_PRIORITY}
    service, cache = make_service(
        tmp_path, adapters, clock, cooldown_seconds=cooldown_seconds
    )
    cache.begin_refresh()
    return service, cache, adapters


def test_af16_warm_cooldown_answers_a_snapshot_isin_with_zero_adapter_calls(tmp_path):
    clock = FakeClock()
    service, cache, adapters = _warming_service(tmp_path, clock)
    assert cache.network_blocked() is True
    result = service.lookup(SNAPSHOT_ISIN)
    assert result.has_facts() is True
    assert result.company == SNAPSHOT_COMPANY
    assert result.source_of("company") == snapshot.SNAPSHOT_SOURCE
    for name in SOURCE_PRIORITY:
        assert adapters[name].calls == []


def test_af16_warm_cooldown_blocks_an_unknown_isin_with_zero_adapter_calls(tmp_path):
    clock = FakeClock()
    service, cache, adapters = _warming_service(tmp_path, clock)
    result = service.lookup(UNKNOWN_ISIN)
    assert result.has_facts() is False
    assert result.failure_code == FAILURE_RATE_LIMITED
    assert cache.network_blocked() is True
    for name in SOURCE_PRIORITY:
        assert adapters[name].calls == []
