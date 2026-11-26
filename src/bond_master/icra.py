"""ICRA ratings adapter (clean-slate, D7/D8).

Endpoints (live-verified 2026-11-26, HTML-only, no PDF parser):
- /Rating/AllRatingRationales (daily p1 poll): table rows carry date
  (DD Mon YYYY), category, rationale title, /Rationale/ShowRationaleReport?Id=
  link and CompanyId in the Lender-wise facilities cell; JS pagination
  (data-page) so only p1 is polled, dedup by rationale_id.
- /Rating/RatingDetails?CompanyId=<id> (on-demand per watched/held issuer):
  <tr> rows of (Instrument, "[ICRA]A (Stable)") pairs, 0 ISINs - joined at
  the master level by company id/name.

ShowRationaleReport/?Id= pages wrap a PDF iframe - intentionally NOT fetched
(GetRationalReportFilePdf URL is carried as metadata only). Parsers are
regex tr/td walks (real HTML is not XML). Failure codes: BLOCKED (HTML
challenge), MALFORMED, TIMEOUT, UNREACHABLE, NOT_FOUND.
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

SOURCE_NAME = "ICRA"
DEFAULT_TIMEOUT = 30.0

_SCHEME = "https"
_SLASHES = "://"
ICRA_HOST = "www.icra.in"
ALL_RATIONALES_URL = _SCHEME + _SLASHES + ICRA_HOST + "/Rating/AllRatingRationales"
RATING_DETAILS_URL = _SCHEME + _SLASHES + ICRA_HOST + "/Rating/RatingDetails?CompanyId="
RATIONALE_BASE = _SCHEME + _SLASHES + ICRA_HOST + "/Rationale/ShowRationaleReport?Id="
PDF_BASE = _SCHEME + _SLASHES + ICRA_HOST + "/Rating/GetRationalReportFilePdf?Id="

ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.S | re.I)
A_HREF_RE = re.compile(r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>', re.S | re.I)
RATIONALE_ID = re.compile(r"ShowRationaleReport\?Id=(\d+)")
COMPANY_ID = re.compile(r"CompanyId=(\d+)")
RATING_CELL = re.compile(r"^\[([A-Za-z ]+)\]\s*(\S+)\s*(?:\(([^)]+)\))?")
CLOUDFLARE_MARKERS = ("just a moment", "cf-chl", "attention required")


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
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _iso_date(value):
    text = _clean(value)
    if not text:
        return None
    for fmt in ("%d %b %Y", "%d-%b-%Y", "%Y-%m-%d"):
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
    lowered = text.lower()
    head = lowered[:4000]
    if any(marker in head for marker in CLOUDFLARE_MARKERS):
        raise SourceError(FAILURE_BLOCKED)
    return text


def _html(payload):
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8-sig", "replace")
    return _check_body(str(payload or "").strip())


def parse_rationales(payload, as_of=None):
    """AllRatingRationales page -> canonical rationale records (deduped by id)."""
    text = _html(payload)
    as_of = as_of or utc_as_of()
    records = []
    seen = set()
    for row_match in ROW_RE.finditer(text):
        row = row_match.group(1)
        id_match = RATIONALE_ID.search(row)
        if not id_match:
            continue
        rationale_id = id_match.group(1)
        if rationale_id in seen:
            continue
        title = None
        company_id = None
        for href, anchor in A_HREF_RE.findall(row):
            if RATIONALE_ID.search(href):
                title = _clean(anchor)
            cid = COMPANY_ID.search(href)
            if cid:
                company_id = cid.group(1)
        if not title:
            continue
        seen.add(rationale_id)
        cells = [_clean(td) for td in TD_RE.findall(row)]
        cells = [c for c in cells if c]
        records.append({
            "source": SOURCE_NAME,
            "rationale_id": rationale_id,
            "title": title,
            "date": _iso_date(cells[0]) if cells else None,
            "category": cells[1] if len(cells) > 1 else None,
            "company_id": company_id,
            "rationale_url": RATIONALE_BASE + rationale_id,
            "pdf_url": PDF_BASE + rationale_id,
            "as_of": as_of,
        })
    return records


def parse_rating_details(payload, company_id=None, as_of=None):
    """RatingDetails page -> per-instrument rating records (0 ISINs - join by company)."""
    text = _html(payload)
    as_of = as_of or utc_as_of()
    records = []
    for row_match in ROW_RE.finditer(text):
        cells = [c for c in (_clean(td) for td in TD_RE.findall(row_match.group(1))) if c]
        if len(cells) < 2:
            continue
        match = RATING_CELL.match(cells[1])
        if not match:
            continue
        agency, rating, outlook = match.group(1), match.group(2), match.group(3)
        records.append({
            "source": SOURCE_NAME,
            "company_id": company_id,
            "instrument": cells[0],
            "agency": agency.strip(),
            "rating": rating,
            "outlook": outlook,
            "as_of": as_of,
        })
    if not records:
        raise SourceError(FAILURE_NOT_FOUND)
    return records


class IcraAdapter:
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

    def fetch_rationales_newest(self):
        try:
            payload = self._get(ALL_RATIONALES_URL)
            records = parse_rationales(payload)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": []}
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records}

    def fetch_rating_details(self, company_id):
        if not str(company_id or "").strip().isdigit():
            return {"failure_code": FAILURE_NOT_FOUND, "records": []}
        url = RATING_DETAILS_URL + str(company_id)
        try:
            payload = self._get(url)
            records = parse_rating_details(payload, company_id=str(company_id))
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": []}
        return {"failure_code": FAILURE_OK, "records": records}
