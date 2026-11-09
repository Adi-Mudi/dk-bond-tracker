import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .validators import AppError

SCHEMA_STATEMENTS = (
    """CREATE TABLE IF NOT EXISTS bonds (
        id INTEGER PRIMARY KEY,
        company TEXT,
        isin TEXT UNIQUE,
        name TEXT,
        amount REAL,
        maturity REAL,
        start_date TEXT,
        end_date TEXT,
        tenure_months INTEGER,
        credit_day INTEGER CHECK (credit_day >= 1 AND credit_day <= 31),
        status TEXT DEFAULT 'On-going',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS payment_ledger (
        id INTEGER PRIMARY KEY,
        bond_id INTEGER NOT NULL REFERENCES bonds(id),
        month TEXT,
        amount REAL,
        paid INTEGER DEFAULT 0,
        tds_applied INTEGER NOT NULL DEFAULT 1,
        UNIQUE (bond_id, month)
    )""",
    """CREATE TABLE IF NOT EXISTS financial_goals (
        id INTEGER PRIMARY KEY,
        name TEXT,
        target_amount REAL,
        target_end_date TEXT,
        note TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS notifications (
        id INTEGER PRIMARY KEY,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        severity TEXT,
        message TEXT,
        read INTEGER DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS alert_prefs (
        id INTEGER PRIMARY KEY,
        key TEXT UNIQUE,
        value TEXT
    )""",
)


@contextmanager
def get_conn(db_path):
    conn = sqlite3.connect(str(Path(db_path)))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _ensure_columns(conn):
    bond_columns = {row[1] for row in conn.execute("PRAGMA table_info(bonds)")}
    if "maturity" not in bond_columns:
        conn.execute("ALTER TABLE bonds ADD COLUMN maturity REAL")
    for column in ("face_value REAL", "tlp_amount REAL", "payment_type TEXT", "interest_payout REAL", "qty REAL", "watch_investment REAL"):
        name = column.split()[0]
        if name not in bond_columns:
            conn.execute(f"ALTER TABLE bonds ADD COLUMN {column}")
    goal_columns = {row[1] for row in conn.execute("PRAGMA table_info(financial_goals)")}
    if "saved_amount" not in goal_columns:
        conn.execute("ALTER TABLE financial_goals ADD COLUMN saved_amount REAL DEFAULT 0")
    for column in ("monthly_amount REAL", "start_date TEXT", "checkins TEXT"):
        name = column.split()[0]
        if name not in goal_columns:
            conn.execute(f"ALTER TABLE financial_goals ADD COLUMN {column}")
    ledger_columns = {row[1] for row in conn.execute("PRAGMA table_info(payment_ledger)")}
    if "tds_applied" not in ledger_columns:
        conn.execute(
            "ALTER TABLE payment_ledger ADD COLUMN tds_applied INTEGER NOT NULL DEFAULT 1"
        )
    for column in (
        "rating TEXT",
        "rating_agency TEXT",
        "coupon_pct REAL",
        "expected_yield_pct REAL",
        "payout_cycle TEXT CHECK (payout_cycle IN ('monthly','quarterly','annual'))",
        "issuer_type TEXT CHECK (issuer_type IN ('corporate_bond','ncd','sdi','government','fd'))",
        "secured INT DEFAULT 1",
        "watch_state TEXT NOT NULL DEFAULT 'holding' CHECK (watch_state IN ('holding','watching'))",
        "broker TEXT",
        "purchase_date TEXT",
        "goal_id INTEGER",
    ):
        name = column.split()[0]
        if name not in bond_columns:
            conn.execute(f"ALTER TABLE bonds ADD COLUMN {column}")


def _migrate_credit_day_bound(conn):
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'bonds'"
    ).fetchone()
    if row is None:
        return
    create_sql = row["sql"]
    if not create_sql or not re.search(r"credit_day\s*<=\s*28\b", create_sql):
        return
    migrate_sql = re.sub(r"(credit_day\s*<=\s*)28\b", r"\g<1>31", create_sql, count=1)
    migrate_sql = re.sub(
        r"^CREATE\s+TABLE\s+(IF\s+NOT\s+EXISTS\s+)?bonds\b",
        "CREATE TABLE bonds_credit_day_migrate",
        migrate_sql,
        count=1,
        flags=re.IGNORECASE,
    )
    columns = [info[1] for info in conn.execute("PRAGMA table_info(bonds)").fetchall()]
    if not columns:
        raise AppError("ERR-schema-migrate", "bonds table has no columns")
    column_list = ", ".join(columns)
    before = conn.execute("SELECT COUNT(*) AS total FROM bonds").fetchone()["total"]
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS bonds_credit_day_migrate")
    conn.execute(migrate_sql)
    conn.execute(
        f"INSERT INTO bonds_credit_day_migrate ({column_list}) SELECT {column_list} FROM bonds"
    )
    conn.execute("DROP TABLE bonds")
    conn.execute("ALTER TABLE bonds_credit_day_migrate RENAME TO bonds")
    after = conn.execute("SELECT COUNT(*) AS total FROM bonds").fetchone()["total"]
    if after != before:
        raise AppError(
            "ERR-schema-migrate",
            f"credit day migration copied {after} of {before} bonds rows",
        )
    conn.commit()
    conn.execute("PRAGMA foreign_keys = ON")


def init_db(path):
    db_path = str(Path(path))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        with get_conn(db_path) as conn:
            _migrate_credit_day_bound(conn)
            for statement in SCHEMA_STATEMENTS:
                conn.execute(statement)
            _ensure_columns(conn)
    except AppError:
        raise
    except sqlite3.Error as exc:
        raise AppError(
            "ERR-schema-create",
            f"schema initialization failed for {db_path}: {exc}",
        ) from exc
