import pytest

from conftest import add_bond, bond_count
from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


BLOCKED_FORM = {
    "company": "  MUTHOOTTU  ",
    "isin": "INE0000NEW99",
    "amount": "50000",
    "start_date": "2026-11-01",
    "end_date": "2027-11-01",
    "credit_day": "5",
}
BLOCKED_MESSAGE = "Cannot add position: Muthoottu has an active position (On-going) — no override"


def seed_active_muthoottu(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Muthoottu", "IN1234567890", "2025-01-01", 12, status="On-going")


def current_bond_count(db_path):
    with get_conn(db_path) as conn:
        return bond_count(conn)


def test_tc67_blocked_add_returns_409_with_exact_banner(client, db_path):
    seed_active_muthoottu(db_path)
    response = client.post("/add", data=BLOCKED_FORM)
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert f'<div id="lock-message">{BLOCKED_MESSAGE}</div>' in html
    assert "operation: ERR-active-position" in html


def test_tc67_blocked_add_inserts_no_row(client, db_path):
    seed_active_muthoottu(db_path)
    assert current_bond_count(db_path) == 1
    client.post("/add", data=BLOCKED_FORM)
    assert current_bond_count(db_path) == 1


def test_tc67_all_surfaces_show_no_trace_of_blocked_duplicate(client, db_path):
    seed_active_muthoottu(db_path)
    grid_before = client.get("/grid").get_data(as_text=True)
    dashboard_before = client.get("/").get_data(as_text=True)
    watch_before = client.get("/watch").get_data(as_text=True)
    response = client.post("/add", data=BLOCKED_FORM)
    assert response.status_code == 409
    grid_after = client.get("/grid").get_data(as_text=True)
    dashboard_after = client.get("/").get_data(as_text=True)
    watch_after = client.get("/watch").get_data(as_text=True)
    assert grid_after == grid_before
    assert dashboard_after == dashboard_before
    assert watch_after == watch_before
    for page in (grid_after, dashboard_after, watch_after):
        assert "MUTHOOTTU" not in page
        assert "INE0000NEW99" not in page
        assert page.count("Muthoottu") == 1
    assert current_bond_count(db_path) == 1


def test_tc67_isin_key_blocks_too(client, db_path):
    seed_active_muthoottu(db_path)
    form = dict(BLOCKED_FORM, company="Some Other Company", isin="IN1234567890")
    response = client.post("/add", data=form)
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert BLOCKED_MESSAGE in html
    assert current_bond_count(db_path) == 1
