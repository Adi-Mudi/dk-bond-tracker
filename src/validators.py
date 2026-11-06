import calendar
from datetime import date, datetime


class AppError(Exception):
    def __init__(self, code, message):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


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


def validate_positive_int(value, field, code="ERR-date-range"):
    if isinstance(value, str):
        text = value.strip()
        try:
            value = int(text)
        except ValueError as exc:
            raise AppError(code, f"{field} must be a positive integer: {text!r}") from exc
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise AppError(code, f"{field} must be a positive integer: {value!r}")
    return value


def date_range_tenure(start_value, end_value, credit_day):
    start = parse_date_value(start_value, "start_date")
    end = parse_date_value(end_value, "end_date")
    tenure = tenure_from_range(start, end)
    credit = validate_credit_day(credit_day)
    return start, end, tenure, credit


def safe_float(value, default=0.0):
    try:
        return float(value) if value is not None else default
    except (TypeError, ValueError):
        return default


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
