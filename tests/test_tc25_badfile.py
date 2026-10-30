import pytest
from openpyxl import Workbook

from src.db import get_conn, init_db
from src.import_xlsm import commit_import, import_workbook
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


def test_missing_workbook_raises_named_open_error(tmp_path):
    db_path = tmp_path / "import.db"
    with pytest.raises(AppError) as exc_info:
        import_workbook(tmp_path / "missing.xlsm", db_path)
    assert exc_info.value.code == "ERR-workbook-open"
    assert "missing" in exc_info.value.message
    assert not db_path.exists()


def test_corrupt_workbook_bytes_raise_named_open_error(tmp_path):
    corrupt = tmp_path / "corrupt.xlsm"
    corrupt.write_bytes(b"this-is-not-a-zip-or-workbook\x00\x01\x02")
    db_path = tmp_path / "import.db"
    with pytest.raises(AppError) as exc_info:
        import_workbook(corrupt, db_path)
    assert exc_info.value.code == "ERR-workbook-open"
    assert exc_info.value.message
    assert not db_path.exists()


def test_workbook_missing_required_sheet_raises_named_error(tmp_path):
    source = tmp_path / "incomplete.xlsx"
    workbook = Workbook()
    workbook.active.title = "Other Sheet"
    workbook.save(source)
    db_path = tmp_path / "import.db"
    with pytest.raises(AppError) as exc_info:
        import_workbook(source, db_path)
    assert exc_info.value.code == "SHEET_NOT_FOUND"
    assert not db_path.exists()


def test_commit_constraint_violation_rolls_back_partial_import(tmp_path):
    db_path = tmp_path / "import.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Existing", "INEEXIST0001", "Existing", 1.0, "2025-09-01", "2026-12-01", 15, 1),
        )
    bonds = [make_bond(2, "INE000000009"), make_bond(3, "INEEXIST0001")]
    grid = [{"2025-09": 100.0}, {"2025-09": 200.0}]
    with pytest.raises(AppError) as exc_info:
        commit_import(db_path, bonds, grid)
    assert exc_info.value.code == "ERR-commit-import"
    with get_conn(db_path) as conn:
        isins = [row[0] for row in conn.execute("SELECT isin FROM bonds ORDER BY id")]
        ledger_rows = conn.execute("SELECT COUNT(*) FROM payment_ledger").fetchone()[0]
    assert isins == ["INEEXIST0001"]
    assert ledger_rows == 0
