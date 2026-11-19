import json
from pathlib import Path

from src.bond_master import bse
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ISIN = "INE205A07DZ6"
OTHER_ISIN = "INE205A07E76"
UNKNOWN_ISIN = "INE999A07999"
EXPECTED_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
MASTER = "bse_list_of_scrip_debt.json"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def transport_for(payload):
    return lambda url, timeout: payload


def adapter(payload=None):
    if payload is None:
        payload = fixture_text(MASTER)
    return bse.BseAdapter(transport=transport_for(payload))


def test_published_endpoint_is_the_bse_json_api():
    assert bse.BSE_LIST_OF_SCRIP_URL == EXPECTED_URL
    url = bse.BSE_LIST_OF_SCRIP_URL
    assert url.startswith("https://")
    assert "api.bseindia.com" in url
    assert url.endswith("/ListofScripData/w")


def test_endpoint_never_points_at_the_dead_csv_download():
    lowered = bse.BSE_LIST_OF_SCRIP_URL.lower()
    assert "www.bseindia.com/download/" not in lowered
    assert ".csv" not in lowered
    assert bse.BSE_DEBT_SEGMENT == "Debentures and Bonds"


def test_build_url_carries_the_debt_segment_and_active_status():
    url = bse.build_url()
    assert url.startswith(EXPECTED_URL + "?")
    assert "segment=Debentures%20and%20Bonds" in url
    assert "status=Active" in url


def test_user_agent_is_a_browser_fingerprint():
    assert bse.USER_AGENT.startswith("Mozilla/5.0")
    assert "Chrome/" in bse.USER_AGENT
    assert bse.REQUEST_HEADERS["User-Agent"] == bse.USER_AGENT
    assert bse.REQUEST_HEADERS["Referer"] == bse.BSE_BASE_URL
    assert bse.REQUEST_HEADERS["Origin"] == bse.BSE_BASE_URL
    assert "Accept-Language" in bse.REQUEST_HEADERS


def test_adapter_name_is_bse():
    assert adapter().name == "BSE"


def test_fetch_maps_the_published_file_into_facts():
    result = adapter().fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.isin == ISIN
    assert result.company == "Zenith Ports Ltd"
    assert result.coupon == 10.25
    assert result.payout_cycle == "annual"
    assert result.face_value == 100000.0
    assert result.rating == "AA"
    assert result.rating_agency == "CARE"
    assert result.issuer_type == "ncd"
    assert result.secured == 1
    assert result.listing_status == "listed"
    assert result.maturity == "2032-05-10"


def test_every_fetched_value_carries_the_bse_source():
    result = adapter().fetch(ISIN)
    for field in (
        "company",
        "coupon",
        "payout_cycle",
        "face_value",
        "rating",
        "rating_agency",
        "issuer_type",
        "secured",
        "listing_status",
        "maturity",
    ):
        assert result.source_of(field) == "BSE"


def test_unlisted_row_maps_both_listing_status_and_secured():
    result = adapter().fetch(OTHER_ISIN)
    assert result.payout_cycle == "quarterly"
    assert result.listing_status == "unlisted"
    assert result.secured == 0
    assert result.issuer_type == "corporate_bond"


def test_unknown_isin_is_not_found():
    result = adapter().fetch(UNKNOWN_ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND
    assert result.has_facts() is False


def test_invalid_isin_never_calls_the_transport():
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return ""

    subject = bse.BseAdapter(transport=transport)
    result = subject.fetch("not-an-isin")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert calls == []


def test_transport_receives_the_api_url_and_timeout():
    seen = []

    def transport(url, timeout):
        seen.append((url, timeout))
        return fixture_text(MASTER)

    bse.BseAdapter(transport=transport, timeout=7.5).fetch(ISIN)
    assert seen == [(bse.build_url(), 7.5)]


def test_network_error_is_unreachable():
    def transport(url, timeout):
        raise OSError("connection refused")

    assert (
        bse.BseAdapter(transport=transport).fetch(ISIN).failure_code
        == FAILURE_UNREACHABLE
    )


def test_clean_404_is_not_found():
    def transport(url, timeout):
        raise FileNotFoundError("404")

    assert bse.BseAdapter(transport=transport).fetch(ISIN).failure_code == FAILURE_NOT_FOUND


def test_timeout_is_reported():
    def transport(url, timeout):
        raise TimeoutError("timed out")

    assert bse.BseAdapter(transport=transport).fetch(ISIN).failure_code == FAILURE_TIMEOUT


def test_source_error_maps_its_failure_code():
    def transport(url, timeout):
        raise bse.SourceError(FAILURE_BLOCKED)

    assert bse.BseAdapter(transport=transport).fetch(ISIN).failure_code == FAILURE_BLOCKED


def test_html_page_at_http_200_is_blocked():
    result = adapter(fixture_text("bse_blocked_page.html")).fetch(ISIN)
    assert result.failure_code == FAILURE_BLOCKED


def test_blank_download_is_malformed():
    assert adapter("   ").fetch(ISIN).failure_code == FAILURE_MALFORMED


def test_non_json_payload_is_parse_error():
    assert adapter("not json at all").fetch(ISIN).failure_code == FAILURE_PARSE_ERROR


def test_without_a_transport_no_request_is_made():
    assert bse.BseAdapter().fetch(ISIN).failure_code == FAILURE_UNREACHABLE


def _record(**overrides):
    record = {
        "ISIN_NUMBER": ISIN,
        "Issuer_Name": "Zenith Ports Ltd",
        "FACE_VALUE": "100000",
        "COUPON_RATE": "10.25",
        "PAYOUT_FREQUENCY": "Annual",
        "CREDIT_RATING": "AA",
        "SECURITY_TYPE": "ncd",
        "SECURED": "Yes",
        "LISTING_STATUS": "Listed",
        "MATURITY_DATE": "2032-05-10",
    }
    record.update(overrides)
    return json.dumps([record])


def test_f5_embedded_agency_is_stripped_even_with_a_populated_agency_column():
    payload = _record(CREDIT_RATING="CRISIL AA", RATING_AGENCY="ICRA")
    result = bse.BseAdapter(transport=transport_for(payload)).fetch(ISIN)
    assert result.rating == "AA"
    assert result.rating_agency == "ICRA"


def test_f5_empty_agency_column_still_resolves_the_embedded_agency():
    payload = _record(CREDIT_RATING="CARE BBB-", RATING_AGENCY="")
    result = bse.BseAdapter(transport=transport_for(payload)).fetch(ISIN)
    assert result.rating == "BBB-"
    assert result.rating_agency == "CARE"
