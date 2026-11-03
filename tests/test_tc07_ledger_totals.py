import pytest

from conftest import add_bond
from src.db import get_conn, init_db
from src.queries import bond_month_totals, portfolio_totals, save_payment
from src.validators import AppError


def test_tc07_bond_totals_k_and_l(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000007", "2025-01-01", 3, maturity=120000.0)
        save_payment(conn, bond_id, "2025-01", 10000.0, 1)
        save_payment(conn, bond_id, "2025-02", 10000.0, 1)
        save_payment(conn, bond_id, "2025-03", 10000.0, 1)
        totals = bond_month_totals(conn, bond_id)
        assert totals["k"] == 30000.0
        assert totals["l"] == -90000.0
        portfolio = portfolio_totals(conn)
        assert portfolio["till_return"] == 30000.0
        assert portfolio["balance"] == -90000.0


def test_tc07_insert_creates_exactly_one_row(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000071", "2025-09-01", 12)
        result = save_payment(conn, bond_id, "2025-09", 10000.0, 1)
        assert result["action"] == "inserted"
        rows = conn.execute(
            "SELECT bond_id, month, amount, paid FROM payment_ledger WHERE bond_id = ?",
            (bond_id,),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["bond_id"] == bond_id
        assert rows[0]["month"] == "2025-09"
        assert rows[0]["amount"] == 10000.0
        assert rows[0]["paid"] == 1


def test_tc07_correction_updates_the_single_row(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000072", "2025-09-01", 12)
        save_payment(conn, bond_id, "2025-09", 0.0, 0)
        result = save_payment(conn, bond_id, "2025-09", 5000.0, 1)
        assert result["action"] == "corrected"
        rows = conn.execute(
            "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, "2025-09"),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["amount"] == 5000.0
        assert rows[0]["paid"] == 1


def test_tc07_void_keeps_row_and_drops_from_totals(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000073", "2025-01-01", 3, maturity=25000.0)
        save_payment(conn, bond_id, "2025-01", 10000.0, 1)
        save_payment(conn, bond_id, "2025-02", 15000.0, 1)
        result = save_payment(conn, bond_id, "2025-01", 0, 0)
        assert result["paid"] == 0
        rows = conn.execute(
            "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, "2025-01"),
        ).fetchall()
        assert len(rows) == 1
        assert rows[0]["paid"] == 0
        assert rows[0]["amount"] == 0
        totals = bond_month_totals(conn, bond_id)
        assert totals["k"] == 15000.0
        assert totals["l"] == -10000.0


def test_tc07_save_validation_errors(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000075", "2025-01-01", 3)
        with pytest.raises(AppError) as exc_info:
            save_payment(conn, bond_id, "2025-01", -1, 1)
        assert exc_info.value.code == "ERR-ledger-insert"
        with pytest.raises(AppError):
            save_payment(conn, bond_id, "2025-13", 100.0, 1)
        with pytest.raises(AppError):
            save_payment(conn, bond_id, "not-a-month", 100.0, 1)
        with pytest.raises(AppError):
            save_payment(conn, 9999, "2025-01", 100.0, 1)


def test_tc07_empty_portfolio_returns_genuine_zeros(tmp_path):
    db_path = tmp_path / "empty.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        assert portfolio_totals(conn) == {
            "total_investment": 0.0,
            "till_return": 0.0,
            "balance": 0.0,
        }
        assert bond_month_totals.__name__ == "bond_month_totals"


def test_tc07_totals_are_query_derived_not_stored(db_path):
    with get_conn(db_path) as conn:
        ledger_columns = [
            row[1] for row in conn.execute("PRAGMA table_info(payment_ledger)").fetchall()
        ]
        assert ledger_columns == ["id", "bond_id", "month", "amount", "paid"]
        bond_columns = [
            row[1].lower()
            for row in conn.execute("PRAGMA table_info(bonds)").fetchall()
        ]
        assert not any("till" in column or "balance" in column for column in bond_columns)
