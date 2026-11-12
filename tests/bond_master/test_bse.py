from pathlib import Path

from src.bond_master import bse
from src.bond_master.base import (
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ISIN = "INE205A07DZ6"
OTHER_ISIN = "INE205A07E76"
UNKNOWN_ISIN = "INE999A07999"
EXPECTED_URL = "https://www.bseindia.com/download/debt/DEBT_SECURITY_MASTER.csv"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def transport_for(payload):
    return lambda url, timeout: payload


def adapter(payload=None):
    if payload is None:
        payload = fixture_text("bse_security_master.csv")
    return bse.BseAdapter(transport=transport_for(payload))


def test_published_download_endpoint_is_a_bse_download_file():
    assert bse.BSE_DEBT_SECURITY_MASTER_URL == EXPECTED_URL
    url = bse.BSE_DEBT_SECURITY_MASTER_URL
    assert url.startswith("https://")
    assert bse.BSE_DOWNLOAD_HOST in url
    assert bse.BSE_DOWNLOAD_PREFIX in url
    assert url.endswith(".csv")


def test_published_endpoint_never_uses_the_bse_api():
    url = bse.BSE_DEBT_SECURITY_MASTER_URL
    assert "api.bseindia.com" not in url
    assert "/api/" not in url


def test_user_agent_identifies_the_app():
    assert bse.USER_AGENT.startswith("DK Bond Tracker")


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


def test_invalid_isin_never_reads_the_file():
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return ""

    subject = bse.BseAdapter(transport=transport)
    result = subject.fetch("not-an-isin")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert calls == []


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


def test_html_page_at_http_200_is_malformed():
    result = adapter(fixture_text("bse_blocked_page.html")).fetch(ISIN)
    assert result.failure_code == FAILURE_MALFORMED


def test_blank_download_is_malformed():
    assert adapter("   ").fetch(ISIN).failure_code == FAILURE_MALFORMED


def test_missing_isin_column_is_malformed():
    assert adapter("FOO,BAR\n1,2\n").fetch(ISIN).failure_code == FAILURE_MALFORMED


def test_without_a_transport_no_request_is_made():
    assert bse.BseAdapter().fetch(ISIN).failure_code == FAILURE_UNREACHABLE
