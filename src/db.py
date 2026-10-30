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
        credit_day INTEGER CHECK (credit_day >= 1 AND credit_day <= 28),
        status TEXT DEFAULT 'On-going',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    )""",
    """CREATE TABLE IF NOT EXISTS payment_ledger (
        id INTEGER PRIMARY KEY,
        bond_id INTEGER NOT NULL REFERENCES bonds(id),
        month TEXT,
        amount REAL,
        paid INTEGER DEFAULT 0,
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
    """CREATE TABLE IF NOT EXISTS share_config (
        id INTEGER PRIMARY KEY,
        section TEXT,
        included INTEGER DEFAULT 0
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


def init_db(path):
    db_path = str(Path(path))
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        with get_conn(db_path) as conn:
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
