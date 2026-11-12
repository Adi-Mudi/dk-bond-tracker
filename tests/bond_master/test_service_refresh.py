from src.bond_master import service as svc
from src.bond_master.base import SOURCE_PRIORITY, FAILURE_UNREACHABLE
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService, refresh_all


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


def test_af10_1_auto_refresh_runs_exactly_once_per_process(db_path, monkeypatch):
    calls = []
    monkeypatch.setattr(svc, "_AUTO_REFRESH_DONE", False)
    monkeypatch.setattr(svc, "_CACHES", {})
    monkeypatch.setattr(svc, "build_default_service", offline_builder(calls))
    refresh_all(str(db_path), "auto")
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
