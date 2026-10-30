from datetime import date

from .status import month_key, tenure_month_map
from .validators import AppError


def notify(conn, severity, message):
    if not isinstance(severity, str) or not severity.strip():
        raise AppError("ERR-notify-build", f"severity must be a non-empty string: {severity!r}")
    if not isinstance(message, str) or not message.strip():
        raise AppError("ERR-notify-build", f"message must be a non-empty string: {message!r}")
    cursor = conn.execute(
        "INSERT INTO notifications (severity, message, read) VALUES (?, ?, 0)",
        (severity.strip(), message),
    )
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-notify-build",
            f"notification insert affected {cursor.rowcount} rows: {message!r}",
        )
    return cursor.lastrowid


def notify_once(conn, key, severity, message):
    if not isinstance(key, str) or not key.strip():
        raise AppError("ERR-notify-build", f"dedupe key must be a non-empty string: {key!r}")
    cursor = conn.execute(
        "INSERT OR IGNORE INTO alert_prefs (key, value) VALUES (?, ?)",
        (key.strip(), "1"),
    )
    if cursor.rowcount != 1:
        return None
    return notify(conn, severity, message)


def unread_count(conn):
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM notifications WHERE read = 0"
    ).fetchone()
    return int(row["n"])


def mark_all_read(conn):
    cursor = conn.execute("UPDATE notifications SET read = 1 WHERE read = 0")
    if cursor.rowcount < 0:
        raise AppError("ERR-notify-build", "mark-all-read affected an unknown row count")
    return cursor.rowcount


def list_notifications(conn, limit=None):
    query = "SELECT id, created_at, severity, message, read FROM notifications ORDER BY created_at DESC, id DESC"
    if limit is not None:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise AppError("ERR-notify-build", f"limit must be a positive integer: {limit!r}")
        query = f"{query} LIMIT {int(limit)}"
    rows = conn.execute(query).fetchall()
    return [dict(row) for row in rows]


def due_reminders(conn, today):
    if not isinstance(today, date):
        raise AppError("ERR-notify-build", f"today must be a date: {today!r}")
    created = []
    current_month = month_key(today)
    rows = conn.execute(
        "SELECT id, company, start_date, tenure_months, credit_day, status FROM bonds ORDER BY id"
    ).fetchall()
    for row in rows:
        if row["status"] == "Completed":
            continue
        credit_day = row["credit_day"]
        if isinstance(credit_day, bool) or not isinstance(credit_day, int) or not 1 <= credit_day <= 28:
            raise AppError(
                "ERR-notify-build",
                f"bond {row['id']}: missing or invalid credit_day: {credit_day!r}",
            )
        lead_day = credit_day - 2
        if lead_day < 1 or today.day != lead_day:
            continue
        try:
            months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
        except AppError as exc:
            raise AppError("ERR-notify-build", f"bond {row['id']}: {exc.message}") from exc
        if current_month not in months:
            continue
        if months.get(current_month, False):
            continue
        days_left = credit_day - today.day
        key = f"due:{row['id']}:{current_month}"
        message = f"{row['company']} payment due in {days_left} days (credit day {credit_day})"
        if notify_once(conn, key, "reminder", message) is None:
            continue
        created.append(
            {
                "bond_id": row["id"],
                "company": row["company"],
                "month": current_month,
                "credit_day": credit_day,
                "severity": "reminder",
            }
        )
    return created
