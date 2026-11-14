import re

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

CANONICAL_CYCLES = ("monthly", "quarterly", "annual")

CYCLE_ALIASES = {
    "monthly": "monthly",
    "quarterly": "quarterly",
    "yearly": "annual",
    "annual": "annual",
}

INVESTMENT_GRADE_BANDS = ("AAA", "AA", "A", "BBB")

RATING_AGENCY_PREFIXES = ("CRISIL", "ICRA", "CARE", "IND", "BWR")

_AGENCY_ALTERNATION = "|".join(RATING_AGENCY_PREFIXES)
_BAND_ALTERNATION = "|".join(INVESTMENT_GRADE_BANDS)

_RATING_PATTERN = re.compile(
    rf"^(?:(?:{_AGENCY_ALTERNATION})[\s-]*)?"
    rf"(?P<band>(?:{_BAND_ALTERNATION}))(?P<modifier>[+-]?)$"
)


def _text(value):
    return str(value if value is not None else "").strip()


def normalize_isin(value):
    text = _text(value).upper()
    return text if ISIN_PATTERN.match(text) else None


def is_valid_isin(value):
    return normalize_isin(value) is not None


def normalize_cycle(value):
    return CYCLE_ALIASES.get(_text(value).lower())


def rating_band(value):
    match = _RATING_PATTERN.match(_text(value).upper())
    return None if match is None else match.group("band")


def is_investment_grade(value):
    return rating_band(value) is not None


def split_rating(value, agency=None):
    text = _text(value).upper()
    existing = _text(agency) or None
    if not text:
        return None, existing
    grade = text
    embedded = None
    for prefix in RATING_AGENCY_PREFIXES:
        if grade.startswith(prefix):
            embedded = prefix
            grade = grade[len(prefix):].lstrip(" -/").strip()
            break
    resolved = existing
    if embedded is not None and resolved is None:
        resolved = embedded
    return (grade or None), resolved
