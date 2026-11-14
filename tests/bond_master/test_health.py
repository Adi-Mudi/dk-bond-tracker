from src.bond_master.base import (
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    SOURCE_PRIORITY,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.health import HealthView, SourceEvent, health_view
from src.bond_master.service import BondMasterService

ISIN = "INE205A07DV2"


def event(source, ok, code, at):
    return SourceEvent(source=source, isin=ISIN, ok=ok, failure_code=code, at=at)


def test_failure_code_is_visible_per_source():
    view = HealthView(
        [
            event("NSDL", False, FAILURE_TIMEOUT, 1000.0),
            event("RBI", True, FAILURE_OK, 1001.0),
        ]
    )
    assert view.status("NSDL").failure_code == FAILURE_TIMEOUT
    assert view.status("RBI").failure_code == FAILURE_OK


def test_last_success_and_last_failure_are_recorded():
    view = HealthView(
        [
            event("NSDL", False, FAILURE_NOT_FOUND, 1000.0),
            event("NSDL", True, FAILURE_OK, 1010.0),
            event("NSDL", False, FAILURE_TIMEOUT, 1020.0),
        ]
    )
    status = view.status("NSDL")
    assert status.last_success == 1010.0
    assert status.last_failure == 1020.0
    assert status.failure_code == FAILURE_TIMEOUT


def test_failure_code_survives_a_later_success():
    view = HealthView(
        [
            event("BSE", False, FAILURE_NOT_FOUND, 1000.0),
            event("BSE", True, FAILURE_OK, 1005.0),
        ]
    )
    status = view.status("BSE")
    assert status.failure_code == FAILURE_NOT_FOUND
    assert status.healthy() is False


def test_sources_are_listed_in_priority_order():
    view = HealthView([event("BSE", False, FAILURE_TIMEOUT, 1000.0)])
    assert [status.source for status in view.sources()] == list(SOURCE_PRIORITY)


def test_unseen_source_is_ok_with_no_timestamps():
    status = HealthView([]).status("NSE")
    assert status.failure_code == FAILURE_OK
    assert status.last_success is None
    assert status.last_failure is None
    assert status.healthy() is True


def test_as_dict_covers_every_source():
    view = HealthView([event("NSDL", False, FAILURE_TIMEOUT, 1000.0)])
    data = view.as_dict()
    assert set(data) == set(SOURCE_PRIORITY)
    assert data["NSDL"]["failure_code"] == FAILURE_TIMEOUT


class FakeAdapter:
    def __init__(self, name, result):
        self.name = name
        self._result = result

    def fetch(self, isin):
        return self._result


def test_af06_health_view_shows_the_failing_source_code(tmp_path):
    adapters = {
        "NSDL": FakeAdapter("NSDL", FetchResult(isin=ISIN, failure_code=FAILURE_TIMEOUT)),
        "RBI": FakeAdapter(
            "RBI",
            FetchResult(isin=ISIN, company="Acme Ltd", sources={"company": "RBI"}),
        ),
    }
    cache = BondMasterCache(tmp_path / "bonds.db")
    service = BondMasterService(adapters, cache, sleep=lambda seconds: None)
    service.lookup(ISIN)
    view = health_view(service)
    assert view.status("NSDL").failure_code == FAILURE_TIMEOUT
    assert view.status("NSDL").healthy() is False
    assert view.status("RBI").failure_code == FAILURE_OK
    assert view.status("RBI").healthy() is True
