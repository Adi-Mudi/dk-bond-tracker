import json
from pathlib import Path

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.india_ratings import (
    SOURCE_NAME,
    IndiaRatingsAdapter,
)

SEARCH_URL = "https://www.indiaratings.co.in/home/GetSearch?searchKey=Tata%20Capital"
ISSUER_URL = "https://www.indiaratings.co.in/home/GetIssuerPressReleases?issuerId=7333"
SEARCH_PAYLOAD = {
    "issuerList": [
        {"issuerID": "7333", "name": "Tata Capital Financial Services Limited"},
        {"issuerID": "4269", "name": "Tata Capital Housing Finance Limited"},
    ],
    "pressreleaseList": [],
    "paidList": [],
}


def make_adapter(pages):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        payload = pages.get(url)
        if isinstance(payload, Exception):
            raise payload
        return payload

    return IndiaRatingsAdapter(transport=transport), calls


def test_search_parses_issuer_list():
    adapter, calls = make_adapter({SEARCH_URL: SEARCH_PAYLOAD})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) == 2
    assert records[0]["issuer_id"] == "7333"
    assert records[0]["company"] == "Tata Capital Financial Services Limited"
    assert records[0]["source"] == SOURCE_NAME
    assert records[0]["as_of"]
    assert calls == [SEARCH_URL]


def test_search_no_results_is_not_found():
    adapter, _ = make_adapter({SEARCH_URL: {"issuerList": [], "pressreleaseList": []}})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_NOT_FOUND
    assert result["records"] == []


def test_search_without_issuer_list_is_not_found():
    adapter, _ = make_adapter({SEARCH_URL: {"unexpected": True}})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_NOT_FOUND


def test_html_response_is_blocked():
    adapter, _ = make_adapter({SEARCH_URL: "<html>error</html>"})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_BLOCKED


def test_transport_timeout_is_timeout():
    adapter, _ = make_adapter({SEARCH_URL: TimeoutError("t")})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_TIMEOUT


def test_transport_connection_error_is_unreachable():
    adapter, _ = make_adapter({SEARCH_URL: ConnectionError("x")})
    result = adapter.search("Tata Capital")
    assert result["failure_code"] == FAILURE_UNREACHABLE


def test_issuer_prs_parse_real_fixture():
    pr_payload = json.loads(
        (Path(__file__).parent / "fixtures" / "indiaratings_issuer_pr.json").read_text(encoding="utf-8")
    )
    url = "https://www.indiaratings.co.in/home/GetIssuerPressReleases?issuerId=7333"
    adapter, _ = make_adapter({url: pr_payload})
    result = adapter.issuer_press_releases(7333)
    assert result["failure_code"] == FAILURE_OK
    assert len(result["records"]) == len(pr_payload)
    assert result["records"][0]["press_release_id"] == pr_payload[0]["pressReleaseID"]
    assert "Withdraws" in result["records"][0]["title"]


def test_issuer_prs_non_list_is_malformed():
    adapter, _ = make_adapter({"https://www.indiaratings.co.in/home/GetIssuerPressReleases?issuerId=7333": {"x": 1}})
    result = adapter.issuer_press_releases(7333)
    assert result["failure_code"] == FAILURE_MALFORMED


def test_issuer_prs_html_is_blocked():
    adapter, _ = make_adapter({"https://www.indiaratings.co.in/home/GetIssuerPressReleases?issuerId=7333": "<html>denied</html>"})
    result = adapter.issuer_press_releases(7333)
    assert result["failure_code"] == FAILURE_BLOCKED


def test_press_release_data_source_error_returns_data_none():
    adapter, _ = make_adapter({"https://www.indiaratings.co.in/pressReleases/GetPressreleaseData?pressReleaseId=9": "not-json{"})
    result = adapter.press_release_data(9)
    assert result["failure_code"] == FAILURE_MALFORMED
    assert result["data"] is None

