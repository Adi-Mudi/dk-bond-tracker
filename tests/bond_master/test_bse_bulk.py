import json
from pathlib import Path

import pytest

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.bse_bulk import BseBulkAdapter, SOURCE_NAME, parse_payload

FIXTURE = Path(__file__).parent / "fixtures" / "bse_list_of_scrip_debt.json"


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def make_adapter(payload):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        if isinstance(payload, Exception):
            raise payload
        return payload

    adapter = BseBulkAdapter(transport=transport)
    return adapter, calls


def test_parses_full_real_payload_with_zero_drift():
    adapter, calls = make_adapter(load_fixture())
    result = adapter.fetch_catalog()
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) >= 5000
    assert calls == [adapter.url]


def test_every_record_is_canonical_d8_shape():
    result = make_adapter(load_fixture())[0].fetch_catalog()
    for record in result["records"]:
        assert set(record) == {
            "isin", "company", "scrip_name", "scrip_code", "scrip_id",
            "face_value", "group", "status", "segment", "source_url", "source",
            "as_of",
        }
        assert record["source"] == SOURCE_NAME
        assert record["isin"]
        assert record["as_of"]


def test_isin_unique_and_valid_format():
    result = make_adapter(load_fixture())[0].fetch_catalog()
    isins = [r["isin"] for r in result["records"]]
    assert len(isins) == len(set(isins))
    import re
    for isin in isins:
        assert re.fullmatch(r"[A-Z]{2}[A-Z0-9]{9}\d", isin), isin


def test_field_population_invariants_from_real_payload():
    records = make_adapter(load_fixture())[0].fetch_catalog()["records"]
    with_company = sum(1 for r in records if r["company"])
    with_face_value = sum(1 for r in records if r["face_value"] is not None)
    assert with_company / len(records) > 0.99
    assert with_face_value / len(records) > 0.99
    assert all(isinstance(r["face_value"], float) for r in records if r["face_value"] is not None)


def test_dead_fields_never_emitted():
    result = make_adapter(load_fixture())[0].fetch_catalog()
    for record in result["records"]:
        assert "INDUSTRY" not in record
        assert "Mktcap" not in record


def test_empty_array_is_ok_with_no_records():
    adapter, _ = make_adapter([])
    result = adapter.fetch_catalog()
    assert result["failure_code"] == FAILURE_OK
    assert result["records"] == []


def test_html_body_is_blocked_not_malformed():
    adapter, _ = make_adapter("<html><body>Access Denied</body></html>")
    result = adapter.fetch_catalog()
    assert result["failure_code"] == FAILURE_BLOCKED


def test_non_json_text_is_malformed():
    adapter, _ = make_adapter("this is not json at all")
    result = adapter.fetch_catalog()
    assert result["failure_code"] == FAILURE_MALFORMED


def test_connection_error_is_unreachable():
    class Boom:
        def fetch_catalog(self):
            return None

    adapter, _ = make_adapter(ConnectionError("no route"))
    result = adapter.fetch_catalog()
    assert result["failure_code"] == FAILURE_UNREACHABLE


def test_transport_timeout_is_timeout():
    adapter, _ = make_adapter(TimeoutError("timed out"))
    result = adapter.fetch_catalog()
    assert result["failure_code"] == FAILURE_TIMEOUT


def test_rows_without_isin_are_skipped():
    rows = [
        {"ISIN_NUMBER": "INE001A07AX9", "Issuer_Name": "A Ltd", "Scrip_Name": "A"},
        {"Issuer_Name": "no isin here"},
        {"ISIN_NUMBER": "INE002A07AY1", "Issuer_Name": "B Ltd", "Scrip_Name": "B"},
    ]
    records = parse_payload(rows)
    assert [r["isin"] for r in records] == ["INE001A07AX9", "INE002A07AY1"]


def test_utf8_bom_is_stripped():
    rows = [{"ISIN_NUMBER": "INE001A07AX9", "Issuer_Name": "A"}]
    payload = "﻿" + json.dumps(rows)
    records = parse_payload(payload)
    assert len(records) == 1


def test_additive_unknown_key_is_tolerated_and_logged_as_drift():
    rows = [{"ISIN_NUMBER": "INE001A07AX9", "Issuer_Name": "A", "BRAND_NEW_KEY": "x"}]
    drift = []
    records = parse_payload(rows, drift=drift)
    assert records and records[0]["isin"] == "INE001A07AX9"
    assert "BRAND_NEW_KEY" in drift


def test_face_value_safe_float_parsing():
    rows = [
        {"ISIN_NUMBER": "INE001A07AX9", "FACE_VALUE": "1,00,000.00"},
        {"ISIN_NUMBER": "INE001A07AY1", "FACE_VALUE": "0.00"},
        {"ISIN_NUMBER": "INE001A07AZ2", "FACE_VALUE": ""},
    ]
    records = parse_payload(rows)
    assert records[0]["face_value"] == 100000.0
    assert records[1]["face_value"] == 0.0
    assert records[2]["face_value"] is None


def test_rows_missing_isin_are_skipped_not_emitted():
    records = parse_payload([{"Scrip_Name": "no isin"}])
    assert records == []


def test_scrip_name_preserved_separately_from_issuer():
    rows = [{
        "ISIN_NUMBER": "INE001A07AX9",
        "Issuer_Name": "Samvardhana Motherson International Limited",
        "Scrip_Name": "SMILCCD",
    }]
    records = parse_payload(rows)
    assert records[0]["company"] == "Samvardhana Motherson International Limited"
    assert records[0]["scrip_name"] == "SMILCCD"
