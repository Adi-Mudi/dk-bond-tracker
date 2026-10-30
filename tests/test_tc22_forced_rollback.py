import pytest

from src.db import get_conn, init_db
from src.import_xlsm import commit_import
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


def test_forced_mid_commit_failure_leaves_ledger_unchanged(tmp_path):
    db_path = tmp_path / "tc22.db"
    init_db(db_path)
    bonds = [
        make_bond(2, "INETC22DUPE1"),
        make_bond(3, "INETC22DUPE1"),
    ]
    grid = [
        {"2025-09": 100.0, "2025-10": 100.0},
        {"2025-09": 200.0},
    ]
    with get_conn(db_path) as conn:
        baseline_bonds = conn.execute("SELECT COUNT(*) FROM bonds").fetchone()[0]
        baseline_ledger = conn.execute("SELECT COUNT(*) FROM payment_ledger").fetchone()[0]
    with pytest.raises(AppError) as exc_info:
        commit_import(db_path, bonds, grid)
    assert exc_info.value.code == "ERR-commit-import"
    with get_conn(db_path) as conn:
        bonds_now = conn.execute("SELECT COUNT(*) FROM bonds").fetchone()[0]
        ledger_now = conn.execute("SELECT COUNT(*) FROM payment_ledger").fetchone()[0]
    assert bonds_now == baseline_bonds
    assert ledger_now == baseline_ledger
    assert ledger_now == 0
