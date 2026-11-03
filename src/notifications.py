import calendar
from datetime import date

from .status import month_key, tenure_month_map
from .validators import AppError, add_months, parse_date_value, validate_credit_day


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
        credit_day = validate_credit_day(row["credit_day"], "ERR-notify-build", context=f"bond {row['id']}")
        due_day = min(credit_day, calendar.monthrange(today.year, today.month)[1])
        lead_day = due_day - 2
        is_lead = lead_day >= 1 and today.day == lead_day
        is_day_of = today.day == due_day
        if not is_lead and not is_day_of:
            continue
        try:
            months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
        except AppError as exc:
            raise AppError("ERR-notify-build", f"bond {row['id']}: {exc.message}") from exc
        if current_month not in months:
            continue
        if months.get(current_month, False):
            continue
        if is_day_of:
            key = f"dayof:{row['id']}:{current_month}"
            severity = "due_today"
            message = f"{row['company']} payment due today (day {due_day})"
        else:
            days_left = due_day - today.day
            key = f"due:{row['id']}:{current_month}"
            severity = "reminder"
            message = f"{row['company']} payment due in {days_left} days (credit day {credit_day})"
        if notify_once(conn, key, severity, message) is None:
            continue
        created.append(
            {
                "bond_id": row["id"],
                "company": row["company"],
                "month": current_month,
                "credit_day": credit_day,
                "severity": severity,
            }
        )
    return created


def maturity_reminders(conn, today, horizons=(30, 7, 1)):
    if not isinstance(today, date):
        raise AppError("ERR-notify-build", f"today must be a date: {today!r}")
    created = []
    rows = conn.execute(
        "SELECT id, company, start_date, end_date, tenure_months, status FROM bonds ORDER BY id"
    ).fetchall()
    for row in rows:
        if row["status"] == "Completed":
            continue
        end_date = None
        raw_end = row["end_date"]
        if raw_end:
            try:
                end_date = parse_date_value(raw_end, "end_date")
            except AppError:
                end_date = None
        if end_date is None and row["start_date"] and row["tenure_months"]:
            try:
                start = parse_date_value(row["start_date"], "start_date")
                end_date = add_months(start, int(row["tenure_months"]))
            except (AppError, TypeError, ValueError):
                continue
        if end_date is None:
            continue
        days_left = (end_date - today).days
        if days_left not in horizons:
            continue
        key = f"maturity:{row['id']}:{today.isoformat()}:{days_left}d"
        message = (
            f"{row['company']} matures in {days_left} day(s) "
            f"({end_date.strftime('%d %b %Y')})"
        )
        if notify_once(conn, key, "maturity_soon", message) is None:
            continue
        created.append(
            {
                "bond_id": row["id"],
                "company": row["company"],
                "end_date": end_date.isoformat(),
                "days_left": days_left,
                "severity": "maturity_soon",
            }
        )
    return created
