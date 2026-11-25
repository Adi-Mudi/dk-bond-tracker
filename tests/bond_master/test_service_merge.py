from src.bond_master.base import SOURCE_PRIORITY, FetchResult
from src.bond_master.cache import BondMasterCache
from src.bond_master import service as service_module
from src.bond_master.service import BondMasterService
from src.bond_master.snapshot import SNAPSHOT_SOURCE
from src.db import init_db

ISIN = "INE205A07DV2"


class FakeAdapter:
    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.calls = []

    def fetch(self, isin):
        self.calls.append(isin)
        return self._result


def make_service(tmp_path, adapters):
    init_db(tmp_path / "bonds.db")
    cache = BondMasterCache(tmp_path / "bonds.db")
    return BondMasterService(
        adapters, cache, sleep=lambda _delay: None, throttle_seconds=0.0, retries=0
    )


def seed(monkeypatch, result):
    monkeypatch.setattr(service_module, "snapshot_lookup", lambda isin: result)


def test_af01_2_snapshot_seed_with_official_facts_answers_without_a_fetch(tmp_path, monkeypatch):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(isin=ISIN, company="NSDL Co", sources={"company": "NSDL"}),
        ),
    }
    seed(
        monkeypatch,
        FetchResult(
            isin=ISIN,
            company="Seed Co",
            rating="AA+",
            rating_agency="CRISIL",
            sources={
                "company": SNAPSHOT_SOURCE,
                "rating": SNAPSHOT_SOURCE,
                "rating_agency": SNAPSHOT_SOURCE,
            },
        ),
    )
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.company == "Seed Co"
    assert result.source_of("company") == SNAPSHOT_SOURCE
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"
    assert result.source_of("rating") == SNAPSHOT_SOURCE
    assert adapters["NSDL"].calls == []


def test_af01_2_nsdl_fills_the_official_fields_missing_from_the_seed(tmp_path, monkeypatch):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(
                isin=ISIN,
                company="NSDL Co",
                rating="AA+",
                rating_agency="CRISIL",
                sources={"company": "NSDL", "rating": "NSDL", "rating_agency": "NSDL"},
            ),
        ),
    }
    seed(
        monkeypatch,
        FetchResult(
            isin=ISIN,
            company="Seed Co",
            coupon=9.0,
            sources={"company": SNAPSHOT_SOURCE, "coupon": SNAPSHOT_SOURCE},
        ),
    )
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.company == "Seed Co"
    assert result.source_of("company") == SNAPSHOT_SOURCE
    assert result.coupon == 9.0
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"
    assert result.source_of("rating") == "NSDL"
    assert result.source_of("rating_agency") == "NSDL"
    assert adapters["NSDL"].calls == [ISIN]


def test_af01_2_fields_fall_back_nsdl_then_snapshot(tmp_path, monkeypatch):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL", FetchResult(isin=ISIN, company="Acme Ltd", sources={"company": "NSDL"})
        ),
    }
    seed(
        monkeypatch,
        FetchResult(
            isin=ISIN,
            coupon=9.0,
            maturity="2030-03-31",
            sources={"coupon": SNAPSHOT_SOURCE, "maturity": SNAPSHOT_SOURCE},
        ),
    )
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSDL"
    assert result.source_of("coupon") == SNAPSHOT_SOURCE
    assert result.source_of("maturity") == SNAPSHOT_SOURCE
    assert result.source_of("face_value") is None


def test_af01_2_nsdl_result_fills_the_gap_when_no_seed_exists(tmp_path, monkeypatch):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL", FetchResult(isin=ISIN, company="NSDL Co", sources={"company": "NSDL"})
        ),
    }
    seed(monkeypatch, None)
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.company == "NSDL Co"
    assert result.source_of("company") == "NSDL"


def test_af01_2_repeat_lookup_merges_the_cached_session_results(tmp_path, monkeypatch):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(
                isin=ISIN,
                company="Acme Ltd",
                rating="AA+",
                rating_agency="CRISIL",
                sources={"company": "NSDL", "rating": "NSDL", "rating_agency": "NSDL"},
            ),
        ),
    }
    seed(monkeypatch, None)
    service = make_service(tmp_path, adapters)
    service.lookup(ISIN)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSDL"
    assert result.source_of("rating") == "NSDL"
    assert adapters["NSDL"].calls == [ISIN]


def test_af01_2_merge_never_raises_when_nothing_is_found(tmp_path, monkeypatch):
    adapters = {
        name: FakeAdapter(name, FetchResult(isin=ISIN))
        for name in SOURCE_PRIORITY
    }
    seed(monkeypatch, None)
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.has_facts() is False


def test_f5_merge_keeps_only_the_grade_when_the_agency_column_is_populated(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(
                isin=ISIN,
                company="Acme Ltd",
                rating="CRISIL AA+",
                rating_agency="ICRA",
                sources={"company": "NSDL", "rating": "NSDL", "rating_agency": "NSDL"},
            ),
        ),
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.rating == "AA+"
    assert result.rating_agency == "ICRA"
    assert result.source_of("rating") == "NSDL"
    assert result.source_of("rating_agency") == "NSDL"


def test_f5_merge_resolves_the_embedded_agency_when_the_column_is_empty(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(
                isin=ISIN,
                company="Acme Ltd",
                rating="CARE BBB+",
                sources={"company": "NSDL", "rating": "NSDL"},
            ),
        ),
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.rating == "BBB+"
    assert result.rating_agency == "CARE"
    assert result.source_of("rating") == "NSDL"
    assert result.source_of("rating_agency") == "NSDL"


def test_f5_merge_is_idempotent_for_already_clean_values(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(
                isin=ISIN,
                company="Acme Ltd",
                rating="AA+",
                rating_agency="CRISIL",
                sources={"company": "NSDL", "rating": "NSDL", "rating_agency": "NSDL"},
            ),
        ),
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"
    assert result.source_of("rating") == "NSDL"
    assert result.source_of("rating_agency") == "NSDL"
