import pytest

from conftest import add_ongoing_seed, bond_count
from src.app import create_app
from src.db import get_conn

COMPANY = "Beta Finance Ltd"
CANDIDATE_ISIN = "INE0000NEW66"
HOLDING_ISIN = "IN1234567890"
BLOCKED_MESSAGE = "Cannot add position: Beta Finance Ltd has an active position (On-going) — no override"
MOVE_DATA = {
    "start_date": "2026-11-01",
    "end_date": "2027-11-01",
    "credit_day": "5",
    "qty": "100",
    "amount": "100000",
    "broker": "ICICI Direct",
}


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_candidate_then_conflicting_holding(client, db_path, company=COMPANY, isin=CANDIDATE_ISIN):
    response = client.post(
        "/watch",
        data={
            "company": company,
            "isin": isin,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, COMPANY, HOLDING_ISIN)
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (isin.upper(),)
        ).fetchone()["id"]


def current_bond_count(db_path):
    with get_conn(db_path) as conn:
        return bond_count(conn)


def assert_blocked(db_path, response):
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert BLOCKED_MESSAGE in html
    assert "Error: ERR-active-position" in html
    assert current_bond_count(db_path) == 2


def test_tc66_force_query_param_grants_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(f"/watch/{candidate_id}/move?force=1", data=MOVE_DATA)
    assert_blocked(db_path, response)


def test_tc66_override_query_param_grants_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(f"/watch/{candidate_id}/move?override=yes", data=MOVE_DATA)
    assert_blocked(db_path, response)


def test_tc66_bypass_query_param_grants_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(f"/watch/{candidate_id}/move?bypass=1", data=MOVE_DATA)
    assert_blocked(db_path, response)


def test_tc66_force_form_field_grants_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(f"/watch/{candidate_id}/move", data=dict(MOVE_DATA, force="1"))
    assert_blocked(db_path, response)


def test_tc66_override_form_field_grants_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(f"/watch/{candidate_id}/move", data=dict(MOVE_DATA, override="yes"))
    assert_blocked(db_path, response)


def test_tc66_bypass_form_field_grants_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(f"/watch/{candidate_id}/move", data=dict(MOVE_DATA, bypass="1"))
    assert_blocked(db_path, response)


def test_tc66_all_override_params_together_grant_no_override(client, db_path):
    candidate_id = seed_candidate_then_conflicting_holding(client, db_path)
    response = client.post(
        f"/watch/{candidate_id}/move?force=1&override=yes&bypass=1",
        data=dict(MOVE_DATA, force="1", override="yes", bypass="1"),
    )
    assert_blocked(db_path, response)
