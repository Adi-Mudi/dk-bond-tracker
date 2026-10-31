from datetime import date

import pytest

from conftest import add_bond, add_payment, pay_range
from src.app import create_app
from src.db import get_conn
from src.queries import HISTORY_MONTH_CAP, monthly_history
from src.status import month_key
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_tc81_history_last_element_is_current_month(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "HistCo", "INE0000000811", "2025-09-01", 24)
        pay_range(conn, bond_id, "2025-09", 4)
        history = monthly_history(conn, today)
    assert history[-1]["month"] == "2026-10"
    assert history[0]["month"] == "2025-09"


def test_tc81_future_ledger_rows_excluded(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "FutureCo", "INE0000000812", "2025-09-01", 24)
        add_payment(conn, bond_id, "2027-01", 999.0)
        add_payment(conn, bond_id, "2030-06", 888.0)
        add_payment(conn, bond_id, "2025-09", 1000.0)
        history = monthly_history(conn, today)
    months = [row["month"] for row in history]
    assert "2027-01" not in months
    assert "2030-06" not in months
    assert all(month <= "2026-10" for month in months)
    assert months[-1] == "2026-10"


def test_tc81_months_with_no_payments_listed_as_zero(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "ZeroCo", "INE0000000813", "2026-08-01", 6)
        add_payment(conn, bond_id, "2026-08", 100.0)
        history = monthly_history(conn, today)
    by_month = {row["month"]: row["total"] for row in history}
    assert by_month["2026-08"] == 100.0
    assert by_month["2026-09"] == 0.0
    assert by_month["2026-10"] == 0.0


def test_tc81_current_month_payment_auto_appends(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "AutoCo", "INE0000000814", "2026-09-01", 12)
        add_payment(conn, bond_id, "2026-09", 700.0)
        before = monthly_history(conn, today)
        assert before[-1] == {"month": "2026-10", "total": 0.0}
        add_payment(conn, bond_id, "2026-10", 750.0)
        after = monthly_history(conn, today)
    assert after[-1] == {"month": "2026-10", "total": 750.0}
    assert after[-2] == {"month": "2026-09", "total": 700.0}


def test_tc81_clock_advance_appends_new_current_month(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "ClockCo", "INE0000000815", "2026-09-01", 12)
        add_payment(conn, bond_id, "2026-09", 700.0)
        october = monthly_history(conn, date(2026, 10, 30))
        november = monthly_history(conn, date(2026, 11, 30))
    assert october[-1]["month"] == "2026-10"
    assert november[-1] == {"month": "2026-11", "total": 0.0}
    assert [row["month"] for row in november][-2:] == ["2026-10", "2026-11"]


def test_tc81_window_starts_at_earliest_of_ledger_and_bond(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "WindowCo", "INE0000000816", "2026-01-01", 24)
        add_payment(conn, bond_id, "2025-11", 100.0)
        history = monthly_history(conn, today)
    assert history[0]["month"] == "2025-11"


def test_tc81_window_capped_at_120_months(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        add_bond(conn, "AncientCo", "INE0000000817", "1990-01-01", 12)
        history = monthly_history(conn, today)
    assert len(history) == HISTORY_MONTH_CAP
    assert history[-1]["month"] == "2026-10"


def test_tc81_empty_portfolio_empty_history(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        history = monthly_history(conn, today)
    assert history == []


def test_tc81_payouts_window_current_and_no_future(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    start = add_months(base, -14)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "DashCo", "INE0000000818", start.isoformat(), 24)
        add_payment(conn, bond_id, month_key(start), 500.0)
    assert client.get("/").status_code == 200
    port = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    months = [part.split('"')[0] for part in port.split('data-month="')[1:]]
    current = f"{base.year:04d}-{base.month:02d}"
    assert months, "payouts grid must render month columns"
    assert current in months
    assert all(month <= current for month in months)
