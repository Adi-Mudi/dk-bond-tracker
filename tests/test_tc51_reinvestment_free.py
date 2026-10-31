from datetime import date

import pytest

from src.db import get_conn
from src.queries import free_up_report
from src.status import month_key


@pytest.fixture
def portfolio(tmp_path):
    from src.db import init_db

    db_path = tmp_path / "tc51.db"
    init_db(db_path)
    today = date.today()
    with get_conn(db_path) as conn:
        completed_id = _insert(
            conn, "Done Corp", "INE00000000D1", 50000.0, date(today.year - 2, 1, 5), 2
        )
        for offset in range(2):
            month = f"{today.year - 2:04d}-{'01' if offset == 0 else '02'}"
            conn.execute(
                "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, 1)",
                (completed_id, month, 1000.0),
            )
        danger_id = _insert(
            conn, "Miss Corp", "INE00000000M1", 20000.0, date(today.year - 1, 1, 5), 12
        )
        ongoing_id = _insert(
            conn, "Live Corp", "INE00000000L1", 30000.0, date(today.year, today.month, 1), 6
        )
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, 1)",
            (ongoing_id, month_key(today), 500.0),
        )
    return db_path, completed_id, danger_id, ongoing_id


def _insert(conn, company, isin, amount, start, tenure):
    from src.validators import add_months

    cursor = conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
        "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            company,
            isin,
            company,
            amount,
            amount,
            start.isoformat(),
            add_months(start, tenure).isoformat(),
            tenure,
            5,
            "On-going",
        ),
    )
    return cursor.lastrowid


def test_completed_bond_principal_is_freed(portfolio):
    db_path, completed_id, danger_id, ongoing_id = portfolio
    with get_conn(db_path) as conn:
        report = free_up_report(conn, date.today())
    assert report["per_bond"][completed_id]["freed"] is True
    assert report["per_bond"][completed_id]["freed_amount"] == 50000.0
    assert report["principal_freed_by_completed"] == 50000.0


def test_ongoing_and_danger_are_not_freed(portfolio):
    db_path, completed_id, danger_id, ongoing_id = portfolio
    with get_conn(db_path) as conn:
        report = free_up_report(conn, date.today())
    assert report["per_bond"][danger_id]["freed"] is False
    assert report["per_bond"][danger_id]["freed_amount"] is None
    assert report["per_bond"][ongoing_id]["freed"] is False
    assert report["per_bond"][ongoing_id]["freed_amount"] is None


def test_deduction_breakdown_excludes_completed(portfolio):
    db_path, completed_id, danger_id, ongoing_id = portfolio
    with get_conn(db_path) as conn:
        report = free_up_report(conn, date.today())
    assert report["deduction_breakdown"] == {"On-going": 30000.0, "Danger": 20000.0}
    assert report["active_locked"] == 50000.0
    assert "Completed" not in report["deduction_breakdown"]


def test_all_completed_full_principal_available(tmp_path):
    from src.db import init_db

    db_path = tmp_path / "tc51_all.db"
    init_db(db_path)
    today = date.today()
    with get_conn(db_path) as conn:
        bond_id = _insert(conn, "Only Done", "INE00000000O1", 75000.0, date(today.year - 2, 1, 5), 2)
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, 1)",
            (bond_id, f"{today.year - 2:04d}-01", 1000.0),
        )
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, 1)",
            (bond_id, f"{today.year - 2:04d}-02", 1000.0),
        )
        report = free_up_report(conn, date.today())
    assert report["principal_freed_by_completed"] == 75000.0
    assert report["active_locked"] == 0.0
    assert report["deduction_breakdown"] == {"On-going": 0.0, "Danger": 0.0}
