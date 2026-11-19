import json
import re
from pathlib import Path

from src.app import create_app
from src.bond_master.base import FAILURE_UNREACHABLE, FetchResult
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService
from src.bond_master.snapshot import SNAPSHOT_SOURCE, snapshot_lookup
from src.db import init_db
from src.views.watch import ONLINE_FACT_FIELDS

SNAPSHOT_ISIN = "INE2YB724070"
NSDL_ISIN = "INE205A07DV2"
OFFICIAL_FIELDS = ("rating", "rating_agency", "issuer_type", "payout_cycle", "secured")
SNAPSHOT_FIELDS = ("company", "coupon", "maturity")
FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"


class FakeAdapter:
    def __init__(self, name, result):
        self.name = name
        self._result = result
        self.calls = []

    def fetch(self, isin):
        self.calls.append(isin)
        return self._result


def make_service(tmp_path, adapters, db_name="bonds.db", cooldown_seconds=60):
    db = tmp_path / db_name
    init_db(db)
    cache = BondMasterCache(db, cooldown_seconds=cooldown_seconds)
    service = BondMasterService(
        adapters, cache, sleep=lambda _delay: None, throttle_seconds=0.0, retries=0
    )
    return service, cache


def official_result(isin):
    return FetchResult(
        isin=isin,
        rating="AA",
        rating_agency="CARE",
        issuer_type="municipal",
        payout_cycle="annual",
        secured=0,
        sources={field: "NSDL" for field in OFFICIAL_FIELDS},
    )


def nsdl_body(isin):
    document = json.loads(
        (FIXTURES / "nsdl_corporate_bond_master.json").read_text(encoding="utf-8")
    )
    record = dict(document["records"][0])
    record["isin"] = isin
    return json.dumps({**document, "records": [record]})


def make_client(db_path, transport):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = transport
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client()


def popup_from(html):
    start = html.index('id="fetch-details"')
    end = html.index("table-wrap watch-scroll", start)
    return html[start:end]


def test_v1_lookup_merges_official_facts_for_snapshot_known_isin(tmp_path):
    assert snapshot_lookup(SNAPSHOT_ISIN) is not None
    official = official_result(SNAPSHOT_ISIN)
    adapter = FakeAdapter("NSDL", official)
    service, _ = make_service(tmp_path, {"NSDL": adapter})
    result = service.lookup(SNAPSHOT_ISIN)
    seed = snapshot_lookup(SNAPSHOT_ISIN)
    for field in SNAPSHOT_FIELDS:
        assert getattr(result, field) == getattr(seed, field)
        assert result.source_of(field) == SNAPSHOT_SOURCE
    for field in OFFICIAL_FIELDS:
        assert getattr(result, field) == getattr(official, field)
        assert result.source_of(field) == "NSDL"
    assert adapter.calls == [SNAPSHOT_ISIN]


def test_v2_cooldown_active_returns_cached_official_without_hammering(tmp_path):
    official = official_result(SNAPSHOT_ISIN)
    adapter = FakeAdapter("NSDL", official)
    service, cache = make_service(tmp_path, {"NSDL": adapter})
    first = service.lookup(SNAPSHOT_ISIN)
    assert first.source_of("rating") == "NSDL"
    assert cache.cooldown_remaining() > 0
    second = service.lookup(SNAPSHOT_ISIN)
    for field in OFFICIAL_FIELDS:
        assert getattr(second, field) == getattr(official, field)
        assert second.source_of(field) == "NSDL"
    assert adapter.calls == [SNAPSHOT_ISIN]


def test_v3_popup_renders_every_fact_row_with_value_or_unavailability(db_path):
    BondMasterCache(db_path).save(
        {
            "isin": NSDL_ISIN,
            "company": "Acme Infrastructure Ltd",
            "payout_cycle": "annual",
            "face_value": 1000.0,
            "rating": "AA+",
            "rating_agency": "CRISIL",
            "issuer_type": "ncd",
            "secured": 1,
            "listing_status": "listed",
            "maturity": "2030-03-31",
            "source": "NSDL",
            "fetched_at": "11 Nov 2026, 09:42",
        }
    )

    def offline(url, timeout):
        raise OSError("network unreachable")

    html = make_client(db_path, offline).get(f"/watch?isin={NSDL_ISIN}").get_data(as_text=True)
    popup = popup_from(html)
    available = set(re.findall(r'data-fetch-detail="([^"]+)"', popup))
    unavailable = set(re.findall(r'data-fetch-unavailable="([^"]+)"', popup))
    assert available | unavailable == set(ONLINE_FACT_FIELDS)
    assert "coupon" in unavailable
    assert "not provided by this source" in popup
    for fact in available:
        assert re.search(rf'data-fetch-source="{fact}"', popup)


def test_v4_popup_shows_face_value_and_listing_status_as_form_context(db_path):
    client = make_client(db_path, lambda url, timeout: nsdl_body(NSDL_ISIN))
    html = client.get(f"/watch?isin={NSDL_ISIN}").get_data(as_text=True)
    popup = popup_from(html)
    assert 'data-fetch-context="face_value"' in popup
    assert 'data-fetch-context="listing_status"' in popup
    assert "Face value" in popup and "Listing status" in popup


def test_v5_offline_failure_preserves_three_snapshot_facts(tmp_path):
    offline = FetchResult(isin=SNAPSHOT_ISIN, failure_code=FAILURE_UNREACHABLE)
    adapter = FakeAdapter("NSDL", offline)
    service, _ = make_service(tmp_path, {"NSDL": adapter})
    result = service.lookup(SNAPSHOT_ISIN)
    seed = snapshot_lookup(SNAPSHOT_ISIN)
    assert result.has_facts()
    for field in SNAPSHOT_FIELDS:
        assert getattr(result, field) == getattr(seed, field)
        assert result.source_of(field) == SNAPSHOT_SOURCE
    for field in OFFICIAL_FIELDS:
        assert getattr(result, field) is None


def test_v6_fetch_endpoint_runs_full_collect_for_snapshot_known_isin(db_path):
    calls = []
    body = nsdl_body(SNAPSHOT_ISIN)

    def transport(url, timeout):
        calls.append(url)
        return body

    response = make_client(db_path, transport).get(f"/watch/lookup?isin={SNAPSHOT_ISIN}")
    payload = response.get_json()
    assert response.status_code == 200
    assert calls
    assert "rating" in payload["popup_facts"]
    assert "NSDL" in payload["source_names"]


def test_state_matrix_snapshot_cached_cooldown_offline(tmp_path):
    assert snapshot_lookup(SNAPSHOT_ISIN) is not None
    adapter = FakeAdapter("NSDL", official_result(SNAPSHOT_ISIN))
    service, _ = make_service(tmp_path, {"NSDL": adapter}, db_name="online.db")

    fresh = service.lookup(SNAPSHOT_ISIN)
    assert fresh.source_of("rating") == "NSDL"
    assert all(fresh.source_of(field) == SNAPSHOT_SOURCE for field in SNAPSHOT_FIELDS)

    cached = service.lookup(SNAPSHOT_ISIN)
    assert cached.source_of("rating") == "NSDL"
    assert adapter.calls == [SNAPSHOT_ISIN]

    cooldown = service.lookup(SNAPSHOT_ISIN)
    assert cooldown.source_of("rating") == "NSDL"
    assert adapter.calls == [SNAPSHOT_ISIN]

    offline_adapter = FakeAdapter(
        "NSDL", FetchResult(isin=SNAPSHOT_ISIN, failure_code=FAILURE_UNREACHABLE)
    )
    offline_service, _ = make_service(
        tmp_path, {"NSDL": offline_adapter}, db_name="offline.db"
    )
    offline = offline_service.lookup(SNAPSHOT_ISIN)
    assert offline.source_of("rating") is None
    assert all(offline.source_of(field) == SNAPSHOT_SOURCE for field in SNAPSHOT_FIELDS)
