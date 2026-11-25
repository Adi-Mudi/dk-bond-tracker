import pytest
import re

from conftest import add_ongoing_seed
from src.app import create_app
from src.bond_master.base import FetchResult
from src.bond_master.cache import BondMasterCache
from src.bond_master.service import BondMasterService
from src.db import get_conn
from src.views.watch import RATING_GATE_MESSAGE, fetch_payload, rating_gate

ISIN = "INE4000F0001"
COMPANY = "Acme Rating Gate Co"
REAL_ISIN = "INE002Z08143"
REAL_COMPANY = "WELSPUN AUNTA-SIMARIA PROJECT PRIVATE LIMITED"


class FakeAdapter:
    def __init__(self, outcome):
        self._outcome = outcome

    def fetch(self, isin):
        return self._outcome


def service_with(db_path, result):
    return BondMasterService(
        {"NSDL": FakeAdapter(result)},
        BondMasterCache(db_path),
        throttle_seconds=0.0,
        retries=0,
    )


def make_client(db_path, service=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    if service is not None:
        app.extensions["bond_master_service"] = service
    return app.test_client()


def unrated_result(isin=ISIN, company=COMPANY):
    return FetchResult(isin=isin, company=company, sources={"company": "NSDL"})


def rated_result(rating, isin=ISIN, company=COMPANY):
    return FetchResult(
        isin=isin,
        company=company,
        rating=rating,
        sources={"company": "NSDL", "rating": "NSDL"},
    )


def post_data(rating="A", isin=ISIN, company=COMPANY, **overrides):
    data = {
        "company": company,
        "isin": isin,
        "coupon_pct": "8.0",
        "expected_yield_pct": "9.2",
    }
    if rating is not None:
        data["rating"] = rating
    data.update(overrides)
    return data


def stored_row(db_path, isin=ISIN):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT isin, company, rating, coupon_pct, expected_yield_pct, maturity_date "
            "FROM bonds WHERE upper(trim(isin)) = upper(?)",
            (isin,),
        ).fetchone()


def error_banner(html):
    return re.search(r'<div id="watch-error-message">(.*?)</div>', html).group(1)


def test_gate_unit_no_fetch_payload_never_blocks():
    assert rating_gate(None, "A") is None
    assert rating_gate({}, "A") is None
    assert rating_gate({"facts": {}}, "A") is None


def test_gate_unit_manual_only_without_fetched_facts():
    assert rating_gate({"facts": {"company": COMPANY}}, "A") is None


def test_gate_unit_effective_manual_over_empty_fetched_rating():
    assert rating_gate(fetch_payload(unrated_result()), "A") is None


def test_gate_unit_fetched_investment_grade_without_manual():
    assert rating_gate(fetch_payload(rated_result("BBB-"))) is None


def test_gate_unit_both_empty_refuses():
    assert rating_gate(fetch_payload(unrated_result()), "") == RATING_GATE_MESSAGE


def test_gate_unit_fetched_below_grade_still_refuses():
    assert rating_gate(fetch_payload(rated_result("BB+")), "AA") == RATING_GATE_MESSAGE


def test_a_manual_only_no_fetch_adds(db_path):
    client = make_client(db_path)
    response = client.post("/watch", data=post_data())
    assert response.status_code == 302
    assert stored_row(db_path)["rating"] == "A"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_b_fetched_without_rating_manual_choice_is_stored(db_path):
    client = make_client(db_path, service_with(db_path, unrated_result()))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    response = client.post("/watch", data=post_data(rating="A"))
    assert response.status_code == 302
    assert stored_row(db_path)["rating"] == "A"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_c_fetched_rating_without_manual_choice_is_stored(db_path):
    client = make_client(db_path, service_with(db_path, rated_result("BBB-")))
    page = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert '<option value="BBB-" selected>BBB-</option>' in page
    response = client.post("/watch", data=post_data(rating="BBB-"))
    assert response.status_code == 302
    assert stored_row(db_path)["rating"] == "BBB-"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_d_neither_source_has_rating_is_refused(db_path):
    client = make_client(db_path, service_with(db_path, unrated_result()))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    response = client.post("/watch", data=post_data(rating=None))
    assert response.status_code == 400
    assert error_banner(response.get_data(as_text=True)) == RATING_GATE_MESSAGE
    assert stored_row(db_path) is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_empty_db_add_creates_one_row(db_path):
    client = make_client(db_path, service_with(db_path, unrated_result()))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    assert client.post("/watch", data=post_data(rating="A")).status_code == 302
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"] == 1


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_persisted_isin_readd_still_duplicate(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, COMPANY, ISIN)
    client = make_client(db_path, service_with(db_path, unrated_result()))
    assert client.get(f"/watch?isin={ISIN}").status_code == 200
    response = client.post("/watch", data=post_data(rating="A"))
    assert response.status_code == 409
    assert "already exists as holding" in response.get_data(as_text=True)


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_charter3_step2_real_isin_add(db_path):
    client = make_client(db_path)
    page = client.get(f"/watch?isin={REAL_ISIN}")
    assert page.status_code == 200
    assert REAL_COMPANY in page.get_data(as_text=True)
    response = client.post(
        "/watch",
        data=post_data(
            rating="A",
            isin=REAL_ISIN,
            company=REAL_COMPANY,
            coupon_pct="8.5",
            maturity_date="2028-09-30",
        ),
    )
    assert response.status_code == 302
    row = stored_row(db_path, REAL_ISIN)
    assert row["company"] == REAL_COMPANY
    assert row["rating"] == "A"
    assert row["maturity_date"] == "2028-09-30"
