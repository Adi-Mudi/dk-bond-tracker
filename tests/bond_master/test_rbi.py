import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.bond_master import rbi
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
VALID_ISIN = "IN0020240019"
ABSENT_ISIN = "IN0000000001"
MALFORMED_ISIN = "IN002024001X"
MASTER = "rbi_securities.json"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def fixture_json(name):
    return json.loads(fixture_text(name))


def make(body=None, name=None):
    if name is not None:
        body = fixture_text(name)
    return rbi.Adapter(reader=lambda url: body)


def raising(exc):
    def reader(url):
        raise exc

    return reader


def test_adapter_name_is_rbi():
    assert rbi.NAME == "RBI"
    assert rbi.Adapter(reader=lambda url: "").name == "RBI"


def test_endpoint_is_an_https_published_download_file():
    assert rbi.ENDPOINT.startswith("https://")
    assert rbi.ENDPOINT.endswith((".json", ".csv", ".zip", ".txt"))


def test_endpoint_never_points_at_the_nse_site_or_api():
    lowered = rbi.ENDPOINT.lower()
    assert "nseindia" not in lowered
    assert "/api/" not in lowered


def test_adapter_reads_only_its_published_endpoint():
    seen = []

    def reader(url):
        seen.append(url)
        return fixture_text(MASTER)

    rbi.Adapter(reader=reader).fetch(VALID_ISIN)
    assert seen == [rbi.ENDPOINT]


def test_fixture_maps_every_fact_with_source():
    expected = fixture_json("rbi_expected.json")
    for isin, want in expected.items():
        result = make(name=MASTER).fetch(isin)
        facts = want["facts"]
        assert result.failure_code == FAILURE_OK
        assert result.isin == isin
        assert result.has_facts() is True
        for field in INSTRUMENT_FIELDS:
            assert getattr(result, field) == facts.get(field), field
        assert dict(result.sources) == want["sources"]


def test_sources_name_rbi_for_every_populated_field():
    result = make(name=MASTER).fetch(VALID_ISIN)
    assert result.sources
    for field, source in result.sources.items():
        assert source == "RBI"
        assert getattr(result, field) is not None
    assert "isin" not in result.sources


def test_government_securities_carry_no_rating():
    result = make(name=MASTER).fetch(VALID_ISIN)
    assert result.rating is None
    assert result.rating_agency is None
    assert "rating" not in result.sources


def test_issuer_type_keeps_the_published_security_type():
    adapter = make(name=MASTER)
    assert adapter.fetch("IN0020240019").issuer_type == "gsec"
    assert adapter.fetch("IN1520240021").issuer_type == "sdl"
    assert adapter.fetch("IN002024X0Z5").issuer_type == "t-bill"


def test_zero_coupon_tbill_leaves_coupon_and_cycle_empty():
    result = make(name=MASTER).fetch("IN002024X0Z5")
    assert result.coupon is None
    assert result.payout_cycle is None
    assert "coupon" not in result.sources
    assert "payout_cycle" not in result.sources


def test_rating_is_mapped_when_the_list_carries_one():
    body = json.dumps(
        {"records": [{"isin": ABSENT_ISIN, "security_name": "State Loan", "credit_rating": "ICRA AA"}]}
    )
    result = make(body=body).fetch(ABSENT_ISIN)
    assert result.rating == "AA"
    assert result.rating_agency == "ICRA"


def test_malformed_isin_is_invalid_and_never_reads():
    seen = []

    def reader(url):
        seen.append(url)
        return ""

    result = rbi.Adapter(reader=reader).fetch(MALFORMED_ISIN)
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert result.isin == MALFORMED_ISIN
    assert result.has_facts() is False
    assert seen == []


def test_isin_absent_from_the_lists_is_not_found():
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
    result = rbi.Adapter(reader=raising(rbi.SourceError(code))).fetch(VALID_ISIN)
    assert result.failure_code == code
    assert result.isin == VALID_ISIN
    assert result.has_facts() is False


def test_reader_timeout_error_maps_to_timeout():
    result = rbi.Adapter(reader=raising(TimeoutError())).fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_TIMEOUT


def test_reader_os_error_maps_to_unreachable():
    result = rbi.Adapter(reader=raising(OSError())).fetch(VALID_ISIN)
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
    result = make(body='{"source": "RBI"}').fetch(VALID_ISIN)
    assert result.failure_code == FAILURE_MALFORMED
