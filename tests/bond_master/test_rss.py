from pathlib import Path

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.rss import FEEDS, RssAdapter, parse_pub_date, parse_rss

FIXTURES = Path(__file__).parent / "fixtures"

RBI_URL = FEEDS["rbi_pressreleases"]["url"]
SEBI_URL = FEEDS["sebi"]["url"]
BSE_URL = FEEDS["bse_notices"]["url"]
NOTIF_URL = FEEDS["rbi_notifications"]["url"]


def load(name):
    return (FIXTURES / name).read_bytes()


def make_adapter(pages, feeds=None):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        payload = pages.get(url)
        if isinstance(payload, Exception):
            raise payload
        if payload is None:
            raise AssertionError(f"unexpected URL: {url}")
        return payload

    return RssAdapter(transport=transport, feeds=feeds), calls


def test_rbi_fixture_parses():
    adapter, calls = make_adapter({RBI_URL: load("rbi_rss.xml")})
    result = adapter.fetch_feed("rbi_pressreleases")
    assert result["failure_code"] == FAILURE_OK
    assert calls == [RBI_URL]
    records = result["records"]
    assert len(records) == 10
    first = records[0]
    assert first["source"] == "RBI"
    assert first["feed"] == "rbi_pressreleases"
    assert first["title"]
    assert first["link"]
    assert first["pub_date"].startswith("2026-11-26")
    assert first["as_of"]
    assert result["sha256"]


def test_sebi_fixture_parses_odd_pubdate():
    adapter, _ = make_adapter({SEBI_URL: load("sebi_rss.xml")})
    result = adapter.fetch_feed("sebi")
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) == 10
    first = records[0]
    assert first["source"] == "SEBI"
    assert first["pub_date"] == "2026-11-26T00:00:00+05:30"
    assert first["title"]
    assert first["as_of"]


def test_bse_notices_guid_and_pdf_flag():
    adapter, _ = make_adapter({BSE_URL: load("bse_notices.xml")})
    result = adapter.fetch_feed("bse_notices")
    assert result["failure_code"] == FAILURE_OK
    records = result["records"]
    assert len(records) == 10
    first = records[0]
    assert first["source"] == "BSE"
    assert first["guid"].startswith("https://")
    assert first["is_pdf"] is True
    assert first["pub_date"].startswith("2026-11-26")
    assert first["as_of"]


def test_zero_items_is_ok_not_malformed():
    body = b'<?xml version="1.0"?><rss version="2.0"><channel><title>x</title></channel></rss>'
    records = parse_rss(body, "SEBI", "sebi")
    assert records == []


def test_html_body_is_blocked():
    adapter, _ = make_adapter({RBI_URL: "<html>Access Denied</html>"})
    result = adapter.fetch_feed("rbi_pressreleases")
    assert result["failure_code"] == FAILURE_BLOCKED
    assert result["records"] == []


def test_garbage_body_is_malformed():
    adapter, _ = make_adapter({SEBI_URL: "not xml at all"})
    assert adapter.fetch_feed("sebi")["failure_code"] == FAILURE_MALFORMED


def test_timeout_is_timeout():
    adapter, _ = make_adapter({BSE_URL: TimeoutError("t")})
    assert adapter.fetch_feed("bse_notices")["failure_code"] == FAILURE_TIMEOUT


def test_connection_error_is_unreachable():
    adapter, _ = make_adapter({RBI_URL: ConnectionError("x")})
    assert adapter.fetch_feed("rbi_pressreleases")["failure_code"] == FAILURE_UNREACHABLE


def test_fetch_all_isolates_one_failing_feed():
    adapter, _ = make_adapter({
        RBI_URL: load("rbi_rss.xml"),
        NOTIF_URL: TimeoutError("t"),
        SEBI_URL: load("sebi_rss.xml"),
        BSE_URL: load("bse_notices.xml"),
    })
    results = adapter.fetch_all()
    assert results["rbi_pressreleases"]["failure_code"] == FAILURE_OK
    assert results["rbi_notifications"]["failure_code"] == FAILURE_TIMEOUT
    assert results["sebi"]["failure_code"] == FAILURE_OK
    assert results["bse_notices"]["failure_code"] == FAILURE_OK
    assert results["rbi_pressreleases"]["records"]
    assert results["rbi_notifications"]["records"] == []


def test_parse_pub_date_formats():
    assert parse_pub_date("Thu, 26 Nov 2026 19:25:00").startswith("2026-11-26")
    assert parse_pub_date("Thu, 26 Nov 2026 16:37:16 GMT").startswith("2026-11-26")
    assert parse_pub_date("26 Nov, 2026 +0530") == "2026-11-26T00:00:00+05:30"
    assert parse_pub_date("26-Nov-2026 22:12:08") == "2026-11-26T22:12:08"
    assert parse_pub_date("not a date") is None
    assert parse_pub_date(None) is None


def test_namespace_tags_are_stripped():
    body = (
        b'<?xml version="1.0"?>'
        b'<rss xmlns:dc="http://purl.org/dc/elements/1.1/"><channel>'
        b'<item><title>T</title><link>https://x.example/a</link>'
        b'<dc:creator>Author</dc:creator><pubDate>Thu, 26 Nov 2026 10:00:00</pubDate>'
        b'</item></channel></rss>'
    )
    records = parse_rss(body, "RBI", "rbi_pressreleases")
    assert len(records) == 1
    assert records[0]["title"] == "T"
