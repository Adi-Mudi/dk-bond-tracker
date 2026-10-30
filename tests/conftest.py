import sys
from datetime import date
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import init_db
from src.validators import add_months


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "bonds.db"
    init_db(path)
    return path


def month_sequence(start_month, count):
    year, mon = map(int, start_month.split("-"))
    out = []
    for offset in range(count):
        month = mon + offset
        out.append(f"{year + (month - 1) // 12:04d}-{(month - 1) % 12 + 1:02d}")
    return out


def add_bond(
    conn,
    company,
    isin,
    start_date,
    tenure_months,
    credit_day=5,
    amount=100000.0,
    maturity=None,
    status="On-going",
):
    start = date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    end = add_months(start, tenure_months)
    if maturity is None:
        maturity = float(tenure_months) * 1000.0
    cursor = conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
        "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            company,
            isin,
            company,
            float(amount),
            float(maturity),
            start.isoformat(),
            end.isoformat(),
            tenure_months,
            credit_day,
            status,
        ),
    )
    return cursor.lastrowid


def add_payment(conn, bond_id, month, amount, paid=1):
    conn.execute(
        "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
        (bond_id, month, float(amount), paid),
    )


def pay_range(conn, bond_id, start_month, count, skip=(), amount=1000.0):
    paid = []
    for month in month_sequence(start_month, count):
        if month in skip:
            continue
        add_payment(conn, bond_id, month, amount)
        paid.append(month)
    return paid


def bond_status(conn, bond_id):
    row = conn.execute("SELECT status FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    return None if row is None else row["status"]


def bond_count(conn):
    return conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
