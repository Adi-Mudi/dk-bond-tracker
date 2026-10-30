from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn
from src.import_xlsm import import_workbook

WORKBOOK = Path(
    "/mnt/Just_Do_It/02_Devp_Soft/01_Adi-Mudi/04_Bonds/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("tc71") / "import_real.db"
    summary = import_workbook(WORKBOOK, db_path)
    return summary, db_path


def test_real_workbook_present():
    assert WORKBOOK.is_file()


def test_legacy_irregular_rows_import_as_goals(imported):
    summary, db_path = imported
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT name, target_amount, target_end_date, note FROM financial_goals"
        ).fetchall()
    amounts = [row["target_amount"] for row in rows]
    assert 39588.0 in amounts
    assert 10063.0 in amounts
    assert 0.0 in amounts
    for row in rows:
        assert "legacy" in str(row["note"]).lower()
        assert row["target_end_date"] is None


def test_legacy_rows_are_goals_not_bonds(imported):
    summary, db_path = imported
    assert summary["bonds"] == 15
    with get_conn(db_path) as conn:
        bond_count = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
        bond_amounts = {
            row[0] for row in conn.execute("SELECT amount FROM bonds").fetchall()
        }
        isins = {
            str(row[0]).strip()
            for row in conn.execute("SELECT isin FROM bonds").fetchall()
        }
    assert bond_count == 15
    assert 0.0 not in bond_amounts
    assert all(isin.startswith("INE") for isin in isins)


def test_goals_page_renders_imported_legacy_rows(imported):
    summary, db_path = imported
    app = create_app(db_path)
    app.config["TESTING"] = True
    body = app.test_client().get("/goals").data.decode()
    assert "legacy schedule" in body
    assert "39588.00" in body
    assert "10063.00" in body
    assert "0.00" in body
    assert "ERR-unexpected" not in body
