import sqlite3
from datetime import date

import pytest

from src.db import get_conn, init_db
from src.import_xlsm import commit_import
from src.validators import AppError, date_range_tenure, legacy_position, validate_credit_day


def make_bond(row, isin, start_month, tenure):
    return {
        "row": row,
        "company": f"Company {row}",
        "isin": isin,
        "status": "On-going",
        "tenure_months": tenure,
        "start_month": start_month,
        "investment": 1000.0,
        "maturity": 1200.0,
    }


@pytest.mark.parametrize("credit_day", [1, 28])
def test_credit_day_accepted_within_1_to_28(credit_day):
    assert validate_credit_day(credit_day) == credit_day


@pytest.mark.parametrize("credit_day", [0, 29, 30, 31, -1])
def test_credit_day_outside_1_to_28_rejected(credit_day):
    with pytest.raises(AppError) as exc_info:
        validate_credit_day(credit_day)
    assert exc_info.value.code == "ERR-date-range"


@pytest.mark.parametrize("credit_day", ["abc", 2.5, None, True])
def test_credit_day_non_integer_rejected(credit_day):
    with pytest.raises(AppError) as exc_info:
        validate_credit_day(credit_day)
    assert exc_info.value.code == "ERR-date-range"


def test_date_range_tenure_returns_validated_tuple():
    result = date_range_tenure(date(2025, 9, 3), date(2026, 12, 2), 5)
    assert result == (date(2025, 9, 3), date(2026, 12, 2), 15, 5)


def test_schema_check_rejects_credit_day_zero_and_29(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        for position, bad_day in enumerate((0, 29)):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
                    "tenure_months, credit_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        f"C{bad_day}",
                        f"INE0000000{position}{bad_day}",
                        "n",
                        1.0,
                        "2025-09-01",
                        "2026-12-01",
                        15,
                        bad_day,
                    ),
                )


def test_legacy_start_month_maps_to_first_day_of_month():
    start, end, tenure, credit_day = legacy_position("2025-09", 15)
    assert start == date(2025, 9, 1)
    assert end == date(2026, 12, 1)
    assert tenure == 15
    assert credit_day == 1


def test_legacy_start_day_31_clamps_credit_day_to_28():
    start, end, tenure, credit_day = legacy_position(date(2025, 1, 31), 15)
    assert start == date(2025, 1, 31)
    assert end == date(2026, 4, 30)
    assert tenure == 15
    assert credit_day == 28


def test_legacy_import_stores_dates_and_default_credit_day(tmp_path):
    db_path = tmp_path / "bonds.db"
    bond = make_bond(2, "INE000000001", "2025-09", 15)
    grid = [{"2025-10": 500.0, "2025-11": 0, "2025-12": None}]
    commit_import(db_path, [bond], grid)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT start_date, end_date, tenure_months, credit_day FROM bonds"
        ).fetchone()
        ledger = conn.execute(
            "SELECT month, amount, paid FROM payment_ledger ORDER BY id"
        ).fetchall()
    assert row["start_date"] == "2025-09-01"
    assert row["end_date"] == "2026-12-01"
    assert row["tenure_months"] == 15
    assert row["credit_day"] == 1
    assert len(ledger) == 1
    assert ledger[0]["month"] == "2025-10"
    assert ledger[0]["amount"] == 500.0
    assert ledger[0]["paid"] == 1


def test_legacy_import_start_day_31_stores_clamped_credit_day(tmp_path):
    db_path = tmp_path / "bonds.db"
    bond = make_bond(2, "INE000000002", date(2025, 1, 31), 15)
    commit_import(db_path, [bond], [{}])
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT start_date, end_date, credit_day FROM bonds").fetchone()
    assert row["start_date"] == "2025-01-31"
    assert row["end_date"] == "2026-04-30"
    assert row["credit_day"] == 28
