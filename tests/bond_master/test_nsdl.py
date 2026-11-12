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


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name):
    return json.loads(fixture_text(name))


def make(body=None, name=None):
    if name is not None:
        body = fixture_text(name)
    return nsdl.Adapter(reader=lambda url: body)


def raising(exc):
    def reader(url):
        raise exc

    return reader


def test_adapter_name_is_nsdl():
    assert nsdl.NAME == "NSDL"
    assert nsdl.Adapter(reader=lambda url: "").name == "NSDL"


def test_endpoint_is_an_https_published_download_file():
    assert nsdl.ENDPOINT.startswith("https://")
    assert nsdl.ENDPOINT.endswith((".json", ".csv", ".zip", ".txt"))


def test_endpoint_never_points_at_the_nse_site_or_api():
    lowered = nsdl.ENDPOINT.lower()
    assert "nseindia" not in lowered
    assert "/api/" not in lowered


def test_adapter_reads_only_its_published_endpoint():
    seen = []

    def reader(url):
        seen.append(url)
        return fixture_text(MASTER)

    nsdl.Adapter(reader=reader).fetch(VALID_ISIN)
    assert seen == [nsdl.ENDPOINT]


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

    def reader(url):
        seen.append(url)
        return ""

    result = nsdl.Adapter(reader=reader).fetch(MALFORMED_ISIN)
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
    result = nsdl.Adapter(reader=raising(nsdl.SourceError(code))).fetch(VALID_ISIN)
    assert result.failure_code == code
    assert result.isin == VALID_ISIN
    assert result.has_facts() is False


def test_reader_timeout_error_maps_to_timeout():
    result = nsdl.Adapter(reader=raising(TimeoutError())).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_TIMEOUT


def test_reader_os_error_maps_to_unreachable():
    result = nsdl.Adapter(reader=raising(OSError())).fetch(VALID_ISIN)
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
