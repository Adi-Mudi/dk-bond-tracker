import sys
import types

import pytest

from src.bond_master import service as service_module
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    INSTRUMENT_FIELDS,
    SOURCE_PRIORITY,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.nsdl import NsdlAdapter
from src.bond_master.service import BondMasterService, default_adapters
from src.db import init_db

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
        init_db(tmp_path / "bonds.db")
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


def test_lookup_consults_nsdl_and_reports_its_source(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [found(ISIN, "NSDL")])}
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSDL"
    assert adapters["NSDL"].calls == [ISIN]


def test_complete_result_never_reconsults_the_snapshot_seed(build, monkeypatch):
    complete = FetchResult(
        isin=ISIN,
        company="Complete Co",
        coupon=8.75,
        payout_cycle="annual",
        face_value=1000.0,
        rating="AA+",
        rating_agency="CRISIL",
        issuer_type="ncd",
        secured=1,
        listing_status="listed",
        maturity="2030-03-31",
        sources={field: "NSDL" for field in INSTRUMENT_FIELDS},
    )
    adapters = {"NSDL": FakeAdapter("NSDL", [complete])}
    service, _, _ = build(adapters)

    snapshot_calls = []

    def stub(isin):
        snapshot_calls.append(isin)
        return None

    monkeypatch.setattr(service_module, "snapshot_lookup", stub)
    result = service.lookup(ISIN)
    assert result.source_of("maturity") == "NSDL"
    assert snapshot_calls == [ISIN]
    assert adapters["NSDL"].calls == [ISIN]


def test_session_cache_serves_a_repeat_lookup_without_a_second_request(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [found(ISIN, "NSDL")])}
    service, _, _ = build(adapters)
    service.lookup(ISIN)
    service.lookup(ISIN)
    assert adapters["NSDL"].calls == [ISIN]


def test_repeat_lookup_of_a_failed_isin_is_served_from_the_session(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_TIMEOUT)])}
    service, _, _ = build(adapters, retries=0)
    first = service.lookup(ISIN)
    second = service.lookup(ISIN)
    assert first.failure_code == second.failure_code == FAILURE_TIMEOUT
    assert adapters["NSDL"].calls == [ISIN]


def test_cooldown_blocks_a_second_new_lookup_within_the_window(build, now):
    adapters = {"NSDL": FakeAdapter("NSDL", [found(ISIN, "NSDL")])}
    service, _, _ = build(adapters)
    assert service.lookup(ISIN).has_facts()
    blocked = service.lookup(OTHER_ISIN)
    assert blocked.failure_code == FAILURE_RATE_LIMITED
    assert adapters["NSDL"].calls == [ISIN]
    now[0] += 60.0
    assert service.lookup(OTHER_ISIN).has_facts()
    assert adapters["NSDL"].calls == [ISIN, OTHER_ISIN]


def test_adapter_exception_never_propagates(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [RuntimeError("boom")])}
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.has_facts() is False


def test_total_failure_returns_a_failure_code_never_raises(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_TIMEOUT)])}
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.has_facts() is False
    assert result.failure_code == FAILURE_TIMEOUT


def test_not_found_total_failure_is_reported(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [failed(ISIN, FAILURE_NOT_FOUND)])}
    service, _, _ = build(adapters, retries=0)
    result = service.lookup(ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND


def test_registry_without_nsdl_reports_not_found(build):
    service, _, _ = build({}, retries=0)
    result = service.lookup(ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND


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
    nsdl = FakeAdapter("NSDL", [failed(ISIN, FAILURE_MALFORMED)])
    service, _, sleeps = build({"NSDL": nsdl}, retries=2)
    service.lookup(ISIN)
    assert len(nsdl.calls) == 1
    assert sleeps == []


def test_html_at_http_200_is_blocked_by_the_adapter(build):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return "<html>blocked by the firewall</html>"

    adapter = NsdlAdapter(
        transport=transport, retry_delay=0, sleep=lambda seconds: None
    )
    service, _, _ = build({"NSDL": adapter}, retries=2)
    result = service.lookup(ISIN)
    assert result.failure_code == FAILURE_BLOCKED
    assert len(calls) == 3


def test_invalid_isin_short_circuits_without_touching_adapters(build):
    nsdl = FakeAdapter("NSDL", [found(ISIN, "NSDL")])
    service, _, _ = build({"NSDL": nsdl})
    result = service.lookup("nope")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert nsdl.calls == []


def test_throttle_paces_retry_attempts(build):
    nsdl = FakeAdapter(
        "NSDL",
        [
            failed(ISIN, FAILURE_UNREACHABLE),
            failed(ISIN, FAILURE_UNREACHABLE),
            found(ISIN, "NSDL"),
        ],
    )
    service, _, sleeps = build(
        {"NSDL": nsdl}, retries=2, retry_backoff=0.5, throttle_seconds=2.0
    )
    result = service.lookup(ISIN)
    assert result.has_facts()
    assert sleeps == [2.0, 2.0]


def test_service_records_an_event_per_source_attempt(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [found(ISIN, "NSDL")])}
    service, _, _ = build(adapters, retries=0)
    service.lookup(ISIN)
    events = service.events()
    assert [(item.source, item.ok) for item in events] == [("NSDL", True)]


def test_sources_lists_the_registry(build):
    adapters = {"NSDL": FakeAdapter("NSDL", [])}
    service, _, _ = build(adapters)
    assert service.sources() == ("NSDL",)


def test_default_adapters_builds_the_single_source_lazily(monkeypatch):
    def fake_module(class_name):
        module = types.ModuleType("fake")
        setattr(
            module,
            class_name,
            lambda transport=None, timeout=None: types.SimpleNamespace(name=class_name),
        )
        return module

    monkeypatch.setitem(sys.modules, "src.bond_master.nsdl", fake_module("NsdlAdapter"))
    adapters = default_adapters(transport=lambda url, timeout: "")
    assert set(adapters) == set(SOURCE_PRIORITY) == {"NSDL"}
