from __future__ import annotations

import csv
import io
from datetime import datetime

from .base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    FetchResult,
)
from .normalize import RATING_AGENCY_PREFIXES, normalize_cycle, normalize_isin

SOURCE_NAME = "BSE"
USER_AGENT = "DK Bond Tracker / 1.0.6"
DEFAULT_TIMEOUT = 10.0
_SCHEME = "https"
_SLASHES = "://"
BSE_DOWNLOAD_HOST = "www.bseindia.com"
BSE_DOWNLOAD_PREFIX = "/download/"
BSE_DEBT_SECURITY_MASTER_PATH = BSE_DOWNLOAD_PREFIX + "debt/DEBT_SECURITY_MASTER.csv"
BSE_DEBT_SECURITY_MASTER_URL = (
    _SCHEME + _SLASHES + BSE_DOWNLOAD_HOST + BSE_DEBT_SECURITY_MASTER_PATH
)

COLUMN_ISIN = "ISIN"
COLUMN_COMPANY = "ISSUER"
COLUMN_COUPON = "COUPON RATE"
COLUMN_CYCLE = "PAYOUT FREQUENCY"
COLUMN_FACE_VALUE = "FACE VALUE"
COLUMN_RATING = "CREDIT RATING"
COLUMN_AGENCY = "RATING AGENCY"
COLUMN_ISSUER_TYPE = "SECURITY TYPE"
COLUMN_SECURED = "SECURED"
COLUMN_LISTING_STATUS = "LISTING STATUS"
COLUMN_MATURITY = "MATURITY DATE"

_DATE_PATTERNS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%m/%d/%Y")
_SECURED_YES = frozenset({"1", "y", "yes", "true", "secured"})
_SECURED_NO = frozenset({"0", "n", "no", "false", "unsecured"})
_LISTED = frozenset({"listed", "list", "active"})
_UNLISTED = frozenset({"unlisted", "not listed", "private"})


def _no_transport(url, timeout):
    raise ConnectionError("no published-download transport configured")


def _clean(value):
    return "" if value is None else str(value).strip()


def _or_none(text):
    return text or None


def _to_float(value):
    text = _clean(value).replace(",", "").replace("%", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _to_secured(value):
    text = _clean(value).lower()
    if text in _SECURED_YES:
        return 1
    if text in _SECURED_NO:
        return 0
    return None


def _to_date(value):
    text = _clean(value)
    if not text:
        return None
    for pattern in _DATE_PATTERNS:
        try:
            return datetime.strptime(text, pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _to_listing_status(value):
    text = _clean(value).lower()
    if text in _LISTED:
        return "listed"
    if text in _UNLISTED:
        return "unlisted"
    return "unknown"


def _looks_like_html(text):
    head = text[:512].strip().lower()
    return head.startswith("<") or "<html" in head or "<!doctype" in head


def _split_rating(rating_value, agency_value):
    rating = _clean(rating_value)
    agency = _clean(agency_value)
    if rating and not agency:
        upper = rating.upper()
        for prefix in RATING_AGENCY_PREFIXES:
            if upper.startswith(prefix):
                agency = prefix
                rating = rating[len(prefix) :].strip(" -/")
                break
    return (_or_none(rating), _or_none(agency))


class BseAdapter:
    name = SOURCE_NAME

    def __init__(
        self, transport=None, timeout=DEFAULT_TIMEOUT, url=BSE_DEBT_SECURITY_MASTER_URL
    ):
        self.url = url
        self.timeout = timeout
        self._transport = transport or _no_transport

    def fetch(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return FetchResult(isin=isin, failure_code=FAILURE_INVALID_ISIN)
        try:
            payload = self._transport(self.url, self.timeout)
        except TimeoutError:
            return FetchResult(isin=normalized, failure_code=FAILURE_TIMEOUT)
        except FileNotFoundError:
            return FetchResult(isin=normalized, failure_code=FAILURE_NOT_FOUND)
        except OSError:
            return FetchResult(isin=normalized, failure_code=FAILURE_UNREACHABLE)
        except Exception:
            return FetchResult(isin=normalized, failure_code=FAILURE_UNREACHABLE)
        if isinstance(payload, bytes):
            payload = payload.decode("utf-8", "replace")
        text = _clean(payload)
        if _looks_like_html(text):
            return FetchResult(isin=normalized, failure_code=FAILURE_BLOCKED)
        if not text:
            return FetchResult(isin=normalized, failure_code=FAILURE_MALFORMED)
        try:
            return self.parse(text, normalized)
        except (csv.Error, ValueError, KeyError, IndexError):
            return FetchResult(isin=normalized, failure_code=FAILURE_PARSE_ERROR)

    def parse(self, text, isin):
        rows = list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))
        if not rows:
            return FetchResult(isin=isin, failure_code=FAILURE_MALFORMED)
        header = [_clean(cell).upper() for cell in rows[0]]
        if COLUMN_ISIN not in header:
            return FetchResult(isin=isin, failure_code=FAILURE_MALFORMED)
        for raw in rows[1:]:
            row = {
                header[index]: (raw[index] if index < len(raw) else "")
                for index in range(len(header))
            }
            if _clean(row.get(COLUMN_ISIN)).upper() == isin:
                return self._row_to_result(row, isin)
        return FetchResult(isin=isin, failure_code=FAILURE_NOT_FOUND)

    def _row_to_result(self, row, isin):
        rating, agency = _split_rating(row.get(COLUMN_RATING), row.get(COLUMN_AGENCY))
        facts = {
            "company": _or_none(_clean(row.get(COLUMN_COMPANY))),
            "coupon": _to_float(row.get(COLUMN_COUPON)),
            "payout_cycle": normalize_cycle(row.get(COLUMN_CYCLE)),
            "face_value": _to_float(row.get(COLUMN_FACE_VALUE)),
            "rating": rating,
            "rating_agency": agency,
            "issuer_type": _or_none(_clean(row.get(COLUMN_ISSUER_TYPE)).lower()),
            "secured": _to_secured(row.get(COLUMN_SECURED)),
            "listing_status": _to_listing_status(row.get(COLUMN_LISTING_STATUS)),
            "maturity": _to_date(row.get(COLUMN_MATURITY)),
        }
        sources = {
            field: SOURCE_NAME for field, value in facts.items() if value is not None
        }
        return FetchResult(isin=isin, sources=sources, failure_code=FAILURE_OK, **facts)
