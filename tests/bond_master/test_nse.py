from pathlib import Path

from src.bond_master import nse
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ISIN = "INE205A07DV2"
YEARLY_ISIN = "INE205A07DW3"
COMBINED_RATING_ISIN = "INE205A07DY5"
UNKNOWN_ISIN = "INE999A07999"
EXPECTED_URL = "https://nsearchives.nseindia.com/content/debt/DEBT_SECURITY_MASTER.csv"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def transport_for(payload):
    return lambda url, timeout: payload


def adapter(payload=None):
    if payload is None:
        payload = fixture_text("nse_security_master.csv")
    return nse.NseAdapter(transport=transport_for(payload))


def test_published_download_endpoint_is_on_the_nse_archive_host():
    assert nse.NSE_SECURITY_MASTER_URL == EXPECTED_URL
    url = nse.NSE_SECURITY_MASTER_URL
    assert url.startswith("https://")
    assert nse.NSE_ARCHIVE_HOST in url
    assert url.endswith(".csv")


def test_published_endpoint_never_uses_the_nse_site_or_api():
    url = nse.NSE_SECURITY_MASTER_URL
    assert "/api/" not in url
    assert "www.nseindia.com" not in url
    assert url.count("nseindia.com") == 1


def test_user_agent_identifies_the_app():
    assert nse.USER_AGENT.startswith("DK Bond Tracker")


def test_adapter_name_is_nse():
    assert adapter().name == "NSE"


def test_fetch_maps_the_published_file_into_facts():
    result = adapter().fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.isin == ISIN
    assert result.company == "Acme Infra Ltd"
    assert result.coupon == 8.75
    assert result.payout_cycle == "annual"
    assert result.face_value == 1000.0
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"
    assert result.issuer_type == "ncd"
    assert result.secured == 1
    assert result.listing_status == "listed"
    assert result.maturity == "2030-03-31"


def test_every_fetched_value_carries_the_nse_source():
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
        assert result.source_of(field) == "NSE"


def test_payout_cycle_is_normalized_to_the_canonical_set():
    result = adapter().fetch(YEARLY_ISIN)
    assert result.payout_cycle == "annual"
    assert result.listing_status == "unlisted"
    assert result.secured == 0


def test_rating_without_a_separate_agency_column_is_split():
    result = adapter().fetch(COMBINED_RATING_ISIN)
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"


def test_maturity_accepts_day_month_year_dates():
    result = adapter().fetch(COMBINED_RATING_ISIN)
    assert result.maturity == "2031-01-20"


def test_unknown_isin_is_not_found():
    result = adapter().fetch(UNKNOWN_ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND
    assert result.has_facts() is False


def test_invalid_isin_never_reads_the_file():
    calls = []

    def transport(url, timeout):
        calls.append(url)
        return ""

    subject = nse.NseAdapter(transport=transport)
    result = subject.fetch("not-an-isin")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert calls == []


def test_network_error_is_unreachable():
    def transport(url, timeout):
        raise OSError("connection refused")

    assert (
        nse.NseAdapter(transport=transport).fetch(ISIN).failure_code
        == FAILURE_UNREACHABLE
    )


def test_clean_404_is_not_found():
    def transport(url, timeout):
        raise FileNotFoundError("404")

    assert nse.NseAdapter(transport=transport).fetch(ISIN).failure_code == FAILURE_NOT_FOUND


def test_timeout_is_reported():
    def transport(url, timeout):
        raise TimeoutError("timed out")

    assert nse.NseAdapter(transport=transport).fetch(ISIN).failure_code == FAILURE_TIMEOUT


def test_html_page_at_http_200_is_blocked():
    result = adapter(fixture_text("nse_blocked_page.html")).fetch(ISIN)
    assert result.failure_code == FAILURE_BLOCKED


def test_blank_download_is_malformed():
    assert adapter("   ").fetch(ISIN).failure_code == FAILURE_MALFORMED


def test_missing_isin_column_is_malformed():
    assert adapter("FOO,BAR\n1,2\n").fetch(ISIN).failure_code == FAILURE_MALFORMED


def test_bytes_payload_is_decoded():
    payload = fixture_text("nse_security_master.csv").encode("utf-8")
    result = nse.NseAdapter(transport=transport_for(payload)).fetch(ISIN)
    assert result.company == "Acme Infra Ltd"


def test_without_a_transport_no_request_is_made():
    assert nse.NseAdapter().fetch(ISIN).failure_code == FAILURE_UNREACHABLE


NSE_HEADER = (
    "ISIN,ISSUER NAME,COUPON (%),PAYOUT CYCLE,FACE VALUE,RATING,RATING AGENCY,"
    "ISSUER TYPE,SECURED,LISTING STATUS,MATURITY DATE\n"
)


def test_f5_embedded_agency_is_stripped_even_with_a_populated_agency_column():
    row = "INE205A07DV2,Acme Infra Ltd,8.75,annual,1000,CRISIL AA+,ICRA,ncd,Yes,Listed,2030-03-31\n"
    result = nse.NseAdapter(transport=transport_for(NSE_HEADER + row)).fetch(ISIN)
    assert result.rating == "AA+"
    assert result.rating_agency == "ICRA"


def test_f5_empty_agency_column_still_resolves_the_embedded_agency():
    row = "INE205A07DV2,Acme Infra Ltd,8.75,annual,1000,CRISIL AA+,,ncd,Yes,Listed,2030-03-31\n"
    result = nse.NseAdapter(transport=transport_for(NSE_HEADER + row)).fetch(ISIN)
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"


def test_f5_the_grade_modifier_survives_the_agency_split():
    row = "INE205A07DV2,Acme Infra Ltd,8.75,annual,1000,CARE BBB-,,ncd,Yes,Listed,2030-03-31\n"
    result = nse.NseAdapter(transport=transport_for(NSE_HEADER + row)).fetch(ISIN)
    assert result.rating == "BBB-"
    assert result.rating_agency == "CARE"
