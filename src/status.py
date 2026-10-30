from datetime import date

from .validators import AppError, add_months, parse_date_value


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
    paid_map = {}
    rows = conn.execute(
        "SELECT month, amount, paid FROM payment_ledger WHERE bond_id = ? ORDER BY month",
        (bond_id,),
    ).fetchall()
    for row in rows:
        amount = row["amount"]
        paid_map[row["month"]] = bool(row["paid"]) and amount is not None and float(amount) > 0
    return {key: paid_map.get(key, False) for key in window}


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
    if isinstance(credit_day, bool) or not isinstance(credit_day, int) or not 1 <= credit_day <= 28:
        raise AppError(
            "ERR-credit-sweep",
            f"credit_day must be an integer in 1-28: {credit_day!r}",
        )
    paid_count = sum(1 for paid in months.values() if paid)
    if paid_count >= tenure:
        return False
    current = month_key(today)
    if current not in months:
        return False
    if today.day <= credit_day:
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
