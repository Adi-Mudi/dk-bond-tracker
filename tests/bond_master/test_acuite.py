from pathlib import Path

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.acuite import (
    LIVERATINGS_URL,
    AcuiteAdapter,
    parse_company_details,
    parse_liveratings,
)

FIXTURES = Path(__file__).parent / "fixtures"
LIST_FIXTURE = FIXTURES / "acuite_liveratings.html"
DETAILS_FIXTURE = FIXTURES / "acuite_company_details.html"
DETAIL_URL = "https://connect.acuite.in/fcompany-details/GOLDEN_FOOD_PRODUCTS/26th_Nov_26"


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

    return AcuiteAdapter(transport=transport), calls


def load_list():
    return LIST_FIXTURE.read_text(encoding="utf-8")


def load_details():
    return DETAILS_FIXTURE.read_text(encoding="utf-8")


def test_liveratings_parses_real_fixture():
    records = parse_liveratings(load_list())
    assert len(records) >= 5
    first = records[0]
    assert first["source"] == "Acuite"
    assert first["master_id"]
    assert first["date"] == "2026-11-26"
    assert first["entity"]
    assert first["entity_slug"]
    assert first["detail_url"].startswith("https://connect.acuite.in/fcompany-details/")
    assert first["as_of"]


def test_liveratings_dedups_by_master_id():
    body = load_list()
    records = parse_liveratings(body + body)
    ids = [r["master_id"] for r in records]
    assert len(ids) == len(set(ids))


def test_liveratings_fetch_ok():
    adapter, calls = make_adapter({LIVERATINGS_URL: load_list()})
    result = adapter.fetch_liveratings_newest()
    assert result["failure_code"] == FAILURE_OK
    assert calls == [LIVERATINGS_URL]
    assert result["records"]


def test_liveratings_empty_is_not_found():
    adapter, _ = make_adapter({LIVERATINGS_URL: "<html><body><table></table></body></html>"})
    result = adapter.fetch_liveratings_newest()
    assert result["failure_code"] == FAILURE_NOT_FOUND
    assert result["records"] == []


def test_company_details_parses_rating_rows():
    records, isin_records = parse_company_details(load_details())
    assert len(records) >= 1
    row = records[0]
    assert row["source"] == "Acuite"
    assert row["instrument"] == "Bank Loan Ratings"
    assert row["quantum_sebi"] == 0.0
    assert row["quantum_other"] == 12.0
    assert row["long_term_rating"].startswith("ACUITE")
    assert row["long_term_action"] == "Reaffirmed"
    assert "not co-operating" in row["long_term_flag"]
    assert row["short_term_rating"] is None
    assert row["regulated_by"] == "RBI"
    assert row["as_of"]
    assert isin_records == [] or all(r["isin"] for r in isin_records)


def test_company_details_fetch_ok():
    adapter, calls = make_adapter({DETAIL_URL: load_details()})
    result = adapter.fetch_company_details(DETAIL_URL)
    assert result["failure_code"] == FAILURE_OK
    assert calls == [DETAIL_URL]
    assert result["records"]


def test_company_details_rejects_foreign_url():
    adapter, calls = make_adapter({})
    result = adapter.fetch_company_details("https://evil.example/fcompany-details/X/Y")
    assert result["failure_code"] == FAILURE_NOT_FOUND
    assert calls == []


def test_company_details_no_ratings_is_not_found():
    try:
        parse_company_details("<html><body><p>nothing</p></body></html>")
        raised = False
    except Exception as exc:
        raised = True
        assert getattr(exc, "failure_code", None) == FAILURE_NOT_FOUND
    assert raised


def test_cloudflare_challenge_is_blocked():
    adapter, _ = make_adapter({LIVERATINGS_URL: "<html><body>Just a moment... cf-chl</body></html>"})
    assert adapter.fetch_liveratings_newest()["failure_code"] == FAILURE_BLOCKED


def test_garbage_body_is_malformed():
    adapter, _ = make_adapter({LIVERATINGS_URL: "not markup at all"})
    assert adapter.fetch_liveratings_newest()["failure_code"] == FAILURE_MALFORMED


def test_timeout_is_timeout():
    adapter, _ = make_adapter({LIVERATINGS_URL: TimeoutError("t")})
    assert adapter.fetch_liveratings_newest()["failure_code"] == FAILURE_TIMEOUT


def test_connection_error_is_unreachable():
    adapter, _ = make_adapter({DETAIL_URL: ConnectionError("x")})
    assert adapter.fetch_company_details(DETAIL_URL)["failure_code"] == FAILURE_UNREACHABLE
