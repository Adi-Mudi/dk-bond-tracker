import pytest

from src.phase4 import tds_deduction
from src.validators import AppError


def assert_named_error(callable_obj, *args, **kwargs):
    with pytest.raises(AppError) as exc_info:
        callable_obj(*args, **kwargs)
    assert exc_info.value.code == "ERR-tds-compute"
    return exc_info.value


def test_tc11_non_numeric_payout_raises_named_error():
    error = assert_named_error(tds_deduction, "10000")
    assert "numeric" in error.message


def test_tc11_none_payout_raises_named_error():
    assert_named_error(tds_deduction, None)


def test_tc11_bool_payout_raises_named_error():
    assert_named_error(tds_deduction, True)


def test_tc11_negative_payout_raises_named_error():
    error = assert_named_error(tds_deduction, -100)
    assert "non-negative" in error.message


def test_tc11_rate_zero_raises_named_error():
    error = assert_named_error(tds_deduction, 10000, 0)
    assert "(0, 1]" in error.message


def test_tc11_negative_rate_raises_named_error():
    assert_named_error(tds_deduction, 10000, -5)


def test_tc11_rate_above_one_raises_named_error():
    assert_named_error(tds_deduction, 10000, 1.5)


def test_tc11_non_numeric_rate_raises_named_error():
    assert_named_error(tds_deduction, 10000, "10%")


def test_tc11_no_silent_zero_on_any_invalid_input():
    cases = [("10000", 0.10), (10000, 0), (10000, -5), (None, 0.10), (-1, 0.10)]
    for payout, rate in cases:
        try:
            result = tds_deduction(payout, rate)
        except AppError as exc:
            assert exc.code == "ERR-tds-compute"
            continue
        raise AssertionError(f"invalid input returned silently: {result!r}")
