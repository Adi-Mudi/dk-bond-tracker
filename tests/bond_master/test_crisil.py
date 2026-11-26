import json
import re
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
from src.bond_master.crisil import (
    LISTING_SERVLET,
    RATING_DOCS_BASE,
    SOURCE_NAME,
    CrisilAdapter,
    rr_record,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_rr():
    return json.loads((FIXTURES / "crisil_rr_listing.json").read_text(encoding="utf-8"))


def load_dr():
    return json.loads((FIXTURES / "crisil_dr_by_isin.json").read_text(encoding="utf-8"))


def make_adapter(pages):
    """pages: dict {url: payload} served by the fake transport."""
    calls = []

    def transport(url, timeout):
        calls.append(url)
        if isinstance(payload_for(url), Exception):
            raise payload_for(url)
        return payload_for(url)

    payload_map = dict(pages)

    def payload_for(url):
        return payload_map.get(url, pages.get("default"))

    adapter = CrisilAdapter(transport=transport)
    return adapter, calls


def test_rr_newest_parses_real_fixture():
    rr = load_rr()
    url0 = f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25"
    adapter, _ = make_adapter({url0: rr, url0.replace("start=0", "start=25"): {"docs": []}})
    result = adapter.fetch_rr_newest(limit=25)
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) == len(rr["docs"])
    first = records[0]
    assert set(first) == {
        "company_code", "company", "industry", "heading", "rating_date",
        "rating_file", "rationale_url", "trans_date", "pr_id", "source",
    }
    assert first["source"] == SOURCE_NAME


def test_rr_record_parses_both_date_formats():
    doc_a = {"companyName": "A", "ratingDate": "Nov 25, 2026", "heading": "h", "prId": 1}
    doc_b = {"companyName": "B", "ratingDate": "June 8, 2017", "heading": "h", "prId": 2}
    rec_a = rr_record(doc_a, [])
    rec_b = rr_record(doc_b, [])
    assert rec_a["rating_date"] == "2026-11-25"
    assert rec_b["rating_date"] == "2017-06-08"


def test_rr_rationale_url_encodes_spaces():
    doc = {"companyName": "X", "ratingFileName": "My Company_November 24, 2026_RR_410880.html", "prId": 9}
    rec = rr_record(doc, [])
    assert "%20" in rec["rationale_url"]
    assert rec["rationale_url"].startswith(RATING_DOCS_BASE)


def test_additive_unknown_key_logged_as_drift():
    doc = {"companyName": "A", "ratingDate": "Nov 25, 2026", "heading": "h", "prId": 1, "SOME_NEW_KEY": 1}
    drift = []
    rec = rr_record(doc, drift)
    assert "SOME_NEW_KEY" in drift


def test_typo_key_showabstarct_is_known_not_drift():
    doc = {"companyName": "A", "ratingDate": "Nov 25, 2026", "heading": "h", "prId": 1,
           "showAbstarct": "x", "abstractTemp": "y"}
    drift = []
    rr_record(doc, drift)
    assert "showAbstarct" not in drift
    assert "abstractTemp" not in drift


def test_rr_newest_stops_at_trans_date_watermark():
    rr = load_rr()
    url = f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25"
    adapter, _ = make_adapter({url: rr, url.replace("start=0", "start=25"): {"docs": []}})
    docs = rr["docs"]
    newest_trans = docs[0]["transDate"]
    result = adapter.fetch_rr_newest(watermark_trans_date="2026-01-01", limit=25)
    assert result["failure_code"] == FAILURE_OK
    for record in result["records"]:
        assert (record["trans_date"] or "") >= "2026-01-01"


def test_rr_pagination_dedups_by_pr_id():
    rr = load_rr()
    url_p0 = f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25"
    url_p1 = f"{LISTING_SERVLET}?cmd=RR&start=25&limit=25"
    adapter, _ = make_adapter({url_p0: rr, url_p1: rr})  # same page served twice
    result = adapter.fetch_rr_newest(limit=25)
    prs = [r["pr_id"] for r in result["records"]]
    assert len(prs) == len(set(prs))


def test_default_watch_parses_dr_fixture():
    dr = load_dr()
    url = f"{LISTING_SERVLET}?cmd=DR&start=0&limit=500"
    adapter, _ = make_adapter({url: dr})
    result = adapter.fetch_default_watch()
    assert result["failure_code"] == FAILURE_OK
    docs = dr["response"]["docs"]
    assert len(result["records"]) == len(docs)
    for record in result["records"]:
        assert record["rating"], "every DR doc carries a rating string"


def test_html_response_is_blocked():
    adapter, _ = make_adapter({f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25": "<html>Access Denied</html>"})
    result = adapter.fetch_rr_newest(limit=25)
    assert result["failure_code"] == FAILURE_BLOCKED


def test_malformed_json_is_malformed():
    adapter, _ = make_adapter({f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25": "not-json{"})
    result = adapter.fetch_rr_newest(limit=25)
    assert result["failure_code"] == FAILURE_MALFORMED


def test_transport_timeout_is_timeout():
    adapter, _ = make_adapter({f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25": TimeoutError("t")})
    result = adapter.fetch_rr_newest(limit=25)
    assert result["failure_code"] == FAILURE_TIMEOUT


def test_transport_connection_error_is_unreachable():
    adapter, _ = make_adapter({f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25": ConnectionError("x")})
    result = adapter.fetch_rr_newest(limit=25)
    assert result["failure_code"] == FAILURE_UNREACHABLE


def test_rationale_fetch_returns_html():
    url = RATING_DOCS_BASE + "SomeDoc.html"
    adapter, _ = make_adapter({url: "<html><body>rationale text</body></html>"})
    result = adapter.fetch_rationale("SomeDoc.html")
    assert result["failure_code"] == FAILURE_OK
    assert "rationale text" in result["html"]


def test_rationale_url_encodes_spaces():
    adapter, _ = make_adapter({})
    url = RATING_DOCS_BASE + "Prakash Auto_Nov 24, 2026_RR.html"
    calls = []

    def transport(u, timeout):
        calls.append(u)
        return "<html>ok</html>"

    adapter._transport = transport
    result = adapter.fetch_rationale("Prakash Auto_Nov 24, 2026_RR.html")
    assert "%20" in calls[0]


def test_match_by_company_filters_and_scores():
    rr = load_rr()
    url = f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25"
    adapter, _ = make_adapter({url: rr})
    target = rr["docs"][0]["companyName"]
    result = adapter.match_by_company(target, rr_page_limit=25)
    assert result["failure_code"] == FAILURE_OK
    assert any(target[:24].casefold() in (r["company"] or "").casefold() for r in result["records"])


def test_match_by_company_not_found():
    adapter, _ = make_adapter({f"{LISTING_SERVLET}?cmd=RR&start=0&limit=25": load_rr()})
    result = adapter.match_by_company("ZZZ Nowhere Limited", rr_page_limit=25)
    assert result["failure_code"] == FAILURE_NOT_FOUND
