from __future__ import annotations

import json

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
NSDL_HOST = "nsdl.co.in"
NSDL_MASTER_PATH = "/downloadables/corporate_bond_master.json"
ENDPOINT = _SCHEME + _SLASHES + NSDL_HOST + NSDL_MASTER_PATH

RECORD_KEYS = ("records", "data", "securities")


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no published-download transport configured")


def _text(value):
    return "" if value is None else str(value).strip()


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


def _compose(isin, record):
    rating, agency = _rating_pair(record)
    values = {
        "company": _text(record.get("issuer_name")) or _text(record.get("security_name")) or None,
        "coupon": _number(record.get("coupon_rate")),
        "payout_cycle": normalize_cycle(record.get("interest_frequency")),
        "face_value": _number(record.get("face_value")),
        "rating": rating,
        "rating_agency": agency,
        "issuer_type": _lower(record.get("security_type")),
        "secured": _secured(record.get("secured")),
        "listing_status": _listing(record.get("listing_status")),
        "maturity": _text(record.get("maturity_date")) or None,
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
        if isinstance(record, dict) and normalize_isin(record.get("isin")) == isin:
            return record
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
    records = _records(document)
    if records is None:
        return _failed(isin, FAILURE_MALFORMED)
    record = _find(records, isin)
    if record is None:
        return _failed(isin, FAILURE_NOT_FOUND)
    return _compose(isin, record)


class NsdlAdapter:
    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT, url=ENDPOINT):
        self.url = url
        self.timeout = timeout
        self._transport = transport or _no_transport

    def fetch(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return _failed(isin, FAILURE_INVALID_ISIN)
        try:
            payload = self._transport(self.url, self.timeout)
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
        return _map_body(normalized, payload)
