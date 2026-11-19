from __future__ import annotations

import json
import re
import time

from .base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_PARSE_ERROR,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    LISTING_STATUSES,
    FetchResult,
)
from .normalize import RATING_AGENCY_PREFIXES, normalize_cycle, normalize_isin

SOURCE_NAME = "NSDL"
DEFAULT_TIMEOUT = 10.0
_SCHEME = "https"
_SLASHES = "://"
NSDL_HOST = "nsdl.com"
SEARCH_PATH = "/web/api/v1/participant/search"
ENDPOINT = _SCHEME + _SLASHES + NSDL_HOST + SEARCH_PATH
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
DEFAULT_PER_PAGE = 100
MAX_ATTEMPTS = 3
RETRY_DELAY = 0.5
_RETRYABLE_BODY = (FAILURE_BLOCKED, FAILURE_PARSE_ERROR, FAILURE_MALFORMED)

RECORD_KEYS = ("data", "records", "securities")
_MONTH_CODES = {
    "JA": "01",
    "FE": "02",
    "MR": "03",
    "AP": "04",
    "MY": "05",
    "JN": "06",
    "JL": "07",
    "AU": "08",
    "SP": "09",
    "OC": "10",
    "NV": "11",
    "DC": "12",
}
_MATURITY_RE = re.compile(r"\b(\d{2})(JA|FE|MR|AP|MY|JN|JL|AU|SP|OC|NV|DC)(\d{2})\b")
_FACE_VALUE_RE = re.compile(r"\bFVRS(\d+(?:\.\d+)?)\b", re.IGNORECASE)


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no published-download transport configured")


def build_url(isin, per_page=DEFAULT_PER_PAGE, base=None):
    root = (base or ENDPOINT).rstrip("/")
    query = (
        "search_type=DetailedSearch"
        "&name="
        f"&isin={isin}"
        "&page=1"
        f"&per_page={per_page}"
    )
    return root + "?" + query


def _text(value):
    return "" if value is None else str(value).strip()


def _clean_name(value):
    return _text(value).strip(" \"'")


def _number(value):
    text = _text(value).replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _secured(value):
    text = _text(value).lower()
    if text in ("1", "yes", "true", "y"):
        return 1
    if text in ("0", "no", "false", "n"):
        return 0
    return None


def _listing(value):
    text = _text(value).lower()
    if not text:
        return None
    return text if text in LISTING_STATUSES else "unknown"


def _lower(value):
    return _text(value).lower() or None


def _rating_pair(record):
    raw = _text(record.get("credit_rating"))
    agency = _text(record.get("rating_agency")) or None
    if not raw:
        return None, agency
    rating = raw.upper()
    if agency is not None:
        prefix = agency.upper()
        if rating.startswith(prefix):
            rating = rating[len(prefix):].strip(" -")
    else:
        for candidate in RATING_AGENCY_PREFIXES:
            if rating.startswith(candidate):
                agency = candidate
                rating = rating[len(candidate):].strip(" -")
                break
    return (rating or None), agency


def _maturity(value):
    match = _MATURITY_RE.search(_text(value).upper())
    if match is None:
        return None
    day, month, year = match.groups()
    return f"20{year}-{_MONTH_CODES[month]}-{day}"


def _description_face_value(value):
    match = _FACE_VALUE_RE.search(_text(value))
    return None if match is None else _number(match.group(1))


def _compose(isin, record):
    rating, agency = _rating_pair(record)
    description = _text(record.get("isin_description__value"))
    values = {
        "company": _clean_name(record.get("name"))
        or _text(record.get("issuer_name"))
        or _text(record.get("security_name"))
        or None,
        "coupon": _number(record.get("coupon_rate")),
        "payout_cycle": normalize_cycle(record.get("interest_frequency")),
        "face_value": _number(record.get("face_value"))
        or _description_face_value(description),
        "rating": rating,
        "rating_agency": agency,
        "issuer_type": _lower(record.get("security_type"))
        or _lower(record.get("security_description")),
        "secured": _secured(record.get("secured")),
        "listing_status": _listing(record.get("listing_status")),
        "maturity": _text(record.get("maturity_date")) or _maturity(description) or None,
    }
    populated = {name: value for name, value in values.items() if value is not None}
    return FetchResult(isin=isin, sources={name: SOURCE_NAME for name in populated}, **populated)


def _records(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in RECORD_KEYS:
            value = document.get(key)
            if isinstance(value, list):
                return value
    return None


def _find(records, isin):
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate = record.get("isin")
        if candidate is None:
            candidate = record.get("field_isin")
        if normalize_isin(candidate) == isin:
            return record
    return None


def _count(value):
    if value is None:
        return None
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _failed(isin, failure_code):
    return FetchResult(isin=isin, failure_code=failure_code)


def _map_body(isin, body):
    text = body.strip()
    if not text:
        return _failed(isin, FAILURE_MALFORMED)
    if text.startswith("<"):
        return _failed(isin, FAILURE_BLOCKED)
    try:
        document = json.loads(text)
    except json.JSONDecodeError:
        return _failed(isin, FAILURE_PARSE_ERROR)
    if isinstance(document, dict) and "data" in document:
        count = _count(document.get("count"))
        if count is None:
            return _failed(isin, FAILURE_MALFORMED)
        if count == 0:
            return _failed(isin, FAILURE_NOT_FOUND)
    records = _records(document)
    if records is None:
        return _failed(isin, FAILURE_MALFORMED)
    record = _find(records, isin)
    if record is None:
        return _failed(isin, FAILURE_NOT_FOUND)
    return _compose(isin, record)


class NsdlAdapter:
    name = SOURCE_NAME

    def __init__(
        self,
        transport=None,
        timeout=DEFAULT_TIMEOUT,
        url=None,
        per_page=DEFAULT_PER_PAGE,
        max_attempts=MAX_ATTEMPTS,
        retry_delay=RETRY_DELAY,
        sleep=None,
    ):
        self.url = url or ENDPOINT
        self.timeout = timeout
        self.per_page = per_page
        self.max_attempts = max(1, int(max_attempts))
        self.retry_delay = retry_delay
        self._sleep = sleep or time.sleep
        self._transport = transport or _no_transport

    def fetch(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return _failed(isin, FAILURE_INVALID_ISIN)
        url = build_url(normalized, self.per_page, self.url)
        attempt = 0
        while True:
            try:
                payload = self._transport(url, self.timeout)
            except SourceError as exc:
                return _failed(normalized, exc.failure_code)
            except TimeoutError:
                return _failed(normalized, FAILURE_TIMEOUT)
            except FileNotFoundError:
                return _failed(normalized, FAILURE_NOT_FOUND)
            except OSError:
                return _failed(normalized, FAILURE_UNREACHABLE)
            except Exception:
                return _failed(normalized, FAILURE_UNREACHABLE)
            if isinstance(payload, bytes):
                payload = payload.decode("utf-8", "replace")
            result = _map_body(normalized, payload)
            if (
                result.failure_code not in _RETRYABLE_BODY
                or attempt >= self.max_attempts - 1
            ):
                return result
            attempt += 1
            self._sleep(self.retry_delay * attempt)
