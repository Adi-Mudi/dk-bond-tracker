"""NSE Wholesale Debt Market (WDM) securities-master adapter (clean-slate, D7/D8).

Discovery: GET /api/daily-reports?key=WDM (plain stdlib - no Akamai wall on
this endpoint, verified live) -> JSON file listing with the official
nsearchives.nseindia.IN URL for wdmlist_<date>.csv. Download the CSV
(UTF-8 with BOM, ~1.2 MB, ~10.6k securities) and emit canonical JSON
records (D8): one per security row.

Emits the fields NSDL/BSE lack: coupon parsed from issue_name, issue_date,
maturity, last/next interest-payment dates, coupon frequency, last traded
price/date - the payout-critical data for UF-W2/UF-P/UF-D.
"""
from __future__ import annotations

import csv
import io
import json
import re

from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)

SOURCE_NAME = "NSE WDM"
DEFAULT_TIMEOUT = 30.0

REPORTS_API = "https" + "://" + "www.nseindia.com" + "/api/daily-reports?key=WDM"
ARCHIVES_BASE = "https" + "://" + "nsearchives.nseindia.in" + "/"
FILE_KEY = "WDM-SEC-AVAILABLE-FOR-TRADE"

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https" + "://" + "www.nseindia.com" + "/",
}


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def _to_float(value):
    text = str(value or "").strip().replace(",", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _clean(value):
    return str(value or "").strip() or None


def _parse_coupon(issue_name):
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", str(issue_name or ""))
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def parse_wdm_csv(payload):
    """Parse the wdmlist CSV body into canonical records.

    Fails loudly on: HTML bodies (BLOCKED), empty bodies (MALFORMED),
    missing the ISIN column (MALFORMED - schema drift).
    """
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8-sig", "replace")
    text = str(payload).lstrip("\ufeff").strip()
    if not text:
        raise SourceError(FAILURE_MALFORMED)
    if text[:1] == "<":
        raise SourceError(FAILURE_BLOCKED)
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames or "ISIN NO." not in [f.strip() for f in reader.fieldnames]:
        raise SourceError(FAILURE_MALFORMED)
    records = []
    seen = set()
    as_of = utc_as_of()
    for row in reader:
        isin = (row.get("ISIN NO.") or "").strip()
        if not isin or isin in seen:
            continue
        seen.add(isin)
        issue_name = _clean(row.get("ISSUE_NAME"))
        records.append({
            "isin": isin,
            "security": _clean(row.get("SECURITY")),
            "security_type": _clean(row.get("SECTYPE")),
            "issue_name": issue_name,
            "issue_desc": _clean(row.get("ISSUE_DESC")),
            "issue_date": _clean(row.get("ISSUE_DATE")),
            "maturity": _clean(row.get("MAT_DATE")),
            "coupon": _parse_coupon(issue_name),
            "last_ip_date": _clean(row.get("Last IP Dt")),
            "next_ip_date": _clean(row.get("Next IP Dt")),
            "coupon_frequency": _clean(row.get("Cpn Freq")),
            "last_traded_price": _to_float(row.get("Last Traded Price (in Rs.)")),
            "last_traded_date": _clean(row.get("Last Traded Date")),
            "status": _clean(row.get("STATUS")),
            "source": SOURCE_NAME,
            "as_of": as_of,
        })
    return records


class NseWdmAdapter:
    """Bulk catalog source for the NSE WDM securities master (D7/D8)."""

    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT, reports_url=REPORTS_API):
        self._transport = transport or _no_transport
        self.timeout = timeout
        self.reports_url = reports_url

    def fetch_latest_catalog(self):
        """Two GETs: file listing -> CSV download. Returns D8 canonical records."""
        try:
            payload = self._transport(self.reports_url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": [], "source_url": None}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "source_url": None}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "source_url": None}
        text = payload.decode("utf-8-sig", "replace") if isinstance(payload, (bytes, bytearray)) else str(payload)
        try:
            listing = json.loads(text)
        except json.JSONDecodeError:
            return {"failure_code": FAILURE_BLOCKED, "records": [], "source_url": None}
        entries = listing.get("PreviousDay") or listing.get("CurrentDay") or []
        target = None
        for entry in entries:
            if entry.get("fileKey") == FILE_KEY:
                target = entry
                break
        if not target:
            return {"failure_code": FAILURE_NOT_FOUND, "records": [], "source_url": None}
        csv_url = (target.get("filePath") or "").rstrip("/") + "/" + target.get("fileActlName", "")
        try:
            csv_payload = self._transport(csv_url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": [], "source_url": csv_url}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "source_url": csv_url}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "source_url": csv_url}
        try:
            records = parse_wdm_csv(csv_payload)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "source_url": csv_url}
        return {"failure_code": FAILURE_OK, "records": records, "source_url": csv_url}


