import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.bond_master import nsdl
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    INSTRUMENT_FIELDS,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures"
VALID_ISIN = "INE205A07DV2"
ABSENT_ISIN = "INE000A00AA1"
MALFORMED_ISIN = "INE205A07DVX"
MASTER = "nsdl_corporate_bond_master.json"
EXPECTED_ENDPOINT = "https://nsdl.co.in/downloadables/corporate_bond_master.json"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name):
    return json.loads(fixture_text(name))


def make(body=None, name=None):
    if name is not None:
        body = fixture_text(name)
    return nsdl.NsdlAdapter(transport=lambda url, timeout: body)


def raising(exc):
    def transport(url, timeout):
        raise exc

    return transport


def test_adapter_name_is_nsdl():
    assert nsdl.SOURCE_NAME == "NSDL"
    assert nsdl.NsdlAdapter().name == "NSDL"


def test_default_timeout_is_ten_seconds():
    assert nsdl.DEFAULT_TIMEOUT == 10.0


def test_endpoint_is_an_https_published_download_file():
    assert nsdl.ENDPOINT.startswith("https://")
    assert nsdl.ENDPOINT.endswith((".json", ".csv", ".zip", ".txt"))


def test_endpoint_never_points_at_the_nse_site_or_api():
    lowered = nsdl.ENDPOINT.lower()
    assert "nseindia" not in lowered
    assert "/api/" not in lowered


def test_endpoint_equals_the_published_download_url():
    assert nsdl.ENDPOINT == EXPECTED_ENDPOINT


def test_transport_receives_the_endpoint_and_timeout():
    seen = []

    def transport(url, timeout):
        seen.append((url, timeout))
        return fixture_text(MASTER)

    nsdl.NsdlAdapter(transport=transport, timeout=7.5).fetch(VALID_ISIN)
    assert seen == [(nsdl.ENDPOINT, 7.5)]


def test_default_transport_reports_unreachable():
    result = nsdl.NsdlAdapter().fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_UNREACHABLE


def test_bytes_payload_is_decoded():
    body = fixture_text(MASTER).encode("utf-8")
    result = nsdl.NsdlAdapter(transport=lambda url, timeout: body).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == "Acme Infrastructure Ltd"


def test_fixture_maps_every_fact_with_source():
    expected = fixture_json("nsdl_expected.json")
    for isin, want in expected.items():
        result = make(name=MASTER).fetch(isin)
        facts = want["facts"]
        assert result.failure_code == FAILURE_OK
        assert result.isin == isin
        assert result.has_facts() is True
        for field in INSTRUMENT_FIELDS:
            assert getattr(result, field) == facts.get(field), field
        assert dict(result.sources) == want["sources"]


def test_sources_name_nsdl_for_every_populated_field():
    result = make(name=MASTER).fetch("INE777A07ZZ3")
    assert result.sources
    for field, source in result.sources.items():
        assert source == "NSDL"
        assert getattr(result, field) is not None
    assert "isin" not in result.sources


def test_rating_keeps_the_modifier_with_its_agency():
    result = make(name=MASTER).fetch(VALID_ISIN)
    assert result.rating == "AA+"
    assert result.rating_agency == "CRISIL"


def test_embedded_agency_prefix_is_split_out():
    result = make(name=MASTER).fetch("INE777A07ZZ3")
    assert result.rating == "A"
    assert result.rating_agency == "CARE"


def test_sub_investment_grade_rating_is_preserved_not_nulled():
    body = json.dumps({"records": [{"isin": ABSENT_ISIN, "credit_rating": "CRISIL BB+"}]})
    result = make(body=body).fetch(ABSENT_ISIN)
    assert result.rating == "BB+"
    assert result.rating_agency == "CRISIL"


def test_malformed_isin_is_invalid_and_never_reads():
    seen = []

    def transport(url, timeout):
        seen.append((url, timeout))
        return ""

    result = nsdl.NsdlAdapter(transport=transport).fetch(MALFORMED_ISIN)
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert result.isin == MALFORMED_ISIN
    assert result.has_facts() is False
    assert seen == []


def test_isin_absent_from_the_master_is_not_found():
    result = make(name=MASTER).fetch(ABSENT_ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND
    assert result.has_facts() is False


def test_valid_isin_in_empty_records_is_not_found():
    result = make(body='{"records": []}').fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND


@pytest.mark.parametrize(
    "code",
    [
        FAILURE_TIMEOUT,
        FAILURE_UNREACHABLE,
        FAILURE_BLOCKED,
        FAILURE_RATE_LIMITED,
        FAILURE_OFFLINE,
    ],
)
def test_transport_source_error_maps_to_its_code(code):
    result = nsdl.NsdlAdapter(transport=raising(nsdl.SourceError(code))).fetch(VALID_ISIN)
    assert result.failure_code == code
    assert result.isin == VALID_ISIN
    assert result.has_facts() is False


def test_reader_timeout_error_maps_to_timeout():
    result = nsdl.NsdlAdapter(transport=raising(TimeoutError())).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_TIMEOUT


def test_missing_download_file_maps_to_not_found():
    result = nsdl.NsdlAdapter(transport=raising(FileNotFoundError())).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND


def test_reader_os_error_maps_to_unreachable():
    result = nsdl.NsdlAdapter(transport=raising(OSError())).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_UNREACHABLE


def test_unexpected_error_maps_to_unreachable():
    result = nsdl.NsdlAdapter(transport=raising(RuntimeError("boom"))).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_UNREACHABLE


def test_non_json_body_maps_to_parse_error():
    result = make(body="this is not json").fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_PARSE_ERROR


def test_html_block_page_maps_to_blocked():
    result = make(body="<html><body>Request blocked</body></html>").fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_BLOCKED


def test_blank_body_maps_to_malformed():
    result = make(body="   ").fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_MALFORMED


def test_json_without_records_maps_to_malformed():
    result = make(body='{"source": "NSDL"}').fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_MALFORMED


def test_scalar_json_maps_to_malformed():
    result = make(body='"just a string"').fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_MALFORMED
