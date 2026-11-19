from __future__ import annotations

import json
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
from .normalize import normalize_cycle, normalize_isin, split_rating

SOURCE_NAME = "BSE"
DEFAULT_TIMEOUT = 10.0
_SCHEME = "https"
_SLASHES = "://"
BSE_WWW_HOST = "www.bseindia.com"
BSE_API_HOST = "api.bseindia.com"
BSE_BASE_URL = _SCHEME + _SLASHES + BSE_WWW_HOST + "/"
BSE_API_ROOT = _SCHEME + _SLASHES + BSE_API_HOST + "/BseIndiaAPI/api"
BSE_LIST_OF_SCRIP_PATH = "/ListofScripData/w"
BSE_LIST_OF_SCRIP_URL = BSE_API_ROOT + BSE_LIST_OF_SCRIP_PATH
BSE_DEBT_SEGMENT = "Debentures and Bonds"
BSE_ACTIVE_STATUS = "Active"
COOKIE_PRIME_URL = BSE_BASE_URL
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)
REQUEST_HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.5",
    "Origin": BSE_BASE_URL,
    "Referer": BSE_BASE_URL,
    "Connection": "keep-alive",
    "Sec-Fetch-Site": "same-site",
}
RECORD_KEYS = ("data", "Table", "records", "securities", "Data")
ISIN_KEYS = ("ISIN_NUMBER", "isin", "ISIN", "field_isin", "Isin", "isin_number")
_DATE_PATTERNS = ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%Y", "%m/%d/%Y")
_SECURED_YES = frozenset({"1", "y", "yes", "true", "secured"})
_SECURED_NO = frozenset({"0", "n", "no", "false", "unsecured"})
_LISTED = frozenset({"listed", "list", "active"})
_UNLISTED = frozenset({"unlisted", "not listed", "private"})


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no published-download transport configured")


def build_url(base=None, segment=BSE_DEBT_SEGMENT, status=BSE_ACTIVE_STATUS):
    root = (base or BSE_LIST_OF_SCRIP_URL).rstrip("/")
    query = (
        "scripcode=&Group=&industry=&segment="
        + segment.replace(" ", "%20")
        + "&status="
        + status
    )
    return root + "?" + query


def _failed(isin, failure_code):
    return FetchResult(isin=isin, failure_code=failure_code)


def _clean(value):
    return "" if value is None else str(value).strip()


def _or_none(text):
    return text or None


def _pick(record, *keys):
    for key in keys:
        value = _clean(record.get(key))
        if value:
            return value
    return ""


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
    return "unknown" if text else None


def _looks_like_html(text):
    head = text[:512].strip().lower()
    return head.startswith("<") or "<html" in head or "<!doctype" in head


def _records(document):
    if isinstance(document, list):
        return document
    if isinstance(document, dict):
        for key in RECORD_KEYS:
            value = document.get(key)
            if isinstance(value, list):
                return value
        for value in document.values():
            if isinstance(value, list):
                return value
    return None


def _find(records, isin):
    for record in records:
        if not isinstance(record, dict):
            continue
        for key in ISIN_KEYS:
            if normalize_isin(record.get(key)) == isin:
                return record
    return None


def _compose(isin, record):
    rating, agency = split_rating(
        _pick(
            record,
            "CREDIT_RATING",
            "Credit_Rating",
            "credit_rating",
            "RATING",
            "rating",
        ),
        _or_none(_pick(record, "RATING_AGENCY", "Rating_Agency", "rating_agency", "AGENCY")),
    )
    values = {
        "company": _or_none(
            _pick(
                record,
                "Issuer_Name",
                "issuer_name",
                "Scrip_Name",
                "scrip_name",
                "COMPANY",
                "name",
            )
        ),
        "coupon": _to_float(
            _pick(record, "COUPON_RATE", "Coupon_Rate", "coupon_rate", "Coupon", "COUPON")
        ),
        "payout_cycle": normalize_cycle(
            _pick(
                record,
                "PAYOUT_FREQUENCY",
                "Payout_Frequency",
                "payout_frequency",
                "Interest_Frequency",
                "interest_frequency",
                "frequency",
            )
        ),
        "face_value": _to_float(_pick(record, "FACE_VALUE", "face_value")),
        "rating": rating,
        "rating_agency": agency,
        "issuer_type": _or_none(
            _pick(
                record,
                "SECURITY_TYPE",
                "Security_Type",
                "security_type",
                "SECURITY TYPE",
                "Segment",
                "segment",
                "GROUP",
            ).lower()
        ),
        "secured": _to_secured(_pick(record, "SECURED", "Secured", "secured")),
        "listing_status": _to_listing_status(
            _pick(
                record,
                "LISTING_STATUS",
                "Listing_Status",
                "listing_status",
                "Status",
                "status",
            )
        ),
        "maturity": _to_date(
            _pick(
                record,
                "MATURITY_DATE",
                "Maturity_Date",
                "maturity_date",
                "MATURITY",
                "maturity",
            )
        ),
    }
    populated = {name: value for name, value in values.items() if value is not None}
    return FetchResult(
        isin=isin,
        sources={name: SOURCE_NAME for name in populated},
        **populated,
    )


def _map_body(isin, payload):
    if isinstance(payload, bytes):
        payload = payload.decode("utf-8", "replace")
    text = _clean(payload)
    if not text:
        return _failed(isin, FAILURE_MALFORMED)
    if _looks_like_html(text):
        return _failed(isin, FAILURE_BLOCKED)
    try:
        document = json.loads(text)
    except (json.JSONDecodeError, TypeError, ValueError):
        return _failed(isin, FAILURE_PARSE_ERROR)
    records = _records(document)
    if records is None:
        return _failed(isin, FAILURE_MALFORMED)
    record = _find(records, isin)
    if record is None:
        return _failed(isin, FAILURE_NOT_FOUND)
    return _compose(isin, record)


class BseAdapter:
    name = SOURCE_NAME

    def __init__(
        self,
        transport=None,
        timeout=DEFAULT_TIMEOUT,
        url=None,
        segment=BSE_DEBT_SEGMENT,
        status=BSE_ACTIVE_STATUS,
    ):
        self.url = url or BSE_LIST_OF_SCRIP_URL
        self.timeout = timeout
        self.segment = segment
        self.status = status
        self._transport = transport or _no_transport

    def fetch(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return FetchResult(isin=isin, failure_code=FAILURE_INVALID_ISIN)
        url = build_url(self.url, self.segment, self.status)
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
        return self.parse(payload, normalized)

    def parse(self, payload, isin):
        return _map_body(isin, payload)
