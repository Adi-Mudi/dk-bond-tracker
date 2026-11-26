"""CRISIL ratings adapter (clean-slate, D7/D8).

Sources (verified live 2026-11-26):
- RR listing servlet: cmd=RR&start&limit -> {docs[], numFound} (39,849 total);
  docs carry companyCode, companyName, industryName, heading, ratingDate,
  ratingFileName, prId, transDate. RatingDocs HTML is fetched ON-DEMAND only
  (never bulk: 39k x 93KB).
- DR endpoint: returns ONLY the ~352 CRISIL-D default list and IGNORES
  isinNumber (params q=*:*) - used solely as the default-watch list.
- By-ISIN path: our ISIN->company masters + company-name matching against
  RR headings (the AEM query param does not filter by ISIN - verified).

Rate discipline (robots.txt + agy consult): identified UA, 1 req / 1.5-2s
with jitter at the caller, 0 retries on 403 (Akamai variance proven - same
headers returned 200 and 403 from different clients same day), exponential
backoff on 429/5xx at the caller. Session cookie preservation left to the
transport (urllib opener with cookie jar when needed).
"""
from __future__ import annotations

import json
import re

from .transport import percent_encode
from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)

SOURCE_NAME = "CRISIL"
DEFAULT_TIMEOUT = 30.0
_BASE = "https" + "://" + "www.crisilratings.com"
LISTING_SERVLET = _BASE + "/bin/crisil/listing/rating_sme_listing_service.json"
RATING_DOCS_BASE = _BASE + "/mnt/winshare/Ratings/RatingList/RatingDocs/"
NEWEST_PAGE_LIMIT = 200

REQUIRED_RR_KEYS = ("companyName", "ratingDate", "heading")
KNOWN_RR_KEYS = frozenset({
    "abstractTemp", "companyCode", "companyName", "heading", "industryName",
    "prId", "ratingDate", "ratingFileName", "showAbstarct", "transDate",
})


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def _parse_date(value):
    """CRISIL dates arrive in multiple formats: 'Nov 25, 2026', 'June 8, 2017'."""
    text = str(value or "").strip()
    for fmt in ("%b %d, %Y", "%B %d, %Y", "%d-%b-%Y", "%Y-%m-%d"):
        try:
            import datetime
            return datetime.datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def rr_record(doc, drift):
    for key in doc:
        if key not in KNOWN_RR_KEYS and key not in drift:
            drift.append(key)
    rating_file = str(doc.get("ratingFileName", "")).strip()
    return {
        "company_code": str(doc.get("companyCode", "")).strip() or None,
        "company": str(doc.get("companyName", "")).strip() or None,
        "industry": str(doc.get("industryName", "")).strip() or None,
        "heading": str(doc.get("heading", "")).strip() or None,
        "rating_date": _parse_date(doc.get("ratingDate")),
        "rating_file": rating_file or None,
        "rationale_url": RATING_DOCS_BASE + percent_encode(rating_file) if rating_file else None,
        "trans_date": _parse_date(doc.get("transDate")),
        "pr_id": doc.get("prId"),
        "source": SOURCE_NAME,
    }


class CrisilAdapter:
    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT):
        self._transport = transport or _no_transport
        self.timeout = timeout

    def _get_json(self, url):
        payload = self._transport(url, self.timeout)
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8-sig", "replace")
        if isinstance(payload, (dict, list)):
            return payload
        text = str(payload).strip()
        if not text:
            raise SourceError(FAILURE_MALFORMED)
        if text[0] == "<":
            raise SourceError(FAILURE_BLOCKED)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            raise SourceError(FAILURE_MALFORMED)

    def fetch_rr_newest(self, watermark_trans_date=None, limit=NEWEST_PAGE_LIMIT):
        """Poll newest RR pages until transDate falls below the watermark.

        watermark_trans_date: ISO date string (from the last successful poll);
        None = fetch only the first page. Returns canonical records, deduped
        by prId, oldest-last.
        """
        records = []
        drift = []
        seen_pr = set()
        start = 0
        while True:
            url = f"{LISTING_SERVLET}?cmd=RR&start={start}&limit={limit}"
            try:
                data = self._get_json(url)
            except SourceError as exc:
                return {"failure_code": exc.failure_code, "records": records, "drift": drift}
            except TimeoutError:
                return {"failure_code": FAILURE_TIMEOUT, "records": records, "drift": drift}
            except ConnectionError:
                return {"failure_code": FAILURE_UNREACHABLE, "records": records, "drift": drift}
            except Exception:
                return {"failure_code": FAILURE_UNREACHABLE, "records": records, "drift": drift}
            docs = data.get("docs", [])
            if not isinstance(docs, list):
                return {"failure_code": FAILURE_MALFORMED, "records": records, "drift": drift}
            reached_watermark = False
            for doc in docs:
                record = rr_record(doc, drift)
                pr = record["pr_id"]
                if pr in seen_pr:
                    continue
                seen_pr.add(pr)
                if watermark_trans_date and (record["trans_date"] or "") < watermark_trans_date:
                    reached_watermark = True
                    continue
                records.append(record)
            if len(docs) < limit or reached_watermark:
                break
            start += limit
        records.sort(key=lambda r: (r["trans_date"] or "", r["pr_id"] or 0))
        return {"failure_code": FAILURE_OK, "records": records, "drift": drift}

    def fetch_default_watch(self, limit=500):
        """DR endpoint: the ~352-doc CRISIL-D default list (ignores ISIN params)."""
        url = f"{LISTING_SERVLET}?cmd=DR&start=0&limit={limit}"
        try:
            data = self._get_json(url)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "drift": []}
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": [], "drift": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "drift": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "drift": []}
        docs = data.get("response", {}).get("docs", [])
        if not isinstance(docs, list):
            return {"failure_code": FAILURE_MALFORMED, "records": [], "drift": []}
        records = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            records.append({
                "company_code": str(doc.get("companyCode", "")).strip() or None,
                "company": str(doc.get("companyName", "")).strip() or None,
                "instrument": str(doc.get("instrument", "")).strip() or None,
                "isin": str(doc.get("isinNumber", "")).strip() or None,
                "due_date": str(doc.get("dueDate", "")).strip() or None,
                "rating": str(doc.get("rating", "")).strip() or None,
                "rr_date": _parse_date(doc.get("rrDate")),
                "source": SOURCE_NAME,
            })
        return {"failure_code": FAILURE_OK, "records": records, "drift": []}

    def fetch_rationale(self, rating_filename):
        """ON-DEMAND: fetch one rationale HTML document (raw, unparsed).

        Never bulk: 39k docs x ~93KB each. Call only for matched watched/held
        bonds. Returns the raw HTML for the raw store.
        """
        name = percent_encode(str(rating_filename))
        url = RATING_DOCS_BASE + name
        try:
            payload = self._transport(url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "html": None}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "html": None}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "html": None}
        if isinstance(payload, (bytes, bytearray)):
            payload = payload.decode("utf-8", "replace")
        text = str(payload).strip()
        if text[:1] == "<" and "<html" in text[:500].lower():
            return {"failure_code": FAILURE_OK, "html": text, "source_url": url}
        return {"failure_code": FAILURE_BLOCKED, "html": None}

    def match_by_company(self, company, rr_page_limit=500):
        """By-ISIN path for AAA..BBB-: match our company name against RR
        headings (cmd=DR ignores isinNumber and holds only D-rated docs).
        Client-side substring match, both directions, casefolded."""
        if not company:
            return {"failure_code": FAILURE_NOT_FOUND, "records": [], "drift": []}
        needle = re.sub(r"\s+", " ", company).casefold()
        url = f"{LISTING_SERVLET}?cmd=RR&start=0&limit={rr_page_limit}"
        try:
            data = self._get_json(url)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "drift": []}
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": [], "drift": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "drift": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "drift": []}
        docs = data.get("docs", [])
        records = []
        for doc in docs:
            if not isinstance(doc, dict):
                continue
            name = str(doc.get("companyName", "")).casefold()
            if needle[:24] and needle[:24] in name or name[:24] and name[:24] in needle:
                records.append(rr_record(doc, []))
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records, "drift": []}

