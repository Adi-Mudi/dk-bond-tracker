import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bond_master import nsdl
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    FetchResult,
)

FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
RECORDED = FIXTURES / "nsdl_web_api_ine002z08143.json"
ISIN = "INE002Z08143"
EXPECTED_COMPANY = "WELSPUN AUNTA-SIMARIA PROJECT PRIVATE LIMITED"


def recorded_body():
    return RECORDED.read_text(encoding="utf-8")


def transport_for(bodies, seen=None):
    calls = {"n": 0}

    def transport(url, timeout):
        index = min(calls["n"], len(bodies) - 1)
        calls["n"] += 1
        if seen is not None:
            seen.append((url, timeout))
        return bodies[index]

    return transport, calls


def test_v1_recorded_fixture_returns_real_nsdl_facts():
    seen = []
    transport, calls = transport_for([recorded_body()], seen=seen)
    result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == EXPECTED_COMPANY
    assert result.issuer_type == "debenture"
    assert result.maturity == "2028-09-30"
    assert result.face_value == 100.0
    assert result.has_facts() is True
    assert calls["n"] == 1
    url = seen[0][0]
    assert url.startswith("https://nsdl.com/web/api/v1/participant/search?")
    assert f"isin={ISIN}" in url
    assert "search_type=DetailedSearch" in url


@pytest.mark.skipif(
    os.environ.get("NSDL_LIVE") != "1",
    reason="live smoke is opt-in; set NSDL_LIVE=1 to hit nsdl.com",
)
def test_v1_live_smoke_with_browser_user_agent(monkeypatch):
    from src.bond_master import transport

    monkeypatch.setattr(transport, "USER_AGENT", nsdl.USER_AGENT)
    result = nsdl.NsdlAdapter(transport=transport.http_get).fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == EXPECTED_COMPANY


def test_v2_block_page_is_retried_then_accepted():
    waits = []
    bodies = ["<html><body>Request Rejected</body></html>", "<html>blocked</html>", recorded_body()]
    transport, calls = transport_for(bodies)
    result = nsdl.NsdlAdapter(transport=transport, sleep=lambda delay: waits.append(delay)).fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == EXPECTED_COMPANY
    assert calls["n"] == 3
    assert waits == [0.5, 1.0]


def test_v2_persistent_block_page_maps_to_blocked_after_retries():
    waits = []
    transport, calls = transport_for(["<html>blocked</html>"])
    result = nsdl.NsdlAdapter(transport=transport, sleep=lambda delay: waits.append(delay)).fetch(ISIN)
    assert result.failure_code == FAILURE_BLOCKED
    assert calls["n"] == nsdl.MAX_ATTEMPTS


def test_v3_count_zero_is_clean_not_found():
    body = json.dumps({"data": [], "count": "0", "status_code": 200})
    transport, calls = transport_for([body])
    result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND
    assert result.isin == ISIN
    assert result.has_facts() is False
    assert calls["n"] == 1


def test_v3_present_count_but_missing_isin_is_not_found():
    other = json.loads(recorded_body())
    other["data"][0]["field_isin"] = "INE999A07XX1"
    transport, _ = transport_for([json.dumps(other)])
    result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_NOT_FOUND


def test_v3_missing_count_is_malformed():
    transport, _ = transport_for(["{\"data\": []}"])
    result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_MALFORMED


def test_v4_fetchresult_and_sources_contract_unchanged():
    transport, _ = transport_for([recorded_body()])
    result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
    assert isinstance(result, FetchResult)
    assert result.failure_code == FAILURE_OK
    assert result.sources
    assert all(source == "NSDL" for source in result.sources.values())
    assert "isin" not in result.sources
    assert result.source_of("company") == "NSDL"


def test_v4_invalid_isin_never_calls_transport():
    transport, calls = transport_for([recorded_body()])
    result = nsdl.NsdlAdapter(transport=transport).fetch("INE002Z0814X")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert calls["n"] == 0


def test_v4_source_error_codes_still_map_through():
    for code in (FAILURE_TIMEOUT, FAILURE_UNREACHABLE, FAILURE_BLOCKED):
        def transport(url, timeout, code=code):
            raise nsdl.SourceError(code)

        result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
        assert result.failure_code == code


def test_v5_state_matrix():
    states = [
        ("live-ok", recorded_body(), FAILURE_OK),
        ("block-page", "<html>blocked</html>", FAILURE_BLOCKED),
        ("not-found", json.dumps({"data": [], "count": "0"}), FAILURE_NOT_FOUND),
    ]
    for label, body, expected in states:
        transport, _ = transport_for([body])
        result = nsdl.NsdlAdapter(transport=transport).fetch(ISIN)
        assert result.failure_code == expected, label

    def timeout_transport(url, timeout):
        raise TimeoutError()

    result = nsdl.NsdlAdapter(transport=timeout_transport).fetch(ISIN)
    assert result.failure_code == FAILURE_TIMEOUT
