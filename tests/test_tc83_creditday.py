import sqlite3
from datetime import date

import pytest

from src.db import get_conn, init_db
from src.validators import AppError, date_range_tenure, legacy_position, validate_credit_day


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



