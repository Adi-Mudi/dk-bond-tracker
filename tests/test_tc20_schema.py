import sqlite3

import pytest

from src.db import get_conn, init_db


def bonds_columns(db_path):
    with get_conn(db_path) as conn:
        return [row[1] for row in conn.execute("PRAGMA table_info(bonds)").fetchall()]


def test_bonds_has_wave2_columns(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    columns = bonds_columns(db_path)
    for expected in ("start_date", "end_date", "credit_day", "tenure_months"):
        assert expected in columns


def test_credit_day_check_rejects_zero_and_32(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        for bad_day in (0, 32):
            with pytest.raises(sqlite3.IntegrityError):
                conn.execute(
                    "INSERT INTO bonds "
                    "(company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    ("Acme", f"INE00000{bad_day:04d}", "n", 1.0, "2025-09-03", "2026-12-02", 15, bad_day),
                )


def test_credit_day_accepts_1_and_31(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        for good_day in (1, 31):
            conn.execute(
                "INSERT INTO bonds "
                "(company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("Acme", f"INE00000{good_day:04d}", "n", 1.0, "2025-09-03", "2026-12-02", 15, good_day),
            )


def test_isin_unique(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Acme", "INE0000000001", "n1", 1.0, "2025-09-03", "2026-12-02", 15, 5),
        )
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                ("Acme Two", "INE0000000001", "n2", 1.0, "2025-09-03", "2026-12-02", 15, 5),
            )


def test_no_per_month_columns(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        month_like = []
        for table in tables:
            columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
            for column in columns:
                name = column[1].lower()
                if name[:3] in ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"):
                    month_like.append(f"{table}.{column[1]}")
    assert month_like == []
