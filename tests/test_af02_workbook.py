from pathlib import Path

import pytest

from src.import_xlsm import locate_sheet, normalize_sheets, open_workbook
from src.validators import AppError

WORKBOOK = Path(
    "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)


@pytest.fixture
def opened():
    workbook = open_workbook(WORKBOOK)
    yield workbook
    workbook.values.close()
    workbook.formulas.close()


def test_real_workbook_exists():
    assert WORKBOOK.is_file()


def test_open_workbook_both_modes(opened):
    assert opened.values.sheetnames == opened.formulas.sheetnames
    assert opened.values.sheetnames


def test_five_sheets_found(opened):
    assert len(opened.values.sheetnames) == 5


def test_normalized_names_trimmed(opened):
    mapping = normalize_sheets(opened.values)
    assert set(mapping) == {"Note", "Bond - Watch list", "Monthly Returns", "Dashboard", "Home Plan"}
    assert mapping["Bond - Watch list"] == "Bond - Watch list "


def test_locate_monthly_returns(opened):
    assert locate_sheet(opened.values, "Monthly Returns") == "Monthly Returns"


def test_locate_sheet_tolerates_padding(opened):
    assert locate_sheet(opened.values, "  Monthly Returns  ") == "Monthly Returns"


def test_locate_missing_sheet_raises(opened):
    with pytest.raises(AppError) as exc_info:
        locate_sheet(opened.values, "No Such Sheet")
    assert exc_info.value.code == "SHEET_NOT_FOUND"


def test_open_missing_file_raises(tmp_path):
    with pytest.raises(AppError) as exc_info:
        open_workbook(tmp_path / "missing.xlsm")
    assert exc_info.value.code == "ERR-workbook-open"
