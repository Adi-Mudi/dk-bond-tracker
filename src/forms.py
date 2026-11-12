import re

from .validators import AppError, date_range_tenure

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")
ISSUER_TYPES = ("corporate_bond", "ncd", "sdi", "government", "fd")
PAYOUT_CYCLES = ("monthly", "quarterly", "annual")

FETCHED_FIELD_BY_FACT = {
    "company": "company",
    "rating": "rating",
    "rating_agency": "rating_agency",
    "coupon": "coupon_pct",
    "face_value": "face_value",
    "issuer_type": "issuer_type",
    "payout_cycle": "payout_cycle",
    "secured": "secured",
}
FACT_BY_FIELD = {field: fact for fact, field in FETCHED_FIELD_BY_FACT.items()}


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


def _fetched_number(raw):
    text = str(raw if raw is not None else "").strip()
    if not text:
        return None
    try:
        value = float(text)
    except (TypeError, ValueError):
        return None
    if value < 0:
        return None
    return value


def _fetched_enum(raw, key, allowed):
    try:
        return _optional_enum({key: raw}, key, allowed, "ERR-autofetch")
    except AppError:
        return None


def fetched_form_values(facts):
    facts = facts or {}
    values = {}
    company = str(facts.get("company") or "").strip()
    if company:
        values["company"] = company
    rating = str(facts.get("rating") or "").strip()
    if rating:
        values["rating"] = rating
    rating_agency = str(facts.get("rating_agency") or "").strip()
    if rating_agency:
        values["rating_agency"] = rating_agency
    coupon = _fetched_number(facts.get("coupon"))
    if coupon is not None:
        values["coupon_pct"] = f"{coupon:g}"
    face_value = _fetched_number(facts.get("face_value"))
    if face_value is not None:
        values["face_value"] = f"{face_value:g}"
    issuer_type = _fetched_enum(facts.get("issuer_type"), "issuer_type", ISSUER_TYPES)
    if issuer_type:
        values["issuer_type"] = issuer_type
    payout_cycle = _fetched_enum(facts.get("payout_cycle"), "payout_cycle", PAYOUT_CYCLES)
    if payout_cycle:
        values["payout_cycle"] = payout_cycle
    secured = facts.get("secured")
    if secured in (0, 1):
        values["secured"] = str(int(secured))
    return values


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
