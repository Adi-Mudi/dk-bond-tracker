from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.queries import portfolio_totals, summary_amounts, this_month_returns
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_amounts(conn, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    prev = add_months(base, -1)
    prev_key = f"{prev.year:04d}-{prev.month:02d}"
    bond_a = add_bond(conn, "Alpha", "INE0000000421", add_months(base, -3).isoformat(), 6, amount=100000.0, maturity=12000.0)
    bond_b = add_bond(conn, "Beta", "INE0000000422", base.isoformat(), 6, amount=50000.0, maturity=6000.0)
    add_payment(conn, bond_a, prev_key, 1200.0)
    add_payment(conn, bond_a, current, 800.0)
    add_payment(conn, bond_b, current, 2500.0)
    unpaid_month = add_months(base, -2)
    conn.execute(
        "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, 0)",
        (bond_a, f"{unpaid_month.year:04d}-{unpaid_month.month:02d}", 999.0),
    )
    return bond_a, bond_b, current


def test_tc42_summary_amounts_exact_sums(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        seed_amounts(conn, today)
        amounts = summary_amounts(conn, today)
    assert amounts["total_investment"] == 150000.0
    assert amounts["till_return"] == 4500.0
    assert amounts["balance"] == 4500.0 - 18000.0
    assert amounts["month"] == "2026-10"
    assert amounts["month_message"] is None


def test_tc42_amounts_equal_portfolio_totals(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        seed_amounts(conn, today)
        totals = portfolio_totals(conn)
        amounts = summary_amounts(conn, today)
    assert amounts["total_investment"] == totals["total_investment"]
    assert amounts["till_return"] == totals["till_return"]
    assert amounts["balance"] == totals["balance"]


def test_tc42_unpaid_and_zero_rows_excluded_from_till_return(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        bond_id, _, current = seed_amounts(conn, today)
        add_payment(conn, bond_id, "2026-06", 0.0, paid=1)
        amounts = summary_amounts(conn, today)
    assert amounts["till_return"] == 4500.0


def test_tc42_this_month_returns_exact_sum(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        seed_amounts(conn, today)
        result = this_month_returns(conn, today)
    assert result == {"month": "2026-10", "total": 3300.0, "message": None}


def test_tc42_dashboard_page_amounts_match_queries(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_amounts(conn, today)
        amounts = summary_amounts(conn, today)
    html = client.get("/").get_data(as_text=True)
    assert "{:.2f}".format(amounts["total_investment"]) in html
    assert "{:.2f}".format(amounts["till_return"]) in html
    assert "{:.2f}".format(amounts["balance"]) in html
