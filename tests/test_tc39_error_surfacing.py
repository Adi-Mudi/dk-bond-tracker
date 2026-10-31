from datetime import date

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.queries import monthly_history, this_month_returns
from src.validators import AppError, add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_tc39_no_bonds_active_this_month_message(client, db_path):
    today = date.today()
    past_start = add_months(today.replace(day=1), -24)
    with get_conn(db_path) as conn:
        add_bond(conn, "EndedCo", "INE0000000391", past_start.isoformat(), 3, amount=10000.0)
    response = client.get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="summary-cards"' in html
    assert "Total Invested" in html
    assert "EndedCo" in html
    assert 'data-amount="10000.00"' in html


def test_tc39_current_month_outside_tenure_windows_not_blank(client, db_path):
    today = date.today()
    past_start = add_months(today.replace(day=1), -36)
    with get_conn(db_path) as conn:
        add_bond(conn, "OldCo", "INE0000000392", past_start.isoformat(), 2, amount=5000.0)
    html = client.get("/").get_data(as_text=True)
    assert "Total Invested" in html
    assert 'id="outstanding-total"' in html
    assert "OldCo" in html
    assert "this-month-total" not in html


def test_tc39_genuine_zero_when_active_bond_has_no_payment(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    with get_conn(db_path) as conn:
        add_bond(conn, "FreshCo", "INE0000000393", base.isoformat(), 6, amount=20000.0)
    html = client.get("/").get_data(as_text=True)
    assert "no holdings yet" not in html
    assert 'id="received-total" data-amount="0.00"' in html


def test_tc39_unresolvable_current_month_explicit_message(db_path, monkeypatch):
    class BrokenDate:
        @classmethod
        def today(cls):
            raise RuntimeError("system clock unreadable")

    monkeypatch.setattr("src.queries.date", BrokenDate)
    with get_conn(db_path) as conn:
        result = this_month_returns(conn)
    assert result["total"] is None
    assert result["message"] == "current month could not be resolved"


def test_tc39_unresolvable_month_history_named_error(db_path, monkeypatch):
    class BrokenDate:
        @classmethod
        def today(cls):
            raise RuntimeError("system clock unreadable")

    monkeypatch.setattr("src.queries.date", BrokenDate)
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as excinfo:
            monthly_history(conn)
    assert excinfo.value.code == "ERR-query-history"


def test_tc39_bond_with_no_ledger_rows_still_listed(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    with get_conn(db_path) as conn:
        add_bond(conn, "NoLedgerCo", "INE0000000394", base.isoformat(), 12, amount=30000.0)
    html = client.get("/").get_data(as_text=True)
    assert "NoLedgerCo" in html
    assert "no bonds active this month" not in html
