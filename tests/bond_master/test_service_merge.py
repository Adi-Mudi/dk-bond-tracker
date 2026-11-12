from src.bond_master.base import SOURCE_PRIORITY, FetchResult
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService

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
    cache = BondMasterCache(tmp_path / "bonds.db")
    return BondMasterService(
        adapters, cache, sleep=lambda _delay: None, throttle_seconds=0.0, retries=0
    )


def test_af01_2_missing_rating_comes_from_the_next_source_with_its_agency(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL",
            FetchResult(
                isin=ISIN,
                company="Acme Ltd",
                coupon=8.75,
                sources={"company": "NSDL", "coupon": "NSDL"},
            ),
        ),
        "RBI": FakeAdapter(
            "RBI",
            FetchResult(
                isin=ISIN,
                rating="AA+",
                rating_agency="CRISIL",
                sources={"rating": "RBI", "rating_agency": "RBI"},
            ),
        ),
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.company == "Acme Ltd"
    assert result.source_of("company") == "NSDL"
    assert result.source_of("coupon") == "NSDL"
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"
    assert result.source_of("rating") == "RBI"
    assert result.source_of("rating_agency") == "RBI"


def test_af01_2_fields_fall_back_in_nsdl_rbi_nse_bse_order(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL", FetchResult(isin=ISIN, company="Acme Ltd", sources={"company": "NSDL"})
        ),
        "RBI": FakeAdapter(
            "RBI", FetchResult(isin=ISIN, coupon=9.0, sources={"coupon": "RBI"})
        ),
        "NSE": FakeAdapter(
            "NSE",
            FetchResult(
                isin=ISIN,
                rating="AA",
                rating_agency="ICRA",
                sources={"rating": "NSE", "rating_agency": "NSE"},
            ),
        ),
        "BSE": FakeAdapter(
            "BSE", FetchResult(isin=ISIN, maturity="2030-03-31", sources={"maturity": "BSE"})
        ),
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSDL"
    assert result.source_of("coupon") == "RBI"
    assert result.source_of("rating") == "NSE"
    assert result.source_of("rating_agency") == "NSE"
    assert result.source_of("maturity") == "BSE"
    assert result.source_of("face_value") is None


def test_af01_2_a_higher_priority_source_wins_the_field_it_has(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL", FetchResult(isin=ISIN, company="NSDL Co", sources={"company": "NSDL"})
        ),
        "NSE": FakeAdapter(
            "NSE", FetchResult(isin=ISIN, company="NSE Co", sources={"company": "NSE"})
        ),
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.company == "NSDL Co"
    assert result.source_of("company") == "NSDL"


def test_af01_2_repeat_lookup_merges_the_cached_session_results(tmp_path):
    adapters = {
        "NSDL": FakeAdapter(
            "NSDL", FetchResult(isin=ISIN, company="Acme Ltd", sources={"company": "NSDL"})
        ),
        "RBI": FakeAdapter(
            "RBI", FetchResult(isin=ISIN, rating="AA+", rating_agency="CRISIL", sources={"rating": "RBI"})
        ),
    }
    service = make_service(tmp_path, adapters)
    service.lookup(ISIN)
    result = service.lookup(ISIN)
    assert result.source_of("company") == "NSDL"
    assert result.source_of("rating") == "RBI"
    assert adapters["NSDL"].calls == [ISIN]
    assert adapters["RBI"].calls == [ISIN]


def test_af01_2_merge_never_raises_when_nothing_is_found(tmp_path):
    adapters = {
        name: FakeAdapter(name, FetchResult(isin=ISIN))
        for name in SOURCE_PRIORITY
    }
    service = make_service(tmp_path, adapters)
    result = service.lookup(ISIN)
    assert result.has_facts() is False
