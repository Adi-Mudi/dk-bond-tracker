import re
from pathlib import Path

from src.app import create_app
from src.bond_master.base import (
    FAILURE_PARSE_ERROR,
    FAILURE_UNREACHABLE,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.nsdl import NsdlAdapter
from src.bond_master.service import BondMasterService
from src.db import get_conn
from src.views.watch import (
    FETCH_FOUND,
    FETCH_IDLE,
    FETCH_NOT_FOUND,
    FETCH_OFFLINE,
    FETCH_STATES,
    POSITION_FIELDS,
    fetch_payload,
    fetch_state,
)

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
TEMPLATE = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")

ISIN = "INE205A07DV2"
COMPANY = "Acme Infrastructure Ltd"
NSDL_MASTER = "nsdl_corporate_bond_master.json"
FETCHED_AT = "11 Nov 2026, 09:42"

INSTRUMENT_SOURCE_FIELDS = (
    "company",
    "rating",
    "rating_agency",
    "coupon_pct",
    "issuer_type",
    "secured",
    "face_value",
    "payout_cycle",
)



def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def nsdl_transport(calls=None, body=None):
    payload = fixture_text(NSDL_MASTER) if body is None else body

    def transport(url, timeout):
        if calls is not None:
            calls.append(url)
        return payload

    return transport


def make_client(db_path, transport=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    if transport is not None:
        app.config["BOND_MASTER_TRANSPORT"] = transport
    return app.test_client(), app


def cache_seed(db_path):
    BondMasterCache(db_path).save(
        {
            "isin": ISIN,
            "company": COMPANY,
            "payout_cycle": "annual",
            "face_value": 1000.0,
            "rating": "AA+",
            "rating_agency": "CRISIL",
            "issuer_type": "ncd",
            "secured": 1,
            "listing_status": "listed",
            "maturity": "2030-03-31",
            "source": "NSDL",
            "fetched_at": FETCHED_AT,
        }
    )


class FakeAdapter:
    def __init__(self, name, outcome):
        self.name = name
        self._outcome = outcome

    def fetch(self, isin):
        return self._outcome


def test_tc_af_01_prefill_runs_once_with_source_labels(db_path):
    calls = []
    client, _ = make_client(db_path, nsdl_transport(calls))
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert f'value="{COMPANY}"' in html
    assert 'name="coupon_pct" min="0" step="0.01" value="8.75"' in html
    assert 'name="face_value" step="any" min="0" placeholder="1000.00" value="1000"' in html
    for field in INSTRUMENT_SOURCE_FIELDS:
        assert f'data-fetch-source="{field}">NSDL<' in html, field
    assert len(calls) == 1
    client.get(f"/watch?isin={ISIN}")
    assert len(calls) == 1


def test_tc_af_01_position_facts_are_never_prefilled(db_path):
    client, _ = make_client(db_path, nsdl_transport())
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert f'value="{COMPANY}"' in html
    assert 'name="watch_investment" step="any" min="0" placeholder="0.00" value=""' in html
    assert 'name="qty" step="1" min="1" placeholder="1" value=""' in html
    for name in ("amount", "start_date", "end_date", "credit_day"):
        assert f'name="{name}"' not in html, name
    result = FetchResult(isin=ISIN, company=COMPANY, sources={"company": "NSDL"})
    payload = fetch_payload(result)
    assert payload["state"] == FETCH_FOUND
    assert set(POSITION_FIELDS).isdisjoint(payload["facts"])
    assert set(POSITION_FIELDS).isdisjoint(payload["values"])


def test_tc_af_12_render_shows_exactly_the_six_states(db_path):
    client, _ = make_client(db_path, nsdl_transport())
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    states = re.findall(r'data-fetch-state="([a-z]+)"', html)
    assert states == list(FETCH_STATES)
    assert 'data-fetch-state="found" hidden' not in html


def test_tc_af_12_template_declares_six_states_and_no_check_digit_state():
    states = re.findall(r'data-fetch-state="([a-z]+)"', TEMPLATE)
    assert states == list(FETCH_STATES)
    lowered = TEMPLATE.lower()
    for token in ("check-digit", "check_digit", "checkdigit", "checksum", "iso 6166"):
        assert token not in lowered, token


def test_tc_af_02_ui_save_works_when_the_fetch_found_nothing(db_path):
    client, _ = make_client(db_path, nsdl_transport(body='{"records": []}'))
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'data-fetch-state="notfound" hidden' not in html
    assert "Metadata not found" in html
    assert "enter manually" in html
    response = client.post(
        "/watch",
        data={
            "company": "My Own Typed Co",
            "isin": ISIN,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT company FROM bonds WHERE isin = ?", (ISIN,)
        ).fetchone()
    assert row is not None
    assert row["company"] == "My Own Typed Co"


def test_tc_af_02_ui_save_works_when_the_fetch_failed(db_path):
    def offline(url, timeout):
        raise OSError("no network")

    client, _ = make_client(db_path, offline)
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'data-fetch-state="offline" hidden' not in html
    response = client.post(
        "/watch",
        data={
            "company": "Failed Fetch Co",
            "isin": ISIN,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        assert (
            conn.execute("SELECT COUNT(*) c FROM bonds WHERE isin = ?", (ISIN,)).fetchone()["c"]
            == 1
        )


def test_tc_af_03_offline_offers_cached_values_with_as_of(db_path):
    cache_seed(db_path)

    def offline(url, timeout):
        raise OSError("no network")

    client, _ = make_client(db_path, offline)
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'data-fetch-state="offline" hidden' not in html
    assert "Could not reach the source" in html
    assert FETCHED_AT in html
    assert 'class="fetch-source fetch-source-cached"' in html
    assert COMPANY in html


def test_tc_af_05_user_edited_field_survives_the_in_form_refresh(db_path):
    calls = []
    client, _ = make_client(db_path, nsdl_transport(calls))
    html = client.get(
        f"/watch?isin={ISIN}&coupon_pct=9.9&dirty=coupon_pct"
    ).get_data(as_text=True)
    assert 'name="coupon_pct" min="0" step="0.01" value="9.9"' in html
    assert 'data-fetch-source="coupon_pct"' not in html
    again = client.get(
        f"/watch?isin={ISIN}&coupon_pct=9.9&dirty=coupon_pct"
    ).get_data(as_text=True)
    assert 'value="9.9"' in again
    assert len(calls) == 1


def test_af_05_form_side_dirty_tracking_is_wired():
    assert 'name="dirty"' in TEMPLATE
    assert 'id="c-dirty"' in TEMPLATE
    assert "dirty[name] = true" in TEMPLATE


def test_tc_af_12_downgrade_state_when_a_higher_source_is_down(db_path):
    service = BondMasterService(
        {
            "NSDL": FakeAdapter("NSDL", FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE)),
            "RBI": FakeAdapter(
                "RBI", FetchResult(isin=ISIN, company="RBI Co", sources={"company": "RBI"})
            ),
        },
        BondMasterCache(db_path),
        throttle_seconds=0.0,
        retries=0,
    )
    client, app = make_client(db_path, None)
    app.extensions["bond_master_service"] = service
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'data-fetch-state="downgrade" hidden' not in html
    assert "lesser-confidence source" in html
    assert 'data-fetch-source="company">RBI<' in html


def test_f4_parse_error_path_uses_the_nsdl_fixture(db_path):
    good = fixture_text(NSDL_MASTER)
    truncated = good[: len(good) // 2]
    adapter = NsdlAdapter(transport=lambda url, timeout: truncated)
    result = adapter.fetch(ISIN)
    assert result.failure_code == FAILURE_PARSE_ERROR
    client, _ = make_client(db_path, nsdl_transport(body=truncated))
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'data-fetch-state="notfound" hidden' not in html
    assert "Metadata not found" in html
    response = client.post(
        "/watch",
        data={
            "company": "Parse Error Co",
            "isin": ISIN,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        assert (
            conn.execute("SELECT COUNT(*) c FROM bonds WHERE isin = ?", (ISIN,)).fetchone()["c"]
            == 1
        )


def test_fetch_state_maps_failure_codes():
    assert fetch_state(None) == FETCH_IDLE
    assert (
        fetch_state(FetchResult(isin=ISIN, failure_code=FAILURE_PARSE_ERROR))
        == FETCH_NOT_FOUND
    )
    assert (
        fetch_state(FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE))
        == FETCH_OFFLINE
    )
    assert (
        fetch_state(FetchResult(isin=ISIN, company=COMPANY, sources={"company": "NSDL"}))
        == FETCH_FOUND
    )
