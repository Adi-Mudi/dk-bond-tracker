import sqlite3

import pytest

from src.db import get_conn, init_db

BOND_MASTER_COLUMNS = [
    "isin",
    "company",
    "payout_cycle",
    "face_value",
    "rating",
    "rating_agency",
    "issuer_type",
    "secured",
    "listing_status",
    "maturity",
    "source",
    "fetched_at",
]


def _table_names(db_path):
    with get_conn(db_path) as conn:
        return [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]


def _columns(db_path, table):
    with get_conn(db_path) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_init_db_creates_bond_master_with_all_columns(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    assert "bond_master" in _table_names(db_path)
    columns = _columns(db_path, "bond_master")
    for expected in BOND_MASTER_COLUMNS:
        assert expected in columns


def test_init_db_twice_is_idempotent(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    first_columns = _columns(db_path, "bond_master")
    init_db(db_path)
    assert _columns(db_path, "bond_master") == first_columns


def test_migration_adds_missing_columns_to_legacy_bond_master(tmp_path):
    db_path = tmp_path / "bonds.db"
    with get_conn(db_path) as conn:
        conn.execute("CREATE TABLE bond_master (isin TEXT PRIMARY KEY, company TEXT)")
    init_db(db_path)
    columns = _columns(db_path, "bond_master")
    for expected in BOND_MASTER_COLUMNS:
        assert expected in columns


def test_listing_status_check_rejects_unknown_value(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO bond_master (isin, listing_status) VALUES (?, ?)",
                ("INE0000000001", "private"),
            )


def test_listing_status_accepts_canonical_values(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        for index, value in enumerate(("listed", "unlisted", "unknown"), start=1):
            conn.execute(
                "INSERT INTO bond_master (isin, listing_status) VALUES (?, ?)",
                (f"INE00000000{index:02d}", value),
            )
        stored = {
            row[0] for row in conn.execute("SELECT listing_status FROM bond_master").fetchall()
        }
    assert stored == {"listed", "unlisted", "unknown"}


def test_payout_cycle_check_rejects_fourth_value(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO bond_master (isin, payout_cycle) VALUES (?, ?)",
                ("INE0000000001", "weekly"),
            )


def test_init_db_preserves_existing_bonds_rows(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds "
            "(company, isin, name, start_date, end_date, tenure_months, credit_day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("Acme", "INE0000000001", "Acme", "2025-09-03", "2026-12-02", 15, 5),
        )
    init_db(db_path)
    with get_conn(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
        isin = conn.execute("SELECT isin FROM bonds").fetchone()["isin"]
    assert count == 1
    assert isin == "INE0000000001"
