from .db import get_conn

SNAPSHOT_VERSION_KEY = "bond_master_snapshot_version"


def get_pref(conn, key, default=None):
    row = conn.execute(
        "SELECT value FROM alert_prefs WHERE key = ?", (key,)
    ).fetchone()
    if row is None:
        return default
    return row["value"]


def set_pref(conn, key, value):
    conn.execute(
        "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
        (key, value),
    )


def get_snapshot_version(conn, default=None):
    return get_pref(conn, SNAPSHOT_VERSION_KEY, default)


def set_snapshot_version(conn, value):
    set_pref(conn, SNAPSHOT_VERSION_KEY, value)


def alert_prefs_map(db_file):
    with get_conn(db_file) as conn:
        rows = conn.execute("SELECT key, value FROM alert_prefs").fetchall()
    return {row["key"]: row["value"] for row in rows}
