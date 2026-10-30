from pathlib import Path

import pytest
from openpyxl import Workbook

from src.db import get_conn
from src.import_xlsm import (
    HOME_PLAN_SHEET_TITLE,
    extract_home_plan,
    import_workbook,
    locate_sheet,
    open_workbook,
)

pytestmark = pytest.mark.remote

WORKBOOK = Path(
    "/mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)


@pytest.fixture(scope="module")
def home_rows():
    workbook = open_workbook(WORKBOOK)
    try:
        sheet_name = locate_sheet(workbook.values, HOME_PLAN_SHEET_TITLE)
        rows = extract_home_plan(workbook.values[sheet_name])
    finally:
        workbook.values.close()
        workbook.formulas.close()
    return rows


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("af05") / "import_real.db"
    summary = import_workbook(WORKBOOK, db_path)
    return summary, db_path


def test_real_workbook_present():
    assert WORKBOOK.is_file()


def test_home_plan_extract_preserves_legacy_amounts(home_rows):
    assert len(home_rows) >= 1
    amounts = [row["amount"] for row in home_rows]
    assert 39588.0 in amounts
    assert 10063.0 in amounts
    assert 0.0 in amounts


def test_home_plan_rows_carry_label_and_amount(home_rows):
    for row in home_rows:
        assert "label" in row
        assert isinstance(row["amount"], float)


def test_home_plan_irregular_values_in_original_positions(home_rows):
    month_rows = [row for row in home_rows if isinstance(row["label"], int)]
    by_label = {row["label"]: row["amount"] for row in month_rows}
    assert by_label[6] == 39588.0
    assert by_label[8] == 10063.0
    assert by_label[9] == 0.0


def test_empty_home_plan_sheet_returns_empty():
    workbook = Workbook()
    try:
        rows = extract_home_plan(workbook.active)
    finally:
        workbook.close()
    assert rows == []


def test_import_summary_carries_goals_count(imported):
    summary, _ = imported
    assert summary["goals"] >= 2


def test_financial_goals_contain_legacy_home_plan_rows(imported, home_rows):
    summary, db_path = imported
    assert summary["goals"] >= 2
    with get_conn(db_path) as conn:
        goal_rows = conn.execute(
            "SELECT name, target_amount, target_end_date, note FROM financial_goals ORDER BY id"
        ).fetchall()
    assert len(goal_rows) >= 2
    amounts = [row["target_amount"] for row in goal_rows]
    assert 39588.0 in amounts
    assert 10063.0 in amounts
    for row in goal_rows:
        assert row["note"] == "legacy home plan"
        assert row["target_end_date"] is None
        assert row["name"] is not None


def test_bonds_count_still_fifteen_after_import(imported):
    summary, db_path = imported
    assert summary["bonds"] == 15
    with get_conn(db_path) as conn:
        bond_rows = conn.execute("SELECT COUNT(*) FROM bonds").fetchone()[0]
        isin_rows = conn.execute("SELECT COUNT(DISTINCT isin) FROM bonds").fetchone()[0]
    assert bond_rows == 15
    assert isin_rows == 15


def test_total_summary_rows_excluded(home_rows, imported):
    labels = [str(row["label"]).strip().lower() for row in home_rows]
    assert not [label for label in labels if label in ("totall", "total", "grandtotal", "sum")]
    summary, db_path = imported
    with get_conn(db_path) as conn:
        names = [str(r[0]).strip().lower() for r in conn.execute("SELECT name FROM financial_goals")]
    assert not [name for name in names if name in ("totall", "total", "grandtotal", "sum")]
