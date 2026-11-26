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
from src.bond_master.nse_wdm import FILE_KEY, NseWdmAdapter, REPORTS_API, parse_wdm_csv

FIXTURES = Path(__file__).parent / "fixtures"


def load_wdm_fixture():
    return (FIXTURES / "nse_wdm_wdmlist.csv").read_text(encoding="utf-8-sig")


def listing_response(entries):
    return json.dumps({"PreviousDay": entries}).encode()


def listing_entry(date="23-Nov-2026", csv_name="wdmlist_23112026.csv", path="https://nsearchives.nseindia.in/content/historical/WDM/2026/NOV/"):
    return {
        "fileHashKey": "WDM-SEC-AVAILABLE-FOR-TRADE-3",
        "fileKey": FILE_KEY,
        "fileSegment": "WDM",
        "displayName": "Securities available for trading(csv)",
        "fileActlName": csv_name,
        "filePath": path,
        "tradingDate": date,
        "filePosition": 1,
        "fileSize": "1.18 MB",
    }


def listing_without_target():
    entry = listing_entry()
    entry["fileKey"] = "WDM-DAILY-REPORT"
    return json.dumps({"PreviousDay": [entry]}).encode()


def make_adapter(pages):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        payload = pages.get(url)
        if isinstance(payload, Exception):
            raise payload
        return payload

    return NseWdmAdapter(transport=transport), calls


CSV_URL = "https://nsearchives.nseindia.in/content/historical/WDM/2026/NOV/wdmlist_23112026.csv"
REPORTS_URL = "https://www.nseindia.com/api/daily-reports?key=WDM"


def test_fetch_latest_catalog_two_gets_and_parses_csv():
    adapter, calls = make_adapter({
        REPORTS_URL: listing_response([listing_entry()]),
        CSV_URL: load_wdm_fixture(),
    })
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_OK
    assert calls[0] == REPORTS_URL
    assert calls[1] == CSV_URL
    records = result["records"]
    assert len(records) >= 10000
    assert result["source_url"] == CSV_URL


def test_records_carry_payout_fields():
    adapter, _ = make_adapter({
        REPORTS_URL: listing_response([listing_entry()]),
        CSV_URL: load_wdm_fixture(),
    })
    result = adapter.fetch_latest_catalog()
    record = result["records"][0]
    for field in ("isin", "security", "issue_name", "maturity", "coupon", "coupon_frequency", "next_ip_date", "status", "source", "as_of"):
        assert field in record
    assert record["source"] == "NSE WDM"
    assert record["coupon"] == 8.33
    assert record["as_of"]


def test_listing_without_target_file_is_not_found():
    entry = listing_entry()
    entry["fileKey"] = "WDM-DAILY-REPORT"
    adapter, _ = make_adapter({REPORTS_URL: listing_response([entry])})
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_NOT_FOUND


def test_reports_api_html_is_blocked():
    adapter, _ = make_adapter({REPORTS_URL: "<html>Access Denied</html>"})
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_BLOCKED


def test_csv_download_timeout_is_timeout():
    listing = listing_response([listing_entry()])
    adapter, _ = make_adapter({
        REPORTS_URL: listing,
        CSV_URL: TimeoutError("timed out"),
    })
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_TIMEOUT
    assert result["source_url"] == CSV_URL


def test_csv_download_connection_error_is_unreachable():
    listing = listing_response([listing_entry()])
    adapter, _ = make_adapter({
        REPORTS_URL: listing,
        CSV_URL: ConnectionError("no route"),
    })
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_UNREACHABLE


def test_reports_api_timeout_is_timeout():
    adapter, _ = make_adapter({REPORTS_URL: TimeoutError("timed out")})
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_TIMEOUT


def test_reports_api_connection_error_is_unreachable():
    adapter, _ = make_adapter({REPORTS_URL: ConnectionError("x")})
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_UNREACHABLE


def test_html_csv_body_is_blocked():
    adapter, _ = make_adapter({
        REPORTS_URL: listing_response([listing_entry()]),
        CSV_URL: "<html>Access Denied</html>",
    })
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_BLOCKED


def test_csv_missing_isin_column_is_malformed():
    adapter, _ = make_adapter({
        REPORTS_URL: listing_response([listing_entry()]),
        CSV_URL: "SECURITY,STATUS\nCG2036,Active\n",
    })
    result = adapter.fetch_latest_catalog()
    assert result["failure_code"] == FAILURE_MALFORMED


def test_parse_wdm_csv_strips_utf8_bom():
    records = parse_wdm_csv("\ufeffSECURITY,ISIN NO.\nCG2036,IN0019790024\n")
    assert len(records) == 1
    assert records[0]["isin"] == "IN0019790024"


def test_parse_wdm_csv_empty_body_raises_malformed():
    import pytest
    from src.bond_master.base import FAILURE_MALFORMED
    from src.bond_master.nse_wdm import SourceError
    with pytest.raises(SourceError) as exc:
        parse_wdm_csv("")
    assert exc.value.failure_code == FAILURE_MALFORMED


def test_duplicate_isins_deduped():
    payload = "SECURITY,ISIN NO.,MAT_DATE\nCG2036,IN0019790024,2036-01-01\nCG2036B,IN0019790024,2036-01-01\n"
    records = parse_wdm_csv(payload)
    assert len(records) == 1
