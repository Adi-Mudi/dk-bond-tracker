from src.db import get_conn, init_db

EXPECTED_TABLES = [
    "alert_prefs",
    "bonds",
    "financial_goals",
    "notifications",
    "payment_ledger",
    "share_config",
]


def table_names(db_path):
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        ).fetchall()
    return [row[0] for row in rows]


def test_init_db_creates_all_six_tables(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    assert table_names(db_path) == EXPECTED_TABLES


def test_init_db_is_idempotent_on_second_run(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    init_db(db_path)
    assert table_names(db_path) == EXPECTED_TABLES


def test_get_conn_enables_foreign_keys(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        fk = conn.execute("PRAGMA foreign_keys").fetchone()[0]
    assert fk == 1


def test_payment_ledger_has_unique_bond_month(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        index_rows = conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type = 'index' AND tbl_name = 'payment_ledger'"
        ).fetchall()
        indexes = {row[0] for row in index_rows}
    assert "sqlite_autoindex_payment_ledger_1" in indexes


def test_bond_insert_select_roundtrip(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds "
            "(company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            ("Acme", "INE0000000001", "Acme N2 9.5%", 100000.0, "2025-09-03", "2026-12-02", 15, 5),
        )
        row = conn.execute(
            "SELECT id, company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, status, created_at "
            "FROM bonds WHERE id = ?",
            (cursor.lastrowid,),
        ).fetchone()
    assert row["company"] == "Acme"
    assert row["isin"] == "INE0000000001"
    assert row["name"] == "Acme N2 9.5%"
    assert row["amount"] == 100000.0
    assert row["start_date"] == "2025-09-03"
    assert row["end_date"] == "2026-12-02"
    assert row["tenure_months"] == 15
    assert row["credit_day"] == 5
    assert row["status"] == "On-going"
    assert row["created_at"]


def test_init_db_creates_missing_parent_dirs(tmp_path):
    nested = tmp_path / "fresh" / "data" / "bonds.db"
    init_db(str(nested))
    assert nested.is_file()
    with get_conn(str(nested)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "bonds" in tables
    assert "payment_ledger" in tables
