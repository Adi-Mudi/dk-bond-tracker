import pytest

from src.validators import AppError, find_duplicate_isins, validate_extracted


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


def test_duplicate_isin_row_2_and_row_40_of_40_bond_set():
    bonds = [make_bond(row, f"INE{row:07d}00") for row in range(2, 42)]
    bonds[0] = make_bond(2, "INE000000042")
    bonds[40 - 2] = make_bond(40, "INE000000042")
    duplicates = find_duplicate_isins(bonds)
    assert len(duplicates) == 1
    assert duplicates[0]["isin"] == "INE000000042"
    assert duplicates[0]["occurrences"] == [2, 40]
    with pytest.raises(AppError) as exc_info:
        validate_extracted(bonds, [{} for _ in bonds])
    assert exc_info.value.code == "ERR-04"
    assert "INE000000042" in exc_info.value.message
    assert "rows 2, 40" in exc_info.value.message


def test_every_occurrence_flagged_when_isin_repeats_three_times():
    bonds = [
        make_bond(row, "INE000000077" if row in (2, 40, 41) else f"INE{row:07d}00")
        for row in range(2, 42)
    ]
    duplicates = find_duplicate_isins(bonds)
    assert len(duplicates) == 1
    assert duplicates[0]["occurrences"] == [2, 40, 41]
    with pytest.raises(AppError) as exc_info:
        validate_extracted(bonds, [{} for _ in bonds])
    assert exc_info.value.code == "ERR-04"
    assert "rows 2, 40, 41" in exc_info.value.message


def test_missing_required_field_names_field_and_row():
    bond = make_bond(2, "INE000000001")
    bond["tenure_months"] = None
    with pytest.raises(AppError) as exc_info:
        validate_extracted([bond], [{}])
    assert exc_info.value.code == "ERR-05"
    assert "row 2" in exc_info.value.message
    assert "tenure_months" in exc_info.value.message


def test_grid_row_count_mismatch_with_bond_count():
    bonds = [make_bond(2, "INE000000001"), make_bond(3, "INE000000002")]
    with pytest.raises(AppError) as exc_info:
        validate_extracted(bonds, [{}])
    assert exc_info.value.code == "ERR-05"
    assert "grid rows 1" in exc_info.value.message
    assert "bond rows 2" in exc_info.value.message
