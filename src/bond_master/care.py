"""CARE Ratings adapter (clean-slate, D7/D8).

Verified endpoints (agy research + live probes 2026-11-25/26, careratings.com):
- header/searchlist?cinput=<query> -> {"data": [[...{CompanyID (encrypted
  b64), CompanyName}...]]} - company search
- getSearchprintrating?companyName=<encrypted CompanyID> -> {"data": [{
  CompanyID (numeric), Company, CompanyInstrument: [{Instrument,
  RatingAmount, Rating}]}]} - instrument ratings per company
- getSearchprdocument / getSearchrrddata?companyName=<enc>&YearID=<YYYY>
  -> documents + rationale data (YearID = report year)

Records are D8 canonical JSON. CARE does not expose ISIN on these endpoints
- records key on company_id + instrument (ISIN linking happens at the
master level via company-name matching).
"""
from __future__ import annotations

import json

from .transport import quote_param
from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)

SOURCE_NAME = "CARE"
DEFAULT_TIMEOUT = 30.0
BASE = "https" + "://" + "www.careratings.com"
SEARCH = BASE + "/header/searchlist?cinput="
PRINT_RATING = BASE + "/getSearchprintrating?companyName="
PRINT_DOCUMENT = BASE + "/getSearchprdocument?companyName="
RRD_DATA = BASE + "/getSearchrrddata?companyName="

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
}


class SourceError(Exception):
    def __init__(self, failure_code):
        super().__init__(failure_code)
        self.failure_code = failure_code


def _no_transport(url, timeout):
    raise ConnectionError("no transport configured")


def _get_json(transport, url, timeout):
    payload = transport(url, timeout)
    if isinstance(payload, (bytes, bytearray)):
        payload = payload.decode("utf-8-sig", "replace")
    if isinstance(payload, (dict, list)):
        return payload
    text = str(payload).strip()
    if not text:
        raise SourceError(FAILURE_MALFORMED)
    if text[:1] == "<":
        raise SourceError(FAILURE_BLOCKED)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        raise SourceError(FAILURE_MALFORMED)


def _find_companies(obj, out):
    if isinstance(obj, dict):
        if "CompanyID" in obj:
            out.append(obj)
        for value in obj.values():
            _find_companies(value, out)
    elif isinstance(obj, list):
        for item in obj:
            _find_companies(item, out)


class CareAdapter:
    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT):
        self._transport = transport or _no_transport
        self.timeout = timeout

    def _get(self, url):
        try:
            data = _get_json(self._transport, url, self.timeout)
        except SourceError:
            raise
        except TimeoutError:
            raise
        except ConnectionError:
            raise
        except Exception:
            raise
        return data

    def search(self, query):
        url = SEARCH + quote_param(query)
        try:
            data = self._get(url)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": []}
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        companies = []
        _find_companies(data, companies)
        records = []
        as_of = utc_as_of()
        for co in companies:
            records.append({
                "company_id": co.get("CompanyID"),
                "company": co.get("CompanyName"),
                "source": SOURCE_NAME,
                "as_of": as_of,
            })
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records}

    def instrument_ratings(self, company_id):
        url = PRINT_RATING + quote_param(company_id)
        try:
            data = self._get(url)
        except SourceError as exc:
            code = FAILURE_NOT_FOUND if exc.failure_code == FAILURE_MALFORMED else exc.failure_code
            return {"failure_code": code, "records": []}
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        records = []
        _find_instruments(data, records, company_id, as_of=utc_as_of())
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records}

    def documents(self, company_id, year_id):
        url = (PRINT_DOCUMENT + quote_param(company_id)
               + "&YearID=" + quote_param(year_id))
        try:
            data = self._get(url)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": [], "documents": []}
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": [], "documents": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "documents": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": [], "documents": []}
        docs = []
        _find_documents(data, docs)
        code = FAILURE_OK if docs else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": docs, "documents": docs}

    def rrd_data(self, company_id, year_id):
        url = (RRD_DATA + quote_param(company_id)
               + "&YearID=" + quote_param(year_id))
        try:
            data = self._get(url)
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "data": None}
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "data": None}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "data": None}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "data": None}
        return {"failure_code": FAILURE_OK, "data": data}


def _find_instruments(obj, records, company_id, company=None, as_of=None):
    if isinstance(obj, dict):
        company = company or obj.get("Company")
        instruments = obj.get("CompanyInstrument")
        if isinstance(instruments, list):
            cid = obj.get("CompanyID")
            for inst in instruments:
                if not isinstance(inst, dict):
                    continue
                records.append({
                    "company_id": cid or company_id,
                    "company": company or obj.get("Company"),
                    "instrument": inst.get("Instrument"),
                    "rating_amount": inst.get("RatingAmount"),
                    "rating": inst.get("Rating"),
                    "source": SOURCE_NAME,
                    "as_of": as_of or utc_as_of(),
                })
        for value in obj.values():
            if isinstance(value, (dict, list)):
                _find_instruments(value, records, company_id, company, as_of=as_of)
    elif isinstance(obj, list):
        for item in obj:
            _find_instruments(item, records, company_id, company, as_of=as_of)


def _find_documents(obj, docs):
    if isinstance(obj, dict):
        for value in obj.values():
            _find_documents(value, docs)
    elif isinstance(obj, list):
        for item in obj:
            _find_documents(item, docs)
