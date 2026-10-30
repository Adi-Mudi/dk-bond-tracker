import pytest

from src.import_xlsm import find_duplicate_isins, validate_extracted
from src.validators import AppError


def make_bond(row, isin):
    return {
        "row": row,
        "company": f"Company {row}",
        "isin": isin,
        "status": "On-going",
        "tenure_months": 15,
        "start_month": "2025-09",
        "investment": 1000.0,
        "maturity": 1200.0,
    }


def test_case_and_whitespace_variants_grouped_as_one_duplicate():
    bonds = [make_bond(5, " IN1234567890 "), make_bond(9, "in1234567890")]
    duplicates = find_duplicate_isins(bonds)
    assert len(duplicates) == 1
    assert duplicates[0]["isin"] == "IN1234567890"
    assert duplicates[0]["occurrences"] == [5, 9]
    with pytest.raises(AppError) as exc_info:
        validate_extracted(bonds, [{}, {}])
    assert exc_info.value.code == "ERR-04"
    assert "IN1234567890" in exc_info.value.message
    assert "rows 5, 9" in exc_info.value.message


def test_empty_input_set_returns_empty_result():
    assert find_duplicate_isins([]) == []
    assert validate_extracted([], []) is None


def test_unavailable_input_set_raises_named_error():
    with pytest.raises(AppError) as exc_info:
        find_duplicate_isins(None)
    assert exc_info.value.code == "ERR-duplicate-check"
