from pathlib import Path

import pytest

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.icra import (
    ALL_RATIONALES_URL,
    RATING_DETAILS_URL,
    IcraAdapter,
    parse_rationales,
    parse_rating_details,
)

FIXTURES = Path(__file__).parent / "fixtures"
RATIIONALES_FIXTURE = FIXTURES / "icra_rationales_p1.html"
DETAILS_FIXTURE = FIXTURES / "icra_rating_details.html"
COMPANY_ID = "18058"
DETAILS_URL = RATING_DETAILS_URL + COMPANY_ID


def make_adapter(pages):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        payload = pages.get(url)
        if isinstance(payload, Exception):
            raise payload
        if payload is None:
            raise AssertionError(f"unexpected URL: {url}")
        return payload

    return IcraAdapter(transport=transport), calls


def load_rationales():
    return RATIIONALES_FIXTURE.read_text(encoding="utf-8")


def load_details():
    return DETAILS_FIXTURE.read_text(encoding="utf-8")


def test_rationales_parses_real_fixture():
    records = parse_rationales(load_rationales())
    assert len(records) >= 8
    first = records[0]
    assert first["source"] == "ICRA"
    assert first["rationale_id"]
    assert first["rationale_url"].endswith("Id=" + first["rationale_id"])
    assert first["pdf_url"].endswith("Id=" + first["rationale_id"])
    assert first["title"]
    assert first["company"] == "AMNS GANDHIDHAM LIMITED (Formerly known as Indian Steel Corporation Limited)"
    assert first["date"] == "2026-11-26"
    assert first["category"] == "Corporate Debt Rating"
    assert first["company_id"]
    assert first["as_of"]


def test_rationales_dedups_by_id():
    body = load_rationales()
    records = parse_rationales(body + body)
    ids = [r["rationale_id"] for r in records]
    assert len(ids) == len(set(ids))


def test_rationales_empty_page_is_not_found():
    adapter, _ = make_adapter({ALL_RATIONALES_URL: "<html><body><table></table></body></html>"})
    result = adapter.fetch_rationales_newest()
    assert result["failure_code"] == FAILURE_NOT_FOUND
    assert result["records"] == []


def test_rating_details_parses_real_fixture():
    records = parse_rating_details(load_details(), company_id=COMPANY_ID)
    assert len(records) >= 2
    ncd = next(r for r in records if "Non-Convertible" in r["instrument"])
    assert ncd["source"] == "ICRA"
    assert ncd["company_id"] == COMPANY_ID
    assert ncd["company"] is None
    assert ncd["agency"] == "ICRA"
    assert ncd["rating"] == "BBB+"
    assert ncd["outlook"] == "Positive"
    assert ncd["as_of"]


def test_rating_details_no_rating_rows_is_not_found():
    with pytest.raises(Exception) as exc:
        parse_rating_details("<html><body><p>no ratings</p></body></html>", company_id="1")
    assert getattr(exc.value, "failure_code", None) == FAILURE_NOT_FOUND


def test_fetch_rating_details_requires_numeric_id():
    adapter, calls = make_adapter({})
    result = adapter.fetch_rating_details("abc")
    assert result["failure_code"] == FAILURE_NOT_FOUND
    assert calls == []


def test_fetch_rating_details_ok():
    adapter, calls = make_adapter({DETAILS_URL: load_details()})
    result = adapter.fetch_rating_details(COMPANY_ID)
    assert result["failure_code"] == FAILURE_OK
    assert calls == [DETAILS_URL]
    assert result["records"]


def test_html_challenge_is_blocked():
    adapter, _ = make_adapter({ALL_RATIONALES_URL: "<html><body>Just a moment... cf-chl</body></html>"})
    assert adapter.fetch_rationales_newest()["failure_code"] == FAILURE_BLOCKED


def test_non_html_body_is_malformed():
    adapter, _ = make_adapter({ALL_RATIONALES_URL: "totally not markup"})
    assert adapter.fetch_rationales_newest()["failure_code"] == FAILURE_MALFORMED


def test_timeout_is_timeout():
    adapter, _ = make_adapter({ALL_RATIONALES_URL: TimeoutError("t")})
    assert adapter.fetch_rationales_newest()["failure_code"] == FAILURE_TIMEOUT


def test_connection_error_is_unreachable():
    adapter, _ = make_adapter({DETAILS_URL: ConnectionError("x")})
    assert adapter.fetch_rating_details(COMPANY_ID)["failure_code"] == FAILURE_UNREACHABLE
