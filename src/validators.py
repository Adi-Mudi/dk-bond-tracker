import calendar
import re
from datetime import date, datetime


class AppError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


def raise_app_error(code, message):
    raise AppError(code, message)


def normalize_header(text):
    return " ".join(str(text).split())


def header_key(text):
    return re.sub(r"[^a-z0-9]", "", normalize_header(text).lower())


def parse_date_value(value, field):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        text = value.strip()
        for pattern in ("%Y-%m-%d", "%Y-%m", "%b-%y", "%b-%Y", "%d-%b-%Y"):
            try:
                return datetime.strptime(text, pattern).date()
            except ValueError:
                continue
    raise AppError("ERR-date-range", f"unparseable {field}: {value!r}")


def add_months(day, months):
    total = day.year * 12 + (day.month - 1) + months
    year, zero_based = divmod(total, 12)
    month = zero_based + 1
    last_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last_day))


def tenure_from_range(start_value, end_value):
    start = parse_date_value(start_value, "start_date")
    end = parse_date_value(end_value, "end_date")
    if end <= start:
        raise AppError(
            "ERR-date-range",
            f"end_date must be after start_date: {start.isoformat()} .. {end.isoformat()}",
        )
    return (end.year - start.year) * 12 + (end.month - start.month)


def validate_credit_day(value, code="ERR-date-range", context=None):
    if isinstance(value, bool) or not isinstance(value, int) or value < 1 or value > 31:
        message = f"credit_day must be an integer in 1-31: {value!r}"
        if context is not None:
            message = f"{context}: {message}"
        raise AppError(code, message)
    return value


def date_range_tenure(start_value, end_value, credit_day):
    start = parse_date_value(start_value, "start_date")
    end = parse_date_value(end_value, "end_date")
    tenure = tenure_from_range(start, end)
    credit = validate_credit_day(credit_day)
    return start, end, tenure, credit


def legacy_position(start_value, tenure_value):
    start = parse_date_value(start_value, "start_month")
    if isinstance(tenure_value, bool) or not isinstance(tenure_value, (int, float)):
        raise AppError("ERR-date-range", f"tenure_months must be a number: {tenure_value!r}")
    if float(tenure_value) != int(tenure_value):
        raise AppError("ERR-date-range", f"tenure_months must be a whole number: {tenure_value!r}")
    tenure = int(tenure_value)
    if tenure < 1:
        raise AppError("ERR-date-range", f"tenure_months must be positive: {tenure}")
    end = add_months(start, tenure)
    credit = min(start.day, 28)
    return start, end, tenure, credit


def active_position_lock(conn, company, isin):
    from .lock import check_add_allowed

    check_add_allowed(company, isin, conn)


def is_blank(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def percent_value(raw, field, code, required=True):
    text = str(raw if raw is not None else "").strip()
    if not text:
        if required:
            raise AppError(code, f"{field} is required")
        return None
    try:
        value = float(text)
    except (TypeError, ValueError) as exc:
        raise AppError(code, f"{field} must be a number: {raw!r}") from exc
    if value < 0:
        raise AppError(code, f"{field} must not be negative: {raw!r}")
    return value


FIRST_DATA_ROW = 2
MASTER_FIELDS = (
    "company",
    "isin",
    "status",
    "tenure_months",
    "start_month",
    "investment",
    "maturity",
)


def find_duplicate_isins(bonds):
    if bonds is None:
        raise AppError("ERR-duplicate-check", "bond set unavailable")
    grouped = {}
    for position, bond in enumerate(bonds):
        raw = bond.get("isin")
        if is_blank(raw):
            continue
        key = str(raw).strip().upper()
        entry = grouped.setdefault(key, {"rows": [], "values": []})
        entry["rows"].append(bond.get("row", position + FIRST_DATA_ROW))
        entry["values"].append(raw)
    duplicates = []
    for key, entry in grouped.items():
        if len(entry["rows"]) > 1:
            duplicates.append({"isin": key, "occurrences": entry["rows"], "values": entry["values"]})
    return duplicates


def validate_extracted(bonds, grid):
    duplicates = find_duplicate_isins(bonds)
    if duplicates:
        details = []
        for duplicate in duplicates:
            rows = ", ".join(str(row) for row in duplicate["occurrences"])
            values = ", ".join(repr(value) for value in duplicate["values"])
            details.append(f"{duplicate['isin']} at rows {rows} (values: {values})")
        raise AppError("ERR-04", "duplicate ISIN: " + "; ".join(details))
    for position, bond in enumerate(bonds):
        missing = [field for field in MASTER_FIELDS if is_blank(bond.get(field))]
        if missing:
            row_number = bond.get("row", position + FIRST_DATA_ROW)
            raise AppError("ERR-05", f"row {row_number}: missing {', '.join(missing)}")
    if len(grid) != len(bonds):
        raise AppError("ERR-05", f"grid rows {len(grid)} != bond rows {len(bonds)}")
