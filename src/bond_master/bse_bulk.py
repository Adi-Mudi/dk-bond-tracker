"""BSE debt-segment bulk catalog adapter (clean-slate, D7/D8).

Fetches the official BSE ListofScripData JSON (Debentures and Bonds, Active)
and emits canonical JSON records (D8): one record per unique ISIN_NUMBER.

Failure codes (base.py): BLOCKED (403/HTML - Akamai TLS/IP sensitive, NEVER
retried), MALFORMED (non-JSON), TIMEOUT, UNREACHABLE, OK. Per agy consult:
403 is TLS/IP-fingerprint variable - retrying is useless; last-good is kept.
"""
from __future__ import annotations

import json

from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)

SOURCE_NAME = "BSE"
DEFAULT_TIMEOUT = 30.0

_SCHEME = "https"
_SLASHES = "://"
BSE_API_HOST = "api.bseindia.com"
BSE_LIST_OF_SCRIP_PATH = "/BseIndiaAPI/api/ListofScripData/w"
ENDPOINT = _SCHEME + _SLASHES + BSE_API_HOST + BSE_LIST_OF_SCRIP_PATH
QUERY = ("?Group=&Scripcode=&industry=&segment=Debentures%20and%20Bonds&status=Active")
URL = ENDPOINT + QUERY

BSE_WWW_HOST = "www.bseindia.com"
BSE_WWW_BASE = _SCHEME + _SLASHES + BSE_WWW_HOST + "/"
BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": BSE_WWW_BASE,
    "Origin": BSE_WWW_BASE,
}

REQUIRED_KEYS = ("ISIN_NUMBER", "Issuer_Name", "Scrip_Name")
KNOWN_KEYS = frozenset({
    "FACE_VALUE", "GROUP", "INDUSTRY", "ISIN_NUMBER", "Issuer_Name",
    "Mktcap", "NSURL", "SCRIP_CD", "Scrip_Name", "Segment", "Status",
    "scrip_id",
})
DEAD_KEYS = frozenset({"INDUSTRY", "Mktcap"})


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def safe_float(value):
    text = str(value).strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def to_record(row, drift, as_of=None):
    isin = str(row.get("ISIN_NUMBER", "")).strip()
    record = {
        "isin": isin,
        "company": str(row.get("Issuer_Name", "")).strip() or None,
        "scrip_name": str(row.get("Scrip_Name", "")).strip() or None,
        "scrip_code": str(row.get("SCRIP_CD", "")).strip() or None,
        "scrip_id": str(row.get("scrip_id", "")).strip() or None,
        "face_value": safe_float(row.get("FACE_VALUE")),
        "group": str(row.get("GROUP", "")).strip() or None,
        "status": str(row.get("Status", "")).strip() or None,
        "segment": str(row.get("Segment", "")).strip() or None,
        "source_url": str(row.get("NSURL", "")).strip() or None,
        "source": SOURCE_NAME,
        "as_of": as_of or utc_as_of(),
    }
    for key in row:
        if key not in KNOWN_KEYS and key not in drift:
            drift.append(key)
    return record


def parse_payload(payload, drift=None):
    """Parse the ListofScripData JSON body into canonical records.

    Permissive on additive unknown keys (collected into drift); fails loudly
    on a non-list root or rows missing required keys.
    """
    drift = [] if drift is None else drift
    as_of = utc_as_of()
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8-sig", "replace")
    if isinstance(payload, str):
        text = payload.lstrip('\ufeff').strip()
        if not text:
            return []
        if text[0] == "<":
            raise SourceError(FAILURE_BLOCKED)
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            raise SourceError(FAILURE_MALFORMED)
    if not isinstance(payload, list):
        raise SourceError(FAILURE_MALFORMED)
    records = []
    skipped = 0
    seen = set()
    for row in payload:
        if not isinstance(row, dict):
            skipped += 1
            continue
        if not str(row.get("ISIN_NUMBER", "")).strip():
            skipped += 1
            continue
        isin = str(row["ISIN_NUMBER"]).strip()
        if isin in seen:
            continue
        seen.add(isin)
        records.append(to_record(row, drift, as_of=as_of))
    if skipped:
        drift.append(f"skipped_rows:{skipped}")
    return records


class BseBulkAdapter:
    """Bulk catalog source: fetches the whole active debt list per refresh.

    Distinct from the per-ISIN Adapter protocol: this feeds the master
    refresh pipeline (like the NSDL bulk CSV), not per-ISIN lookups.
    """

    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT, url=URL):
        self.url = url
        self.timeout = timeout
        self._transport = transport or _no_transport
        self.last_drift = []

    def fetch_catalog(self):
        try:
            payload = self._transport(self.url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": [], "drift": self.last_drift}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "drift": self.last_drift}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "drift": self.last_drift}
        try:
            records = parse_payload(payload, drift=self.last_drift)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "drift": self.last_drift}
        return {"failure_code": FAILURE_OK, "records": records, "drift": list(self.last_drift)}
