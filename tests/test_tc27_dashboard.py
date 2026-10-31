from datetime import date

import pytest

from conftest import add_bond, add_payment, pay_range
from src.app import create_app
from src.db import get_conn
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def first_of_month(day):
    return day.replace(day=1)


def seed_dashboard_portfolio(conn, today):
    base = first_of_month(today)
    danger_start = add_months(base, -2)
    completed_start = add_months(base, -2)
    add_bond(conn, "DangerCo", "INE0000000271", danger_start.isoformat(), 6)
    ongoing_id = add_bond(conn, "OngoingCo", "INE0000000272", base.isoformat(), 6)
    add_payment(conn, ongoing_id, f"{base.year:04d}-{base.month:02d}", 500.0)
    completed_id = add_bond(conn, "DoneCo", "INE0000000273", completed_start.isoformat(), 1)
    pay_range(conn, completed_id, f"{completed_start.year:04d}-{completed_start.month:02d}", 1)
    return completed_id


def test_tc27_get_dashboard_returns_200(client, db_path):
    with get_conn(db_path) as conn:
        seed_dashboard_portfolio(conn, date.today())
    response = client.get("/")
    assert response.status_code == 200


def test_tc27_dashboard_markers_present(client, db_path):
    with get_conn(db_path) as conn:
        seed_dashboard_portfolio(conn, date.today())
    html = client.get("/").get_data(as_text=True)
    for marker in (
        'id="summary-cards"',
        'id="card-total"',
        'id="card-received"',
        'id="card-next-payout"',
        'id="total-invested"',
        'id="received-total"',
        'id="next-payout-amount"',
        'id="outstanding-total"',
        'id="invested-received-chart"',
    ):
        assert marker in html, marker


def test_tc27_seeded_bonds_render_live_amounts(client, db_path):
    with get_conn(db_path) as conn:
        seed_dashboard_portfolio(conn, date.today())
    html = client.get("/").get_data(as_text=True)
    assert 'data-amount="300000.00"' in html
    assert 'data-amount="1500.00"' in html
    for company in ("DangerCo", "OngoingCo", "DoneCo"):
        assert company in html


def test_tc27_new_payment_reflected_on_next_request(client, db_path):
    today = date.today()
    base = first_of_month(today)
    month = f"{base.year:04d}-{base.month:02d}"
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "LiveCo", "INE0000000274", base.isoformat(), 6)
    first = client.get("/").get_data(as_text=True)
    assert 'id="received-total" data-amount="0.00"' in first
    with get_conn(db_path) as conn:
        add_payment(conn, bond_id, month, 500.0)
    second = client.get("/").get_data(as_text=True)
    assert 'id="received-total" data-amount="500.00"' in second


def test_tc27_two_no_change_requests_identical(client, db_path):
    with get_conn(db_path) as conn:
        seed_dashboard_portfolio(conn, date.today())
    first = client.get("/").get_data(as_text=True)
    second = client.get("/").get_data(as_text=True)
    assert first == second
