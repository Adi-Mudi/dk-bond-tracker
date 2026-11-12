import sys
import types

import pytest

from src.bond_master.base import (
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    SOURCE_PRIORITY,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.nse import NseAdapter
from src.bond_master.service import BondMasterService, default_adapters

ISIN = "INE205A07DV2"
OTHER_ISIN = "INE205A07DW3"


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


def found(isin, source):
    return FetchResult(isin=isin, company="Acme Ltd", sources={"company": source})


def failed(isin, code):
    return FetchResult(isin=isin, failure_code=code)


@pytest.fixture
def now():
    return [1000.0]


@pytest.fixture
def build(tmp_path, now):
    def _build(adapters, **kwargs):
        sleeps = []
        cache = BondMasterCache(tmp_path / "bonds.db", clock=lambda: now[0])
        service = BondMasterService(
            adapters,
            cache,
            clock=lambda: now[0],
            sleep=sleeps.append,
            throttle_seconds=kwargs.pop("throttle_seconds", 0.0),
            **kwargs,
        )
        return service, cache, sleeps

    return _build


def test_failover_tries_sources_in_priority_order_and_first_answer_wins(build):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_NOT_FOUND)]),
        "RBI": FakeAdapter("RBI", [failed(ISIN, FAILURE_UNREACHABLE)]),
        "NSE": FakeAdapter("NSE", [found(ISIN, "NSE")]),
        "BSE": FakeAdapter("BSE", [found(ISIN, "BSE")]),
    }
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSE"
    assert adapters["NSDL"].calls == [ISIN]
    assert adapters["RBI"].calls == [ISIN]
    assert adapters["NSE"].calls == [ISIN]
    assert adapters["BSE"].calls == []


def test_first_source_success_stops_the_chain(build):
    adapters = {name: FakeAdapter(name, [found(ISIN, name)]) for name in SOURCE_PRIORITY}
    service, _, _ = build(adapters)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSDL"
    assert adapters["NSDL"].calls == [ISIN]
    for name in ("RBI", "NSE", "BSE"):
        assert adapters[name].calls == []


def test_priority_order_comes_from_base_not_the_registry(build):
    adapters = {
        "BSE": FakeAdapter("BSE", [found(ISIN, "BSE")]),
        "NSE": FakeAdapter("NSE", [found(ISIN, "NSE")]),
    }
    service, _, _ = build(adapters)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSE"
    assert adapters["BSE"].calls == []


def test_session_cache_serves_a_repeat_lookup_without_a_second_request(build):
    adapters = {name: FakeAdapter(name, [found(ISIN, name)]) for name in SOURCE_PRIORITY}
    service, _, _ = build(adapters)
    service.lookup(ISIN)
    service.lookup(ISIN)
    assert adapters["NSDL"].calls == [ISIN]
    for name in ("RBI", "NSE", "BSE"):
        assert adapters[name].calls == []


def test_repeat_lookup_of_a_failed_isin_is_served_from_the_session(build):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_NOT_FOUND)]),
        "BSE": FakeAdapter("BSE", [failed(ISIN, FAILURE_TIMEOUT)]),
    }
    service, _, _ = build(adapters, retries=0)
    first = service.lookup(ISIN)
    second = service.lookup(ISIN)
    assert first.failure_code == second.failure_code == FAILURE_TIMEOUT
    assert adapters["NSDL"].calls == [ISIN]
    assert adapters["BSE"].calls == [ISIN]


def test_cooldown_blocks_a_second_new_lookup_within_the_window(build, now):
    adapters = {name: FakeAdapter(name, [found(ISIN, name)]) for name in SOURCE_PRIORITY}
    service, _, _ = build(adapters)
    assert service.lookup(ISIN).has_facts()
    blocked = service.lookup(OTHER_ISIN)
    assert blocked.failure_code == FAILURE_RATE_LIMITED
    assert adapters["NSDL"].calls == [ISIN]
    now[0] += 60.0
    assert service.lookup(OTHER_ISIN).has_facts()
    assert adapters["NSDL"].calls == [ISIN, OTHER_ISIN]


def test_adapter_exception_never_propagates_and_fails_over(build):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [RuntimeError("boom")]),
        "RBI": FakeAdapter("RBI", [found(ISIN, "RBI")]),
    }
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "RBI"


def test_total_failure_returns_a_failure_code_never_raises(build):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_TIMEOUT)]),
        "BSE": FakeAdapter("BSE", [failed(ISIN, FAILURE_NOT_FOUND)]),
    }
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.has_facts() is False
    assert result.failure_code == FAILURE_TIMEOUT


def test_network_failure_is_retried_with_backoff_then_succeeds(build):
    nsdl = FakeAdapter(
        "NSDL",
        [
            failed(ISIN, FAILURE_UNREACHABLE),
            failed(ISIN, FAILURE_UNREACHABLE),
            found(ISIN, "NSDL"),
        ],
    )
    service, _, sleeps = build({"NSDL": nsdl}, retries=2, retry_backoff=0.5)
    result = service.lookup(ISIN)
    assert result.has_facts()
    assert len(nsdl.calls) == 3
    assert sleeps == [0.5, 1.0]


def test_not_found_is_not_retried(build):
    nsdl = FakeAdapter("NSDL", [failed(ISIN, FAILURE_NOT_FOUND)])
    service, _, sleeps = build({"NSDL": nsdl}, retries=2)
    service.lookup(ISIN)
    assert len(nsdl.calls) == 1
    assert sleeps == []


def test_malformed_is_not_retried(build):
    nse_adapter = FakeAdapter("NSE", [failed(ISIN, FAILURE_MALFORMED)])
    service, _, sleeps = build({"NSE": nse_adapter}, retries=2)
    service.lookup(ISIN)
    assert len(nse_adapter.calls) == 1
    assert sleeps == []


def test_html_at_http_200_is_malformed_and_never_retried(build):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return "<html>blocked by the firewall</html>"

    service, _, _ = build({"NSE": NseAdapter(transport=transport)}, retries=2)
    result = service.lookup(ISIN)
    assert result.failure_code == FAILURE_MALFORMED
    assert len(calls) == 1


def test_invalid_isin_short_circuits_without_touching_adapters(build):
    nsdl = FakeAdapter("NSDL", [found(ISIN, "NSDL")])
    service, _, _ = build({"NSDL": nsdl})
    result = service.lookup("nope")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert nsdl.calls == []


def test_sources_without_an_adapter_are_skipped(build):
    bse = FakeAdapter("BSE", [found(ISIN, "BSE")])
    service, _, _ = build({"BSE": bse})
    result = service.lookup(ISIN)
    assert result.source_of("company") == "BSE"


def test_global_throttle_spaces_out_source_requests(build):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_NOT_FOUND)]),
        "RBI": FakeAdapter("RBI", [failed(ISIN, FAILURE_NOT_FOUND)]),
    }
    service, _, sleeps = build(adapters, throttle_seconds=2.0, retries=0)
    service.lookup(ISIN)
    assert sleeps == [2.0]


def test_service_records_an_event_per_source_attempt(build):
    adapters = {
        "NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_NOT_FOUND)]),
        "NSE": FakeAdapter("NSE", [found(ISIN, "NSE")]),
    }
    service, _, _ = build(adapters, retries=0)
    service.lookup(ISIN)
    events = service.events()
    assert [(item.source, item.ok) for item in events] == [("NSDL", False), ("NSE", True)]
    assert events[0].failure_code == FAILURE_NOT_FOUND


def test_sources_lists_the_registry_in_priority_order(build):
    adapters = {
        "BSE": FakeAdapter("BSE", []),
        "NSDL": FakeAdapter("NSDL", []),
    }
    service, _, _ = build(adapters)
    assert service.sources() == ("NSDL", "BSE")


def test_default_adapters_builds_all_four_sources_lazily(monkeypatch):
    def fake_module(class_name):
        module = types.ModuleType("fake")
        setattr(
            module,
            class_name,
            lambda transport=None, timeout=None: types.SimpleNamespace(name=class_name),
        )
        return module

    monkeypatch.setitem(sys.modules, "src.bond_master.nsdl", fake_module("NsdlAdapter"))
    monkeypatch.setitem(sys.modules, "src.bond_master.rbi", fake_module("RbiAdapter"))
    adapters = default_adapters(transport=lambda url, timeout: "")
    assert set(adapters) == set(SOURCE_PRIORITY)
