from datetime import date, timedelta
from pathlib import Path

import pytest

from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.db import get_conn
from src.validators import add_months

NSDL_FIXTURE = (
    Path(__file__).resolve().parent / "bond_master" / "fixtures" / "nsdl_corporate_bond_master.json"
)

_START = date.today() - timedelta(days=30)
_START_ISO = _START.isoformat()
_END_ISO = add_months(_START, 36).isoformat()


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def watch_candidate(client, isin, **overrides):
    data = {
        "company": "Maturity Co",
        "isin": isin,
        "rating": "AA",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
    }
    data.update(overrides)
    return client.post("/watch", data=data)


def candidate_row(db_path, isin):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id, maturity_date, listing_status FROM bonds WHERE isin = ?",
            (isin,),
        ).fetchone()


def test_tc271_30_candidate_save_persists_maturity_and_listing(client, db_path):
    response = watch_candidate(
        client,
        "INE9000A0271",
        maturity_date="2029-06-30",
        listing_status="listed",
    )
    assert response.status_code == 302
    row = candidate_row(db_path, "INE9000A0271")
    assert row["maturity_date"] == "2029-06-30"
    assert row["listing_status"] == "listed"


def test_tc271_31_candidate_save_defaults_when_fetch_is_missing(client, db_path):
    response = watch_candidate(client, "INE9000A0272")
    assert response.status_code == 302
    row = candidate_row(db_path, "INE9000A0272")
    assert row["maturity_date"] is None
    assert row["listing_status"] == "unknown"


def test_tc271_29_fetch_capture_saves_cached_maturity_and_listing(db_path):
    isin = "INE205A07DV2"
    cache = BondMasterCache(db_path, cooldown_seconds=0)
    cache.save(
        {
            "isin": isin,
            "company": "Fetch Capture Co",
            "rating": "AA+",
            "listing_status": "listed",
            "maturity": "2031-12-31",
            "source": "NSDL",
            "fetched_at": "11 Nov 2026, 09:42",
        }
    )
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    payload = NSDL_FIXTURE.read_text(encoding="utf-8")
    app.config["BOND_MASTER_TRANSPORT"] = lambda url, timeout: payload
    app.extensions["bond_master_cache"] = cache
    client = app.test_client()
    html = client.get(f"/watch?isin={isin}").get_data(as_text=True)
    assert 'data-fetch-state="found"' in html
    assert 'value="2031-12-31"' in html
    assert 'value="listed"' in html
    response = client.post(
        "/watch",
        data={
            "company": "Fetch Capture Co",
            "isin": isin,
            "rating": "AA+",
            "coupon_pct": "8.75",
            "expected_yield_pct": "8.5",
            "maturity_date": "2031-12-31",
            "listing_status": "listed",
        },
    )
    assert response.status_code == 302
    row = candidate_row(db_path, isin)
    assert row["maturity_date"] == "2031-12-31"
    assert row["listing_status"] == "listed"


def test_tc271_29_first_fetch_capture_saves_fetched_maturity_and_listing(db_path):
    isin = "INE205A07DV2"
    cache = BondMasterCache(db_path, cooldown_seconds=0)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    payload = NSDL_FIXTURE.read_text(encoding="utf-8")
    app.config["BOND_MASTER_TRANSPORT"] = lambda url, timeout: payload
    app.extensions["bond_master_cache"] = cache
    client = app.test_client()
    html = client.get(f"/watch?isin={isin}").get_data(as_text=True)
    assert 'data-fetch-state="found"' in html
    assert 'value="2030-03-31"' in html
    assert 'value="listed"' in html
    response = client.post(
        "/watch",
        data={
            "company": "First Fetch Co",
            "isin": isin,
            "rating": "AA+",
            "coupon_pct": "8.75",
            "expected_yield_pct": "8.5",
            "maturity_date": "2030-03-31",
            "listing_status": "listed",
        },
    )
    assert response.status_code == 302
    row = candidate_row(db_path, isin)
    assert row["maturity_date"] == "2030-03-31"
    assert row["listing_status"] == "listed"


def test_tc271_24_25_carry_maturity_and_listing_from_candidate_to_holding(client, db_path):
    watch_candidate(
        client,
        "INE9000A0273",
        maturity_date="2030-03-31",
        listing_status="unlisted",
    )
    cid = candidate_row(db_path, "INE9000A0273")["id"]
    response = client.post(
        f"/watch/{cid}/move",
        data={
            "start_date": _START_ISO,
            "end_date": _END_ISO,
            "credit_day": "5",
            "purchase_date": _START_ISO,
            "qty": "10",
            "amount": "10000",
            "broker": "Broker X",
        },
    )
    assert response.status_code in (200, 302)
    row = candidate_row(db_path, "INE9000A0273")
    assert row["maturity_date"] == "2030-03-31"
    assert row["listing_status"] == "unlisted"
