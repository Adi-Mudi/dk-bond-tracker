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
