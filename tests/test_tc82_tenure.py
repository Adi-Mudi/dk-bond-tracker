from datetime import date, datetime

import pytest

from src.validators import AppError, tenure_from_range


def test_srs_example_2025_09_03_to_2026_12_02_is_fifteen_months():
    assert tenure_from_range(date(2025, 9, 3), date(2026, 12, 2)) == 15


def test_day_shy_2025_01_15_to_2025_02_14_counts_one_plain_month():
    assert tenure_from_range(date(2025, 1, 15), date(2025, 2, 14)) == 1


def test_day_shy_span_keeps_plain_year_times_12_plus_month_delta():
    start = date(2025, 9, 3)
    end = date(2026, 12, 2)
    assert tenure_from_range(start, end) == (end.year - start.year) * 12 + (end.month - start.month)


def test_day_shy_end_of_month_range_not_decremented():
    assert tenure_from_range(date(2025, 1, 31), date(2025, 2, 28)) == 1


def test_datetime_values_accepted():
    assert tenure_from_range(datetime(2025, 1, 15), datetime(2025, 2, 14)) == 1


def test_end_before_start_rejected():
    with pytest.raises(AppError) as exc_info:
        tenure_from_range(date(2026, 1, 10), date(2026, 1, 1))
    assert exc_info.value.code == "ERR-date-range"


def test_end_equal_to_start_rejected():
    with pytest.raises(AppError) as exc_info:
        tenure_from_range(date(2025, 9, 3), date(2025, 9, 3))
    assert exc_info.value.code == "ERR-date-range"


def test_unparseable_start_date_rejected():
    with pytest.raises(AppError) as exc_info:
        tenure_from_range("not-a-date", date(2025, 9, 3))
    assert exc_info.value.code == "ERR-date-range"
    assert "start_date" in exc_info.value.message


def test_unparseable_end_date_rejected():
    with pytest.raises(AppError) as exc_info:
        tenure_from_range(date(2025, 9, 3), None)
    assert exc_info.value.code == "ERR-date-range"
    assert "end_date" in exc_info.value.message
