from pathlib import Path

import pytest

from src.import_xlsm import (
    BOND_SHEET_TITLE,
    WATCH_LIST_SHEET_TITLE,
    extract_bond_master,
    extract_watch_list,
    import_workbook,
    locate_sheet,
    open_workbook,
    validate_watch_vs_master,
)
from src.validators import AppError

pytestmark = pytest.mark.remote

WORKBOOK = Path(
    "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)

EXPECTED_ISINS = [
    "INE420C07130",
    "INE101Q07BS1",
    "INE342T07569",
    "INE0BUS07CE3",
    "INE07HK07866",
    "INE08XP07431",
    "INE109C07139",
    "INE926R07019",
    "INE04UP07162",
    "INE0NES07329",
    "INE572J07810",
    "INE104W07245",
    "INE01XO07066",
    "INE04Q907199",
    "INE0I5X07042",
]


@pytest.fixture(scope="module")
def workbook_data():
    workbook = open_workbook(WORKBOOK)
    try:
        watch_name = locate_sheet(workbook.values, WATCH_LIST_SHEET_TITLE)
        watch_rows = extract_watch_list(workbook.values[watch_name])
        values_name = locate_sheet(workbook.values, BOND_SHEET_TITLE)
        formulas_name = locate_sheet(workbook.formulas, BOND_SHEET_TITLE)
        bonds = extract_bond_master(
            workbook.values[values_name], workbook.formulas[formulas_name]
        )
    finally:
        workbook.values.close()
        workbook.formulas.close()
    return watch_rows, bonds


def test_real_workbook_present():
    assert WORKBOOK.is_file()


def test_watch_list_extracts_bond_rows_with_isins(workbook_data):
    watch_rows, _ = workbook_data
    assert len(watch_rows) >= 15
    isins = [str(row["isin"]).strip().upper() for row in watch_rows]
    assert set(isins) == set(EXPECTED_ISINS)
    for row in watch_rows:
        assert row["company"]
        assert row["isin"]


def test_watch_list_rows_carry_detail_columns(workbook_data):
    watch_rows, _ = workbook_data
    for row in watch_rows:
        assert "face_value" in row
        assert "investment" in row
        assert "tlp_amount" in row
        assert "discount_amount" in row


def test_validate_watch_vs_master_passes(workbook_data):
    watch_rows, bonds = workbook_data
    result = validate_watch_vs_master(watch_rows, bonds)
    assert result["matched"] == 15


def test_validate_mismatch_raises_err_watch_mismatch(workbook_data):
    watch_rows, bonds = workbook_data
    mismatched = [dict(row) for row in watch_rows]
    mismatched[0] = dict(mismatched[0], isin="INE0000MISMATCH")
    with pytest.raises(AppError) as exc_info:
        validate_watch_vs_master(mismatched, bonds)
    assert exc_info.value.code == "ERR-watch-mismatch"


def test_validate_extra_isin_raises_err_watch_mismatch(workbook_data):
    watch_rows, bonds = workbook_data
    extra = [dict(row) for row in watch_rows]
    extra.append(dict(extra[0], isin="INE0000EXTRA0"))
    with pytest.raises(AppError) as exc_info:
        validate_watch_vs_master(extra, bonds)
    assert exc_info.value.code == "ERR-watch-mismatch"


def test_import_real_workbook_runs_watch_validation(tmp_path):
    db_path = tmp_path / "af06.db"
    summary = import_workbook(WORKBOOK, db_path)
    assert summary["bonds"] == 15
    assert summary["goals"] >= 2
