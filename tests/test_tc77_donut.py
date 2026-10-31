from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.db import get_conn
from src.queries import chart_data, summary_counts
from src.validators import add_months


def seed_donut_portfolio(conn, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    for index in range(2):
        add_bond(conn, f"Danger{index}", f"INE000000077{index}D", add_months(base, -4).isoformat(), 12, amount=10000.0)
    for index in range(2):
        add_bond(conn, f"Ongoing{index}", f"INE000000077{index}O", base.isoformat(), 6, amount=20000.0)
    completed_id = add_bond(conn, "Completed0", "INE0000000770C", add_months(base, -4).isoformat(), 2, amount=30000.0)
    completed_months = [add_months(base, -4), add_months(base, -3)]
    for offset, month_start in enumerate(completed_months):
        add_payment(conn, completed_id, f"{month_start.year:04d}-{month_start.month:02d}", 1000.0 + offset)
    flip_id = add_bond(conn, "Flippable", "INE0000000771F", add_months(base, -3).isoformat(), 12, amount=40000.0)
    flip_months = [add_months(base, -3), add_months(base, -2), add_months(base, -1)]
    for month_start in flip_months:
        add_payment(conn, flip_id, f"{month_start.year:04d}-{month_start.month:02d}", 1500.0)
    return flip_id, f"{add_months(base, -1).year:04d}-{add_months(base, -1).month:02d}", current


def test_tc77_donut_counts_equal_summary_counts(db_path):
    today = date(2026, 10, 3)
    with get_conn(db_path) as conn:
        seed_donut_portfolio(conn, today)
        data = chart_data(conn, today)
        counts = summary_counts(conn, today)
    assert data["donut"] == counts
    assert counts == {"danger": 2, "ongoing": 3, "completed": 1, "total": 6}


def test_tc77_donut_recomputes_after_flip(db_path):
    today = date(2026, 10, 3)
    with get_conn(db_path) as conn:
        flip_id, void_month, _ = seed_donut_portfolio(conn, today)
        before = chart_data(conn, today)["donut"]
        assert before == {"danger": 2, "ongoing": 3, "completed": 1, "total": 6}
        conn.execute(
            "UPDATE payment_ledger SET amount = 0, paid = 0 WHERE bond_id = ? AND month = ?",
            (flip_id, void_month),
        )
        after = chart_data(conn, today)["donut"]
    assert after == {"danger": 3, "ongoing": 2, "completed": 1, "total": 6}


def test_tc77_empty_portfolio_donut_zeros(db_path):
    today = date(2026, 10, 3)
    with get_conn(db_path) as conn:
        data = chart_data(conn, today)
    assert data["donut"] == {"danger": 0, "ongoing": 0, "completed": 0, "total": 0}
