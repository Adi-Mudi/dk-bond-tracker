import calendar
from datetime import date

from .ledger import paid_map
from .validators import AppError, add_months, parse_date_value, validate_credit_day


def month_key(value):
    return f"{value.year:04d}-{value.month:02d}"


def _validate_today(today):
    if not isinstance(today, date):
        raise AppError("ERR-status-compute", f"today must be a date: {today!r}")


def _validate_tenure(tenure_months):
    if isinstance(tenure_months, bool) or not isinstance(tenure_months, int) or tenure_months < 1:
        raise AppError(
            "ERR-status-compute",
            f"tenure_months must be a positive integer: {tenure_months!r}",
        )
    return tenure_months


def _validate_months(months):
    if not isinstance(months, dict):
        raise AppError("ERR-status-compute", f"months map must be a dict: {months!r}")
    return months


def _due_window(start_date, tenure_months):
    tenure = _validate_tenure(tenure_months)
    try:
        start = parse_date_value(start_date, "start_date")
    except AppError as exc:
        raise AppError(
            "ERR-status-compute",
            f"start month unparseable: {start_date!r}",
        ) from exc
    return [month_key(add_months(start, offset)) for offset in range(tenure)]


def tenure_month_map(conn, bond_id, start_date, tenure_months):
    window = _due_window(start_date, tenure_months)
    return paid_map(conn, bond_id, window)


def compute_row_status(months, tenure_months, today):
    tenure = _validate_tenure(tenure_months)
    _validate_months(months)
    _validate_today(today)
    paid_count = sum(1 for paid in months.values() if paid)
    if paid_count >= tenure:
        return "Completed"
    current = month_key(today)
    for key, paid in months.items():
        if key < current and not paid:
            return "Danger"
    return "On-going"


def credit_day_overdue(months, tenure_months, credit_day, today):
    tenure = _validate_tenure(tenure_months)
    _validate_months(months)
    _validate_today(today)
    credit_day = validate_credit_day(credit_day, "ERR-credit-sweep")
    paid_count = sum(1 for paid in months.values() if paid)
    if paid_count >= tenure:
        return False
    current = month_key(today)
    if current not in months:
        return False
    last_day = calendar.monthrange(today.year, today.month)[1]
    if today.day < min(credit_day + 1, last_day):
        return False
    return not months.get(current, False)


def compute_row_status_daywise(months, tenure_months, credit_day, today):
    status = compute_row_status(months, tenure_months, today)
    if status != "On-going":
        return status
    if credit_day_overdue(months, tenure_months, credit_day, today):
        return "Danger"
    return "On-going"


def recompute_all(conn, today):
    _validate_today(today)
    changed = []
    rows = conn.execute(
        "SELECT id, company, start_date, tenure_months, status FROM bonds ORDER BY id"
    ).fetchall()
    for row in rows:
        months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
        status = compute_row_status(months, row["tenure_months"], today)
        if status != row["status"]:
            conn.execute(
                "UPDATE bonds SET status = ? WHERE id = ?",
                (status, row["id"]),
            )
            changed.append(
                {
                    "bond_id": row["id"],
                    "company": row["company"],
                    "from": row["status"],
                    "to": status,
                }
            )
    return changed
