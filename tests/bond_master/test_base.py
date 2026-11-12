import sys
from dataclasses import fields
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_CODES,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    INSTRUMENT_FIELDS,
    LISTING_STATUSES,
    POSITION_FIELDS,
    RESULT_FIELDS,
    SOURCE_PRIORITY,
    Adapter,
    FetchResult,
)

AF01_FACTS = frozenset(
    {
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
    }
)


def test_instrument_fields_are_the_af01_facts():
    assert set(INSTRUMENT_FIELDS) == set(AF01_FACTS)
    assert "coupon" in INSTRUMENT_FIELDS
    assert "isin" not in INSTRUMENT_FIELDS


def test_result_fields_carry_the_isin_join_key():
    assert RESULT_FIELDS[0] == "isin"
    assert set(RESULT_FIELDS) == set(AF01_FACTS) | {"isin"}


def test_no_position_facts_in_the_field_model():
    for name in POSITION_FIELDS:
        assert name not in RESULT_FIELDS
        assert name not in INSTRUMENT_FIELDS


def test_position_fields_name_the_af12_exclusions():
    assert set(POSITION_FIELDS) == {
        "amount",
        "quantity",
        "start_date",
        "end_date",
        "credit_day",
    }


def test_fetch_result_exposes_every_result_field():
    names = {item.name for item in fields(FetchResult)}
    assert set(RESULT_FIELDS) <= names
    assert "sources" in names
    assert "failure_code" in names


def test_listing_statuses_are_the_af08_set():
    assert tuple(LISTING_STATUSES) == ("listed", "unlisted", "unknown")


def test_source_priority_is_nsdl_rbi_nse_bse():
    assert tuple(SOURCE_PRIORITY) == ("NSDL", "RBI", "NSE", "BSE")


def test_failure_codes_cover_the_af06_states():
    assert FAILURE_OK in FAILURE_CODES
    assert FAILURE_NOT_FOUND in FAILURE_CODES
    assert FAILURE_UNREACHABLE in FAILURE_CODES
    assert FAILURE_TIMEOUT in FAILURE_CODES
    assert FAILURE_BLOCKED in FAILURE_CODES
    assert FAILURE_PARSE_ERROR in FAILURE_CODES
    assert FAILURE_OFFLINE in FAILURE_CODES
    assert len(set(FAILURE_CODES)) == len(FAILURE_CODES)
    assert all(isinstance(code, str) for code in FAILURE_CODES)


def test_default_failure_code_is_ok():
    assert FetchResult().failure_code == FAILURE_OK


def test_facts_sources_and_helpers():
    result = FetchResult(
        isin="INE205A07DV2",
        company="Acme Ltd",
        coupon=8.75,
        payout_cycle="annual",
        face_value=1000.0,
        rating="AA+",
        rating_agency="CRISIL",
        issuer_type="ncd",
        secured=1,
        listing_status="listed",
        maturity="2030-03-31",
        sources={"company": "NSDL", "rating": "NSE", "maturity": "BSE"},
    )
    assert result.facts() == {
        "company": "Acme Ltd",
        "coupon": 8.75,
        "payout_cycle": "annual",
        "face_value": 1000.0,
        "rating": "AA+",
        "rating_agency": "CRISIL",
        "issuer_type": "ncd",
        "secured": 1,
        "listing_status": "listed",
        "maturity": "2030-03-31",
    }
    assert result.source_of("rating") == "NSE"
    assert result.source_of("secured") is None
    assert result.has_facts() is True


def test_failure_result_reports_code_and_no_facts():
    result = FetchResult(isin="INE205A07DV2", failure_code=FAILURE_NOT_FOUND)
    assert result.failure_code == FAILURE_NOT_FOUND
    assert result.has_facts() is False


def test_adapter_protocol_declares_the_contract():
    assert getattr(Adapter, "_is_protocol", False) is True
    assert "fetch" in Adapter.__dict__
    assert "name" in Adapter.__annotations__


def test_a_structural_adapter_returns_a_fetch_result():
    class FakeAdapter:
        name = "NSDL"

        def fetch(self, isin):
            return FetchResult(
                isin=isin,
                company="Acme Ltd",
                sources={"company": "NSDL"},
            )

    adapter = FakeAdapter()
    result = adapter.fetch("INE205A07DV2")
    assert isinstance(result, FetchResult)
    assert result.isin == "INE205A07DV2"
    assert result.source_of("company") == "NSDL"
