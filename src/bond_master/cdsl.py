"""CDSL (Central Depository Services India) adapter (clean-slate, D7/D8).

Channels (live-verified 2026-11-26, robots.txt Allow, Cloudflare
Content-Signal use=reference):
- Bulk XLSX (DOWNLOAD, weekly): PreferenceShares_data.xlsx (3,972 rows) and
  securitised_debt_instruments.xlsx (221 rows) under /downloads/CorporateBond/.
  Parsed with stdlib zipfile + ElementTree - zero new dependencies (cells are
  shared strings; dates are DDMMYYYY text, no Excel serials).
- LIGHT per-ISIN (on-demand): popup-isin.aspx (label:value SSR page) and
  CorpBondDatabase.aspx (stable lbl*/txt* span ids + grdRatingDtls table).

Records are D8 canonical JSON (source + as_of). Failure codes: BLOCKED
(Cloudflare challenge / HTML body), MALFORMED (bad zip or missing required
columns), TIMEOUT, UNREACHABLE, NOT_FOUND (unknown ISIN page), INVALID_ISIN.
"""
from __future__ import annotations

import html as html_lib
import io
import re
import zipfile
from xml.etree import ElementTree

from .base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)
from .normalize import normalize_isin

SOURCE_NAME = "CDSL"
DEFAULT_TIMEOUT = 30.0

_SCHEME = "https"
_SLASHES = "://"
CDSL_HOST = "www.cdslindia.com"
PREF_XLSX_URL = (
    _SCHEME + _SLASHES + CDSL_HOST + "/downloads/CorporateBond/PreferenceShares_data.xlsx"
)
SEC_XLSX_URL = (
    _SCHEME + _SLASHES + CDSL_HOST
    + "/downloads/CorporateBond/securitised_debt_instruments.xlsx"
)
POPUP_URL = _SCHEME + _SLASHES + CDSL_HOST + "/investors/popup-isin.aspx?isin_code="
CORPDB_URL = _SCHEME + _SLASHES + CDSL_HOST + "/CorporateBond/CorpBondDatabase.aspx?ISIN="

NS = "{" + "http" + "://" + "schemas.openxmlformats.org/spreadsheetml/2006/main}"

REQUIRED_COLUMNS = ("ISIN", "Issuer Name")
PREF_KNOWN_COLUMNS = frozenset({
    "Issuer Name", "ISIN", "ISIN Description", "ISIN Description ",
    "Issue Amount (ISSUED CAPITAL * par value)", "Face Value", "Date of Issue",
    "Redemption / Date of Maturity", "RTA Agent", "Company Address",
    "Listed/Unlisted",
})
SEC_KNOWN_COLUMNS = frozenset({
    "SECURITY_TYPE", "Issuer Name", "ISIN", "Name of Instrument", "Coupon Rate",
    "ISIN Description long", "Face Value", "Date of Issue",
    "Redemption / Date of Maturity", "RTA Name", "Company Address",
    "Contact Person of the Company", "Remarks", "Remarks on Redemption Date",
})

CLOUDFLARE_MARKERS = ("just a moment", "cf-chl", "challenge-platform", "attention required")
POPUP_MARKER = "ISIN Details"


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def _text(value):
    if value is None:
        return None
    text = str(value).replace("\xa0", " ").strip()
    return text or None


def _safe_float(value):
    text = _text(value)
    if not text:
        return None
    text = text.replace(",", "").replace("%", "").strip()
    try:
        return float(text)
    except ValueError:
        return None


def _iso_date(value):
    text = _text(value)
    if not text or text in ("-", "NA", "N/A"):
        return None
    match = re.fullmatch(r"(\d{2})(\d{2})(\d{4})", text)
    if match:
        day, month, year = match.groups()
        return f"{year}-{month}-{day}"
    match = re.fullmatch(r"(\d{1,2})-([A-Za-z]{3})-(\d{4})", text)
    if match:
        day, mon, year = match.groups()
        months = {
            "jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05",
            "jun": "06", "jul": "07", "aug": "08", "sep": "09", "oct": "10",
            "nov": "11", "dec": "12",
        }
        month = months.get(mon.lower())
        if month:
            return f"{year}-{month}-{int(day):02d}"
    return None


def _listing(value):
    text = (_text(value) or "").lower()
    if text == "listed":
        return "listed"
    if text == "unlisted":
        return "unlisted"
    return "unknown"


def _column_letter(ref):
    match = re.match(r"([A-Z]+)", ref or "")
    return match.group(1) if match else None


def _load_shared_strings(zf):
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ElementTree.fromstring(zf.read("xl/sharedStrings.xml"))
    values = []
    for si in root.findall(f"{NS}si"):
        values.append("".join(t.text or "" for t in si.iter(f"{NS}t")))
    return values


def _first_sheet_path(zf):
    names = zf.namelist()
    if "xl/worksheets/sheet1.xml" in names:
        return "xl/worksheets/sheet1.xml"
    sheets = sorted(n for n in names if n.startswith("xl/worksheets/") and n.endswith(".xml"))
    if sheets:
        return sheets[0]
    raise SourceError(FAILURE_MALFORMED)


def parse_xlsx(payload, known_columns, drift=None):
    """Parse a CDSL bulk XLSX into header-keyed row dicts.

    Fails loudly: HTML bodies -> BLOCKED, non-zip -> MALFORMED, missing
    required columns -> MALFORMED. Unknown headers append to drift.
    """
    drift = [] if drift is None else drift
    if isinstance(payload, str):
        payload = payload.encode("utf-8", "replace")
    if not payload:
        raise SourceError(FAILURE_MALFORMED)
    if payload[:2] != b"PK":
        text = payload[:200].decode("utf-8", "replace").lstrip().lower()
        if text.startswith("<!doctype") or text.startswith("<html") or text.startswith("<?xml"):
            raise SourceError(FAILURE_BLOCKED)
        raise SourceError(FAILURE_MALFORMED)
    try:
        zf = zipfile.ZipFile(io.BytesIO(payload))
        shared = _load_shared_strings(zf)
        root = ElementTree.fromstring(zf.read(_first_sheet_path(zf)))
    except SourceError:
        raise
    except Exception:
        raise SourceError(FAILURE_MALFORMED)
    rows = []
    header = None
    for row_el in root.iter(f"{NS}row"):
        cells = {}
        for cell in row_el.findall(f"{NS}c"):
            col = _column_letter(cell.get("r"))
            if not col:
                continue
            cell_type = cell.get("t")
            value_el = cell.find(f"{NS}v")
            if cell_type == "inlineStr":
                inline = cell.find(f"{NS}is")
                value = "".join(t.text or "" for t in inline.iter(f"{NS}t")) if inline is not None else None
            elif value_el is None or value_el.text is None:
                continue
            elif cell_type == "s":
                try:
                    value = shared[int(value_el.text)]
                except (ValueError, IndexError):
                    raise SourceError(FAILURE_MALFORMED)
            else:
                value = value_el.text
            cells[col] = value
        if header is None:
            header = {col: _text(val) for col, val in cells.items()}
            missing = [c for c in REQUIRED_COLUMNS if c not in header.values()]
            if missing:
                raise SourceError(FAILURE_MALFORMED)
            for name in header.values():
                if name and name not in known_columns and name not in drift:
                    drift.append(name)
            continue
        row = {}
        for col, head in header.items():
            if head:
                row[head] = cells.get(col)
        rows.append(row)
    if header is None:
        raise SourceError(FAILURE_MALFORMED)
    return rows


def to_pref_record(row, as_of=None):
    as_of = as_of or utc_as_of()
    return {
        "isin": _text(row.get("ISIN")),
        "company": _text(row.get("Issuer Name")),
        "description": _text(row.get("ISIN Description ") or row.get("ISIN Description")),
        "security_type": "Preference Shares",
        "issue_amount": _safe_float(row.get("Issue Amount (ISSUED CAPITAL * par value)")),
        "face_value": _safe_float(row.get("Face Value")),
        "issue_date": _iso_date(row.get("Date of Issue")),
        "maturity": _iso_date(row.get("Redemption / Date of Maturity")),
        "rta": _text(row.get("RTA Agent")),
        "address": _text(row.get("Company Address")),
        "listing_status": _listing(row.get("Listed/Unlisted")),
        "source": SOURCE_NAME,
        "as_of": as_of,
    }


def to_sec_record(row, as_of=None):
    as_of = as_of or utc_as_of()
    return {
        "isin": _text(row.get("ISIN")),
        "company": _text(row.get("Issuer Name")),
        "security_type": _text(row.get("SECURITY_TYPE")),
        "instrument": _text(row.get("Name of Instrument")),
        "coupon": _safe_float(row.get("Coupon Rate")),
        "description": _text(row.get("ISIN Description long")),
        "face_value": _safe_float(row.get("Face Value")),
        "issue_date": _iso_date(row.get("Date of Issue")),
        "maturity": _iso_date(row.get("Redemption / Date of Maturity")),
        "rta": _text(row.get("RTA Name")),
        "address": _text(row.get("Company Address")),
        "contact": _text(row.get("Contact Person of the Company")),
        "remarks": _text(row.get("Remarks")),
        "remarks_redemption": _text(row.get("Remarks on Redemption Date")),
        "listing_status": None,
        "source": SOURCE_NAME,
        "as_of": as_of,
    }


def _strip_html(html_text):
    text = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html_text, flags=re.S | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&#160;", " ")
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _between(text, start, ends):
    index = text.find(start)
    if index < 0:
        return None
    index += len(start)
    stop = len(text)
    for end in ends:
        pos = text.find(end, index)
        if pos >= 0:
            stop = min(stop, pos)
    return text[index:stop].strip() or None


def parse_popup(body):
    """popup-isin.aspx -> field dict, or SourceError(NOT_FOUND/BLOCKED/MALFORMED)."""
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    text = _strip_html(str(body or ""))
    if not text:
        raise SourceError(FAILURE_MALFORMED)
    has_content = POPUP_MARKER in text or "ISIN:" in text
    if not has_content:
        lowered = text.lower()
        if any(marker in lowered for marker in CLOUDFLARE_MARKERS):
            raise SourceError(FAILURE_BLOCKED)
        raise SourceError(FAILURE_NOT_FOUND)
    isin = _between(text, "ISIN:", ["ISIN Description:"])
    if not isin or not normalize_isin(isin.split()[0]):
        raise SourceError(FAILURE_NOT_FOUND)
    paid_up = _between(text, "Paid up value:", ["ISIN Price"])
    return {
        "isin": isin.split()[0],
        "description": _between(text, "ISIN Description:", ["ISIN Short Name:"]),
        "short_name": _between(text, "ISIN Short Name:", ["Security Type Description:"]),
        "security_type": _between(text, "Security Type Description:", ["ISIN Status:"]),
        "isin_status": _between(text, "ISIN Status:", ["ISIN Listing status:"]),
        "listing_status": _listing(_between(text, "ISIN Listing status:", ["Paid up value:"])),
        "paid_up_value": _safe_float(paid_up),
        "address": _between(text, "Address:", ["Tel."]),
        "rta": _between(text, "RTA - Physical (Name & Address):", ["RTA - Demat"]),
    }


def _span(html_text, span_id):
    match = re.search(r'id="%s"[^>]*>([^<]*)</span>' % re.escape(span_id), html_text)
    return _text(match.group(1)) if match else None


def _parse_rating_table(html_text):
    index = html_text.find('id="grdRatingDtls"')
    if index < 0:
        return []
    end = html_text.find("</table>", index)
    table = html_text[index:end if end > 0 else len(html_text)]
    ratings = []
    for row_html in re.findall(r"<tr[^>]*>(.*?)</tr>", table, flags=re.S):
        cells = [
            _text(re.sub(r"<[^>]+>", "", cell).replace("&nbsp;", " "))
            for cell in re.findall(r"<td[^>]*>(.*?)</td>", row_html, flags=re.S)
        ]
        if len(cells) >= 2 and cells[0] and cells[1]:
            rating = cells[1]
            outlook = None
            if " /" in rating:
                rating, _, outlook = rating.partition(" /")
                rating = rating.strip()
                outlook = outlook.strip() or None
            if not outlook and len(cells) > 2 and cells[2]:
                outlook = cells[2]
            ratings.append({
                "agency": cells[0],
                "rating": rating,
                "outlook": outlook,
                "action": cells[3] if len(cells) > 3 else None,
                "watch": cells[4] if len(cells) > 4 else None,
                "rating_date": _iso_date(cells[5]) if len(cells) > 5 else None,
                "status": cells[6] if len(cells) > 6 else None,
            })
    return ratings


def parse_corpdb(body):
    """CorpBondDatabase.aspx -> field dict, or SourceError(NOT_FOUND/BLOCKED/MALFORMED)."""
    if isinstance(body, (bytes, bytearray)):
        body = body.decode("utf-8", "replace")
    html_text = str(body or "")
    if not html_text.strip():
        raise SourceError(FAILURE_MALFORMED)
    issuer = _span(html_text, "txtIssuerName")
    if not issuer:
        lowered = html_text.lower()
        if any(marker in lowered for marker in CLOUDFLARE_MARKERS):
            raise SourceError(FAILURE_BLOCKED)
        if "asp.net" in lowered or "<html" in lowered:
            raise SourceError(FAILURE_NOT_FOUND)
        raise SourceError(FAILURE_MALFORMED)
    ratings = _parse_rating_table(html_text)
    latest = None
    dated = [r for r in ratings if r.get("rating_date")]
    if dated:
        latest = max(dated, key=lambda r: r["rating_date"])
    elif ratings:
        latest = ratings[0]
    return {
        "company": issuer,
        "face_value": _safe_float(_span(html_text, "lblFaceValue")),
        "coupon": _safe_float(_span(html_text, "lblCouponRate")),
        "coupon_basis": _span(html_text, "lblCouponBasis"),
        "coupon_type": _span(html_text, "lblCouponType"),
        "redemption_date": _iso_date(_span(html_text, "lblRedmDate")),
        "issue_size": _safe_float(_span(html_text, "lblIssueSize")),
        "issue_price": _safe_float(_span(html_text, "lblIssuePrice")),
        "rating_status": _span(html_text, "lblRatingStatus"),
        "rating": latest["rating"] if latest else None,
        "rating_agency": latest["agency"] if latest else None,
        "rating_date": latest["rating_date"] if latest else None,
        "outlook": latest.get("outlook") if latest else None,
        "ratings": ratings,
    }


class CdslAdapter:
    """Bulk XLSX catalog source + on-demand per-ISIN detail (D7/D8)."""

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

    def fetch_preference_shares(self):
        drift = []
        try:
            payload = self._get(PREF_XLSX_URL)
            rows = parse_xlsx(payload, PREF_KNOWN_COLUMNS, drift=drift)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "drift": drift}
        as_of = utc_as_of()
        records = [to_pref_record(row, as_of=as_of) for row in rows]
        records = [r for r in records if r["isin"] and normalize_isin(r["isin"])]
        return {"failure_code": FAILURE_OK, "records": records, "drift": drift}

    def fetch_securitised(self):
        drift = []
        try:
            payload = self._get(SEC_XLSX_URL)
            rows = parse_xlsx(payload, SEC_KNOWN_COLUMNS, drift=drift)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "drift": drift}
        as_of = utc_as_of()
        records = [to_sec_record(row, as_of=as_of) for row in rows]
        records = [r for r in records if r["isin"] and normalize_isin(r["isin"])]
        return {"failure_code": FAILURE_OK, "records": records, "drift": drift}

    def fetch_isin_detail(self, isin):
        norm = normalize_isin(isin)
        if not norm:
            return {"failure_code": FAILURE_INVALID_ISIN, "record": None}
        try:
            popup_body = self._get(POPUP_URL + norm)
            popup = parse_popup(popup_body)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "record": None}
        try:
            corp_body = self._get(CORPDB_URL + norm)
            corp = parse_corpdb(corp_body)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "record": None}
        record = {
            "isin": norm,
            "source": SOURCE_NAME,
            "as_of": utc_as_of(),
            **popup,
            **corp,
        }
        record["isin"] = norm
        return {"failure_code": FAILURE_OK, "record": record}
