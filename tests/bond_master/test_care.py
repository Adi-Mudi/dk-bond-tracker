import json
from pathlib import Path

import pytest

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.care import CareAdapter, SOURCE_NAME

FIXTURES = Path(__file__).parent / "fixtures"
SEARCH_URL = "https://www.careratings.com/header/searchlist?cinput=Tata%20Capital"
CID_ENC = "MYPjaBsE6/+MP8Mnsz03TA=="
import urllib.parse  # noqa: F401
CID_ENC_Q = urllib.parse.quote(CID_ENC)  # adapter quotes with default-safe form: "+" -> %2B, "=" -> %3D, "/" stays
PR_URL = f"https://www.careratings.com/getSearchprintrating?companyName={CID_ENC_Q}"


def load_search():
    return json.loads((FIXTURES / "care_searchlist.json").read_text(encoding="utf-8"))


def load_printrating():
    return json.loads((FIXTURES / "care_printrating.json").read_text(encoding="utf-8"))


def make_adapter(pages):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        payload = pages.get(url)
        if isinstance(payload, Exception):
            raise payload
        return payload

    return CareAdapter(transport=transport), calls


def test_search_finds_companies():
    adapter, calls = make_adapter({SEARCH_URL: load_search()})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) == 3
    assert records[0]["company_id"] == CID_ENC
    assert "Tata" in records[0]["company"]
    assert calls == [SEARCH_URL]


def test_search_no_results_is_not_found():
    adapter, _ = make_adapter({SEARCH_URL: []})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_NOT_FOUND


def test_html_response_is_blocked():
    adapter, _ = make_adapter({SEARCH_URL: "<html>denied</html>"})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_BLOCKED


def test_malformed_json_is_malformed():
    adapter, _ = make_adapter({SEARCH_URL: "not-json{"})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_MALFORMED


def test_transport_timeout_is_timeout():
    adapter, _ = make_adapter({SEARCH_URL: TimeoutError("t")})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_TIMEOUT


def test_transport_connection_error_is_unreachable():
    adapter, _ = make_adapter({SEARCH_URL: ConnectionError("x")})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_UNREACHABLE


def test_instrument_ratings_parse_real_fixture():
    pr = load_printrating()
    adapter, _ = make_adapter({PR_URL: pr})
    result = adapter.instrument_ratings(CID_ENC)
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) == len(pr["data"][0]["CompanyInstrument"])
    for record in records:
        assert record["company_id"] == pr["data"][0]["CompanyID"]
        assert record["rating"]
        assert record["instrument"]


def test_instrument_ratings_empty_is_not_found():
    adapter, _ = make_adapter({PR_URL: {"data": []}})
    result = adapter.instrument_ratings("missing")
    assert result["failure_code"] == FAILURE_NOT_FOUND
