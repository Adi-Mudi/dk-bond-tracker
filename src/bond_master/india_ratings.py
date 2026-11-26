"""India Ratings & Research adapter (clean-slate, D7/D8).

Verified endpoints (agy research + live probe 2026-11-26):
- home/GetSearch?searchKey=<query> -> {issuerList[{issuerID, name}],
  pressreleaseList[...], paidList}
- home/GetIssuerPressReleases?issuerId=<id> -> PR list with ISIN annexures
- pressReleases/GetPressreleaseData?pressReleaseId=<id> -> full PR data

Emits canonical JSON records (D8). Unauthenticated JSON - no PDF parsing
needed for v1 (Rating Gate + Alerts unblock).
"""
import json
import re

from .transport import build_search_url
from .base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    utc_as_of,
)

SOURCE_NAME = "India Ratings"
DEFAULT_TIMEOUT = 30.0
BASE = "https" + "://" + "www.indiaratings.co.in"
GET_SEARCH = BASE + "/home/GetSearch?searchKey="
ISSUER_PR = BASE + "/home/GetIssuerPressReleases?issuerId="
PR_DATA = BASE + "/pressReleases/GetPressreleaseData?pressReleaseId="


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


def _company_matches(needle, name):
    needle = re.sub(r"\s+", " ", str(needle or "")).casefold().strip()
    name = re.sub(r"\s+", " ", str(name or "")).casefold().strip()
    return bool(needle) and bool(name) and (needle[:24] in name or name[:24] in needle)


class IndiaRatingsAdapter:
    name = SOURCE_NAME

    def __init__(self, transport=None, timeout=DEFAULT_TIMEOUT):
        self._transport = transport or _no_transport
        self.timeout = timeout

    def search(self, search_key):
        url = build_search_url(GET_SEARCH, "searchKey", search_key)
        try:
            data = _get_json(self._transport, url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": []}
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        records = []
        as_of = utc_as_of()
        for issuer in data.get("issuerList", []) or []:
            if isinstance(issuer, dict):
                records.append({
                    "issuer_id": issuer.get("issuerID"),
                    "company": issuer.get("name"),
                    "source": SOURCE_NAME,
                    "as_of": as_of,
                })
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records}

    def issuer_press_releases(self, issuer_id):
        url = ISSUER_PR + str(issuer_id)
        try:
            data = _get_json(self._transport, url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "records": []}
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "records": []}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "records": []}
        if not isinstance(data, list):
            return {"failure_code": FAILURE_MALFORMED, "records": []}
        records = []
        as_of = utc_as_of()
        docs = data
        for pr in docs:
            if not isinstance(pr, dict):
                continue
            records.append({
                "press_release_id": pr.get("pressReleaseID"),
                "title": pr.get("pressReleaseTitle"),
                "pr_type": pr.get("prTypeName"),
                "source": SOURCE_NAME,
                "as_of": as_of,
            })
        code = FAILURE_OK if records else FAILURE_NOT_FOUND
        return {"failure_code": code, "records": records}

    def press_release_data(self, press_release_id):
        url = PR_DATA + str(press_release_id)
        try:
            data = _get_json(self._transport, url, self.timeout)
        except TimeoutError:
            return {"failure_code": FAILURE_TIMEOUT, "data": None}
        except SourceError as exc:
            return {"failure_code": exc.failure_code, "data": None}
        except ConnectionError:
            return {"failure_code": FAILURE_UNREACHABLE, "data": None}
        except Exception:
            return {"failure_code": FAILURE_UNREACHABLE, "data": None}
        return {"failure_code": FAILURE_OK, "data": data}
