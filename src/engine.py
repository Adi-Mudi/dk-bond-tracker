import calendar
from datetime import date

from .status import month_key
from .validators import AppError, add_months, parse_date_value, validate_credit_day

DISPLAY_LABELS = {"Returned": "Received", "Completed": "Matured"}
HEALTH_ORDER = {"Danger": 0, "On-going": 1, "Matured": 2, "Invalid": 3}


def display_label(value):
    if value is None:
        return ""
    return DISPLAY_LABELS.get(value, value)


def due_day(credit_day, year, month):
    return min(int(credit_day), calendar.monthrange(year, month)[1])


def payout_date_label(month, credit_day):
    year, month_number = month.split("-")
    day = due_day(credit_day, int(year), int(month_number))
    return f"{day:02d} {calendar.month_abbr[int(month_number)]} {year}"


def month_due_passed(month, credit_day, today):
    current = month_key(today)
    if month < current:
        return True
    if month > current:
        return False
    return today.day >= due_day(credit_day, today.year, today.month)


def entry_paid(entry):
    if not entry:
        return False
    try:
        amount = entry["amount"]
        flag = entry["paid"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError("ERR-health-compute", f"ledger entry unreadable: {exc}") from exc
    if amount is None:
        return False
    try:
        value = float(amount)
    except (TypeError, ValueError) as exc:
        raise AppError("ERR-health-compute", f"ledger amount unreadable: {amount!r}") from exc
    return bool(flag) and value > 0


def _require_date(value, field):
    if not isinstance(value, date):
        raise AppError("ERR-health-compute", f"{field} must be a date: {value!r}")
    return value


def _require_tenure(value):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AppError(
            "ERR-health-compute", f"tenure_months must be a positive integer: {value!r}"
        )
    return value


def _require_credit_day(value):
    return validate_credit_day(value, "ERR-health-compute")


def _position_value(position, key):
    try:
        return position[key]
    except (KeyError, IndexError, TypeError) as exc:
        raise AppError("ERR-health-compute", f"position field {key} missing: {exc}") from exc


def _row_value(row, key, default=None):
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        return default


def _paid_map(ledger_entries):
    if ledger_entries is None:
        return {}
    if isinstance(ledger_entries, dict):
        paid = {}
        for key, value in ledger_entries.items():
            if isinstance(value, (bool, int, float)):
                paid[str(key)] = bool(value)
            else:
                paid[str(key)] = entry_paid(value)
        return paid
    paid = {}
    try:
        entries = list(ledger_entries)
    except TypeError as exc:
        raise AppError("ERR-health-compute", f"ledger entries unreadable: {exc}") from exc
    for entry in entries:
        try:
            month = str(entry["month"])
        except (KeyError, IndexError, TypeError) as exc:
            raise AppError("ERR-health-compute", f"ledger entry unreadable: {exc}") from exc
        paid[month] = entry_paid(entry)
    return paid


def tenure_window(start_value, tenure_value):
    start = parse_date_value(start_value, "start_date")
    tenure = _require_tenure(tenure_value)
    return [month_key(add_months(start, offset)) for offset in range(tenure)]


def derive_health(position, ledger_entries, today):
    today = _require_date(today, "today")
    start = parse_date_value(_position_value(position, "start_date"), "start_date")
    end = parse_date_value(_position_value(position, "end_date"), "end_date")
    tenure = _require_tenure(_position_value(position, "tenure_months"))
    credit_day = _require_credit_day(_position_value(position, "credit_day"))
    window = tenure_window(start, tenure)
    paid = _paid_map(ledger_entries)
    paid_count = sum(1 for key in window if paid.get(key, False))
    if end <= today or paid_count >= tenure:
        return "Matured"
    for key in window:
        if not paid.get(key, False) and month_due_passed(key, credit_day, today):
            return "Danger"
    return "On-going"


def row_sort_key(row):
    value = _row_value(row, "health")
    if value is None:
        value = _row_value(row, "status")
    label = display_label(value)
    if label not in HEALTH_ORDER:
        raise AppError("ERR-row-sort", f"unknown status value: {value!r}")
    row_id = _row_value(row, "id")
    return (
        HEALTH_ORDER[label],
        str(_row_value(row, "company") or "").lower(),
        row_id if isinstance(row_id, int) else 0,
    )


def sort_rows(rows):
    return sorted(rows, key=row_sort_key)


def list_months_through_current(today, first_key=None):
    today = _require_date(today, "today")
    current = month_key(today)
    if first_key is None:
        return [current]
    start_date = parse_date_value(first_key, "first_month")
    if month_key(start_date) >= current:
        return [current]
    keys = []
    offset = 0
    while True:
        key = month_key(add_months(start_date, offset))
        keys.append(key)
        if key >= current:
            return keys
        offset += 1
