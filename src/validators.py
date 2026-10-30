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


def validate_credit_day(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise AppError("ERR-date-range", f"credit_day must be an integer in 1-28: {value!r}")
    if value < 1 or value > 28:
        raise AppError("ERR-date-range", f"credit_day must be in 1-28: {value}")
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
