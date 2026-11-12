import re
from unittest.mock import patch

from conftest import add_ongoing_seed
from src.app import create_app
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_RATE_LIMITED,
    FAILURE_UNREACHABLE,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService
from src.db import get_conn
from src.views.watch import (
    FETCH_OFFLINE,
    RATING_GATE_MESSAGE,
    fetch_message,
    fetch_payload,
    rating_gate,
)

ISIN = "INE205A07DV2"
COMPANY = "Acme Infrastructure Ltd"
NEW_ISIN_FETCHED = "INE4000F0001"
NEW_ISIN_TYPED = "INE4000T0001"
HOLDING_COMPANY = "Beta Finance Ltd"
HOLDING_ISIN = "IN1234567890"


class FakeAdapter:
    def __init__(self, name, outcome):
        self.name = name
        self._outcome = outcome

    def fetch(self, isin):
        return self._outcome


def service_with(db_path, result):
    return BondMasterService(
        {"NSDL": FakeAdapter("NSDL", result)},
        BondMasterCache(db_path),
        throttle_seconds=0.0,
        retries=0,
    )


def make_client(db_path, service=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    if service is not None:
        app.extensions["bond_master_service"] = service
    return app.test_client(), app


def error_banner(html):
    return re.search(r'<div id="watch-error-message">(.*?)</div>', html).group(1)


def candidate_isins(db_path):
    with get_conn(db_path) as conn:
        return [
            row["isin"]
            for row in conn.execute("SELECT isin FROM bonds ORDER BY id").fetchall()
        ]


def test_af09_1_fetched_bb_plus_refused_with_the_plain_message(db_path):
    result = FetchResult(
        isin=ISIN,
        company=COMPANY,
        rating="BB+",
        sources={"company": "NSDL", "rating": "NSDL"},
    )
    assert rating_gate(fetch_payload(result)) == RATING_GATE_MESSAGE
    client, _ = make_client(db_path, service_with(db_path, result))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    response = client.post(
        "/watch",
        data={
            "company": COMPANY,
            "isin": ISIN,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "supports only AAA to BBB-" in html
    assert error_banner(html) == RATING_GATE_MESSAGE
    assert candidate_isins(db_path) == []


def test_af09_2_fetched_unrated_refused_with_the_same_message(db_path):
    result = FetchResult(isin=ISIN, company=COMPANY, sources={"company": "NSDL"})
    assert rating_gate(fetch_payload(result)) == RATING_GATE_MESSAGE
    client, _ = make_client(db_path, service_with(db_path, result))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    response = client.post(
        "/watch",
        data={
            "company": COMPANY,
            "isin": ISIN,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert error_banner(html) == RATING_GATE_MESSAGE
    assert candidate_isins(db_path) == []


def test_af09_3_fetched_bbb_minus_accepted_and_prefilled(db_path):
    result = FetchResult(
        isin=ISIN,
        company=COMPANY,
        rating="BBB-",
        sources={"company": "NSDL", "rating": "NSDL"},
    )
    assert rating_gate(fetch_payload(result)) is None
    client, _ = make_client(db_path, service_with(db_path, result))
    page = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert f'value="{COMPANY}"' in page
    assert '<option value="BBB-" selected>BBB-</option>' in page
    response = client.post(
        "/watch",
        data={
            "company": COMPANY,
            "isin": ISIN,
            "rating": "BBB-",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    assert candidate_isins(db_path) == [ISIN]


def test_af09_fetch_failure_never_blocks_the_add(db_path):
    result = FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE)
    assert rating_gate(fetch_payload(result)) is None
    client, _ = make_client(db_path, service_with(db_path, result))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    response = client.post(
        "/watch",
        data={
            "company": "Typed After Failure Co",
            "isin": ISIN,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    assert candidate_isins(db_path) == [ISIN]


def test_af04_1_fetched_company_gets_the_same_error_as_a_typed_company(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, HOLDING_COMPANY, HOLDING_ISIN)
    result = FetchResult(
        isin=NEW_ISIN_FETCHED,
        company=HOLDING_COMPANY,
        rating="AA",
        sources={"company": "NSDL", "rating": "NSDL"},
    )
    client, _ = make_client(db_path, service_with(db_path, result))
    page = client.get(f"/watch?isin={NEW_ISIN_FETCHED}").get_data(as_text=True)
    assert f'value="{HOLDING_COMPANY}"' in page
    fetched = client.post(
        "/watch",
        data={
            "company": HOLDING_COMPANY,
            "isin": NEW_ISIN_FETCHED,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    typed = client.post(
        "/watch",
        data={
            "company": HOLDING_COMPANY,
            "isin": NEW_ISIN_TYPED,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert fetched.status_code == 409
    assert typed.status_code == 409
    fetched_message = error_banner(fetched.get_data(as_text=True))
    assert fetched_message == error_banner(typed.get_data(as_text=True))
    assert "already exists as holding" in fetched_message
    assert candidate_isins(db_path) == [HOLDING_ISIN]


def test_af04_2_fetched_company_without_a_conflict_saves(db_path):
    result = FetchResult(
        isin=NEW_ISIN_FETCHED,
        company="Fresh Fetched Co",
        rating="AA",
        sources={"company": "NSDL", "rating": "NSDL"},
    )
    client, _ = make_client(db_path, service_with(db_path, result))
    assert client.get(f"/watch?isin={NEW_ISIN_FETCHED}").status_code == 200
    response = client.post(
        "/watch",
        data={
            "company": "Fresh Fetched Co",
            "isin": NEW_ISIN_FETCHED,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    assert candidate_isins(db_path) == [NEW_ISIN_FETCHED]


def test_af10_2_three_manual_taps_inside_the_cooldown_run_once(db_path):
    client, _ = make_client(db_path)
    calls = []

    def fake_refresh_all(db_file, trigger="manual"):
        from src.views.watch import _bond_cache

        calls.append((str(db_file), trigger))
        _bond_cache().begin_refresh()
        return {"NSDL": {"status": "ok", "failure_code": "OK", "as_of": "2026-11-13T00:00:00+00:00"}}

    with patch("src.bond_master.service.refresh_all", fake_refresh_all, create=True):
        first = client.post("/watch/refresh")
        second = client.post("/watch/refresh")
        third = client.post("/watch/refresh")

    assert first.status_code == 200
    assert first.get_json()["status"] == "refreshed"
    assert first.get_json()["summary"]["NSDL"]["status"] == "ok"
    assert second.status_code == 429
    assert second.get_json()["status"] == "cooldown"
    assert third.status_code == 429
    assert third.get_json()["status"] == "cooldown"
    assert len(calls) == 1
    assert calls[0][1] == "manual"


def test_af10_2_refresh_route_passes_the_manual_trigger_and_db(db_path):
    client, app = make_client(db_path)
    seen = []

    def fake_refresh_all(db_file, trigger="manual"):
        seen.append((str(db_file), trigger))
        return {"NSDL": {"status": "ok", "failure_code": "OK", "as_of": "2026-11-13T00:00:00+00:00"}}

    with patch("src.bond_master.service.refresh_all", fake_refresh_all, create=True):
        response = client.post("/watch/refresh")

    assert response.status_code == 200
    assert seen == [(str(db_path), "manual")]


def test_offline_banner_wording_distinguishes_reach_from_blocked():
    assert fetch_message(FETCH_OFFLINE, FAILURE_UNREACHABLE) == "Could not reach the source"
    assert (
        fetch_message(FETCH_OFFLINE, FAILURE_BLOCKED)
        == "The source blocked or rate-limited the request"
    )
    assert fetch_message(FETCH_OFFLINE, FAILURE_RATE_LIMITED) == fetch_message(
        FETCH_OFFLINE, FAILURE_BLOCKED
    )
    assert fetch_message(FETCH_OFFLINE, FAILURE_UNREACHABLE) != fetch_message(
        FETCH_OFFLINE, FAILURE_BLOCKED
    )


def test_offline_blocked_fetch_renders_the_blocked_wording(db_path):
    client, _ = make_client(
        db_path, service_with(db_path, FetchResult(isin=ISIN, failure_code=FAILURE_BLOCKED))
    )
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'data-fetch-state="offline" hidden' not in html
    assert "The source blocked or rate-limited the request" in html


def test_offline_unreachable_fetch_keeps_the_reach_wording(db_path):
    client, _ = make_client(
        db_path, service_with(db_path, FetchResult(isin=ISIN, failure_code=FAILURE_UNREACHABLE))
    )
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert "Could not reach the source" in html
    assert "blocked or rate-limited" not in html
