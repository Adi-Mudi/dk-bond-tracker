import pytest

from conftest import add_bond, bond_count
from src.app import create_app
from src.db import get_conn

BLOCKED_MESSAGE = "Cannot add position: Beta Finance Ltd has an active position (On-going) — no override"


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_active_muthoottu(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="On-going")


def base_form():
    return {
        "company": "MUTHOOTTU",
        "isin": "INE0000NEW66",
        "amount": "50000",
        "start_date": "2026-11-01",
        "end_date": "2027-11-01",
        "credit_day": "5",
    }


def current_bond_count(db_path):
    with get_conn(db_path) as conn:
        return bond_count(conn)


def assert_blocked(client, db_path, response, expected_count=1):
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert BLOCKED_MESSAGE in html
    assert "operation: ERR-active-position" in html
    assert current_bond_count(db_path) == expected_count


def test_tc66_force_query_param_grants_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    response = client.post("/add?force=1", data=base_form())
    assert_blocked(client, db_path, response)


def test_tc66_override_query_param_grants_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    response = client.post("/add?override=yes", data=base_form())
    assert_blocked(client, db_path, response)


def test_tc66_bypass_query_param_grants_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    response = client.post("/add?bypass=1", data=base_form())
    assert_blocked(client, db_path, response)


def test_tc66_force_form_field_grants_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    form = dict(base_form(), force="1")
    response = client.post("/add", data=form)
    assert_blocked(client, db_path, response)


def test_tc66_override_form_field_grants_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    form = dict(base_form(), override="yes")
    response = client.post("/add", data=form)
    assert_blocked(client, db_path, response)


def test_tc66_bypass_form_field_grants_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    form = dict(base_form(), bypass="1")
    response = client.post("/add", data=form)
    assert_blocked(client, db_path, response)


def test_tc66_all_override_params_together_grant_no_override(client, db_path):
    seed_active_muthoottu(db_path)
    form = dict(base_form(), force="1", override="yes", bypass="1")
    response = client.post("/add?force=1&override=yes&bypass=1", data=form)
    assert_blocked(client, db_path, response)
    html = response.get_data(as_text=True)
    assert BLOCKED_MESSAGE in html
