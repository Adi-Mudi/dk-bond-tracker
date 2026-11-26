"""Acuité Ratings adapter (clean-slate, D7/D8) - final module of the 11-source wave.

Endpoints (live-verified 2026-11-26, connect.acuite.in):
- /liveratings (daily p1 poll): 20 accordion rows/page - tr id = master_id,
  Date ("26th Nov 26"), entity anchor -> fcompany-details/<SLUG>/<DATE>.
  No rating/instrument in the list row; dedup/stop key = master_id.
- /fcompany-details/<SLUG>/<DATE> (on-demand per listed entity): ratings
  table (Product | Quantum SEBI | Quantum Other FSR | Long Term Rating |
  Short Term Rating | Regulated By); rating cells split on "|" into
  rating/action/flag. ISIN lender table parsed when present (0 ISINs on
  some entities - join by company + instrument at master level).

The 6.7MB sitemap.xml is NOT polled: live probe shows Last-Modified 2025-08
and broken non-XML head - stale. Failure codes: BLOCKED, MALFORMED,
TIMEOUT, UNREACHABLE, NOT_FOUND.
"""
from __future__ import annotations

import html as html_lib
import re
from datetime import datetime

from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)

SOURCE_NAME = "Acuite"
DEFAULT_TIMEOUT = 30.0

_SCHEME = "https"
_SLASHES = "://"
ACUITE_HOST = "connect.acuite.in"
LIVERATINGS_URL = _SCHEME + _SLASHES + ACUITE_HOST + "/liveratings"
DETAILS_BASE = _SCHEME + _SLASHES + ACUITE_HOST + "/fcompany-details/"

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
TR_OPEN_RE = re.compile(r"<tr[^>]*>", re.S | re.I)
CELL_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)
LINK_RE = re.compile(r'<a[^>]*href="([^"]*fcompany-details[^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
MASTER_ID_RE = re.compile(r'\bid="(\d+)"')
COMPANY_ATTR_RE = re.compile(r'data-company="(\d+)"')
PR_DATE_RE = re.compile(r"<b>Press Release</b>.*?<b>([^<]+)</b>", re.S | re.I)
TITLE_RE = re.compile(r"<title>([^<]+)</title>", re.S | re.I)
DATE_CELL = re.compile(r'<th[^>]*class="[^"]*td-date[^"]*"[^>]*>(.*?)</th>', re.S | re.I)
ISIN_CELL = re.compile(r"\b([A-Z]{2}[A-Z0-9]{9}[0-9])\b")
CLOUDFLARE_MARKERS = ("just a moment", "cf-chl", "attention required")
ORDINAL_RE = re.compile(r"(\d{1,2})(?:st|nd|rd|th)\b", re.I)


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def _clean(text):
    if text is None:
        return None
    text = html_lib.unescape(str(text))
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ").replace("\xad", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _safe_float(value):
    text = _clean(value)
    if not text or text in ("-", "NA", "N/A"):
        return None
    text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def _iso_date(value):
    text = _clean(value)
    if not text:
        return None
    text = ORDINAL_RE.sub(r"\1", text)
    text = re.sub(r"\s+", " ", text).strip()
    for fmt in ("%d %b %y", "%d %b %Y", "%d-%b-%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _check_body(text):
    if not text:
        raise SourceError(FAILURE_MALFORMED)
    if text[:1] != "<" and "<" not in text[:200]:
        raise SourceError(FAILURE_MALFORMED)
    head = text.lower()[:4000]
    if any(marker in head for marker in CLOUDFLARE_MARKERS):
        raise SourceError(FAILURE_BLOCKED)
    return text


def _html(payload):
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8-sig", "replace")
    return _check_body(str(payload or "").strip())


def _split_rating_cell(value):
    text = _clean(value)
    if not text or text == "-":
        return None, None, None
    parts = [p.strip() for p in text.split("|")]
    rating = parts[0] or None
    action = parts[1] if len(parts) > 1 and parts[1] else None
    flag = " | ".join(parts[2:]) if len(parts) > 2 else None
    return rating, action, flag


def parse_liveratings(payload, as_of=None):
    """liveratings p1 -> list records keyed by master_id (tr id)."""
    text = _html(payload)
    as_of = as_of or utc_as_of()
    records = []
    seen = set()
    for row_match in ROW_RE.finditer(text):
        row = row_match.group(1)
        tr_open = TR_OPEN_RE.search(row_match.group(0))
        if not tr_open or "accordion-toggle" not in tr_open.group(0):
            continue
        id_match = MASTER_ID_RE.search(tr_open.group(0))
        if not id_match:
            continue
        master_id = id_match.group(1)
        if master_id in seen:
            continue
        date_match = DATE_CELL.search(row)
        link_match = LINK_RE.search(row)
        if not date_match or not link_match:
            continue
        href, anchor = link_match.group(1), _clean(link_match.group(2))
        if not anchor:
            continue
        seen.add(master_id)
        slug_match = re.search(r"fcompany-details/([^/]+)/", href)
        company_match = COMPANY_ATTR_RE.search(row)
        records.append({
            "source": SOURCE_NAME,
            "master_id": master_id,
            "company_id": company_match.group(1) if company_match else None,
            "date": _iso_date(date_match.group(1)),
            "entity": anchor,
            "entity_slug": slug_match.group(1) if slug_match else None,
            "detail_url": href,
            "as_of": as_of,
        })
    return records


def parse_company_details(payload, as_of=None):
    """fcompany-details page -> per-product rating records (+ ISIN rows when present)."""
    text = _html(payload)
    as_of = as_of or utc_as_of()
    company = None
    title_match = TITLE_RE.search(text)
    if title_match:
        company = _clean(title_match.group(1).split(" - ")[0]) or None
    rating_date = None
    pr_match = PR_DATE_RE.search(text)
    if pr_match:
        rating_date = _iso_date(pr_match.group(1))
    records = []
    isin_records = []
    for row_match in ROW_RE.finditer(text):
        cells = [c for c in (_clean(td) for td in CELL_RE.findall(row_match.group(1))) if c]
        if len(cells) >= 6 and _safe_float(cells[1]) is not None and _safe_float(cells[2]) is not None:
            long_rating, long_action, long_flag = _split_rating_cell(cells[3])
            short_rating, short_action, short_flag = _split_rating_cell(cells[4])
            records.append({
                "source": SOURCE_NAME,
                "company": company,
                "isin": None,
                "instrument": cells[0],
                "quantum_sebi": _safe_float(cells[1]),
                "quantum_other": _safe_float(cells[2]),
                "long_term_rating": long_rating,
                "long_term_action": long_action,
                "long_term_flag": long_flag,
                "short_term_rating": short_rating,
                "short_term_action": short_action,
                "short_term_flag": short_flag,
                "regulated_by": cells[5],
                "rating_date": rating_date,
                "as_of": as_of,
            })
            continue
        if len(cells) >= 2 and cells[0] and ISIN_CELL.fullmatch(cells[1]):
            isin_records.append({
                "source": SOURCE_NAME,
                "company": company,
                "lender": cells[0],
                "isin": cells[1],
                "facility": cells[2] if len(cells) > 2 else None,
                "listing_status": cells[3] if len(cells) > 3 else None,
                "regulated_by": cells[4] if len(cells) > 4 else None,
                "date_of_issuance": _iso_date(cells[5]) if len(cells) > 5 else None,
                "coupon": _safe_float(cells[6]) if len(cells) > 6 else None,
                "as_of": as_of,
            })
    if not records and not isin_records:
        raise SourceError(FAILURE_NOT_FOUND)
    return records, isin_records


class AcuiteAdapter:
    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT):
        self._transport = transport or _no_transport
        self.timeout = timeout

    def _get(self, url):
        try:
            return self._transport(url, self.timeout)
        except TimeoutError:
            raise SourceError(FAILURE_TIMEOUT)
        except ConnectionError:
            raise SourceError(FAILURE_UNREACHABLE)
        except SourceError:
            raise
        except Exception:
            raise SourceError(FAILURE_UNREACHABLE)

    def fetch_liveratings_newest(self):
        try:
            payload = self._get(LIVERATINGS_URL)
            records = parse_liveratings(payload)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": []}
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records}

    def fetch_company_details(self, detail_url):
        url = str(detail_url or "").strip()
        if not url.startswith(DETAILS_BASE):
            return {"failure_code": FAILURE_NOT_FOUND, "records": [], "isin_records": []}
        try:
            payload = self._get(url)
            records, isin_records = parse_company_details(payload)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "isin_records": []}
        for record in records:
            record["rationale_url"] = url
        return {"failure_code": FAILURE_OK, "records": records, "isin_records": isin_records}
