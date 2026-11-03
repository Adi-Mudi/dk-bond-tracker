import re

from .validators import AppError, date_range_tenure

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
ISSUER_TYPES = ("corporate_bond", "ncd", "sdi", "government", "fd")
PAYOUT_CYCLES = ("monthly", "quarterly", "annual")


def _required_text(form, key, label, code):
    value = str(form.get(key, "")).strip()
    if not value:
        raise AppError(code, f"{label} is required")
    return value


def _amount(form, code):
    raw = str(form.get("amount", "")).strip()
    try:
        amount = float(raw)
    except ValueError as exc:
        raise AppError(code, f"amount must be a number: {raw!r}") from exc
    if amount < 0:
        raise AppError(code, f"amount must not be negative: {raw!r}")
    return amount


def _credit_value(form, code):
    raw = str(form.get("credit_day", "")).strip()
    try:
        return int(raw)
    except ValueError as exc:
        raise AppError(code, f"credit day must be an integer in 1-31: {raw!r}") from exc


def _optional_enum(form, key, allowed, code):
    value = str(form.get(key, "")).strip() or None
    if value is not None and value not in allowed:
        raise AppError(code, f"{key} must be one of {', '.join(allowed)}: {value!r}")
    return value


def parse_position_form(form, code="ERR-add-fields"):
    company = _required_text(form, "company", "company", code)
    isin = _required_text(form, "isin", "ISIN", code).upper()
    amount = _amount(form, code)
    credit_value = _credit_value(form, code)
    start_date, end_date, tenure_months, credit_day = date_range_tenure(
        form.get("start_date", ""), form.get("end_date", ""), credit_value
    )
    if tenure_months < 1:
        raise AppError(
            "ERR-date-range",
            f"tenure must span at least one whole month: {tenure_months}",
        )
    return {
        "company": company,
        "isin": isin,
        "amount": amount,
        "start_date": start_date,
        "end_date": end_date,
        "tenure_months": tenure_months,
        "credit_day": credit_day,
        "issuer_type": _optional_enum(form, "issuer_type", ISSUER_TYPES, code),
        "payout_cycle": _optional_enum(form, "payout_cycle", PAYOUT_CYCLES, code),
        "secured": 1 if str(form.get("secured", "1")) == "1" else 0,
    }
