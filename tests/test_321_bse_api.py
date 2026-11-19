import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.bond_master import bse, service, snapshot
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    SOURCE_PRIORITY,
    FetchResult,
)

FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
RECORDED = FIXTURES / "bse_list_of_scrip_debt.json"
RECORDED_LIVE = FIXTURES / "bse_list_of_scrip_debt_live.json"
ISIN = "INE205A07DZ6"
OTHER_ISIN = "INE205A07E76"
PARTIAL_ISIN = "INE205A07F82"
LIVE_ISIN = "INE775A08105"
LIVE_COMPANY = "Samvardhana Motherson International Limited"
EXPECTED_COMPANY = "Zenith Ports Ltd"


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


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return b"[]"


def http_error(code):
    return urllib.error.HTTPError(bse.BSE_LIST_OF_SCRIP_URL, code, "denied", {}, None)


class FingerprintedGet:
    def __init__(self, opener=None):
        self.opener = opener
        self.calls = []
        self.primed = False

    def __call__(self, url, timeout=bse.DEFAULT_TIMEOUT):
        if self.opener is None:
            jar = http.cookiejar.CookieJar()
            self.opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(jar)
            )

        def open_target(target):
            request = urllib.request.Request(target, headers=bse.REQUEST_HEADERS)
            self.calls.append(
                (request.full_url, {key.lower(): value for key, value in request.header_items()})
            )
            if hasattr(self.opener, "open"):
                return self.opener.open(request, timeout=timeout)
            return self.opener(request, timeout=timeout)

        try:
            if not self.primed:
                with open_target(bse.COOKIE_PRIME_URL) as response:
                    response.read()
                self.primed = True
            with open_target(url) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                raise bse.SourceError(FAILURE_BLOCKED) from exc
            if exc.code == 404:
                raise bse.SourceError(FAILURE_NOT_FOUND) from exc
            raise ConnectionError(f"HTTP error {exc.code} from BSE") from exc
        except urllib.error.URLError as exc:
            raise ConnectionError(f"could not reach BSE: {exc.reason}") from exc


def test_v1_recorded_fixture_returns_real_bse_facts():
    seen = []
    transport, calls = transport_for([recorded_body()], seen=seen)
    result = bse.BseAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == EXPECTED_COMPANY
    assert result.coupon == 10.25
    assert result.payout_cycle == "annual"
    assert result.face_value == 100000.0
    assert result.rating == "AA"
    assert result.rating_agency == "CARE"
    assert result.issuer_type == "ncd"
    assert result.secured == 1
    assert result.listing_status == "listed"
    assert result.maturity == "2032-05-10"
    assert result.has_facts() is True
    assert calls["n"] == 1
    url = seen[0][0]
    assert url.startswith("https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?")
    assert "segment=Debentures%20and%20Bonds" in url
    assert ".csv" not in url
    assert "/download/" not in url


def test_v1_recorded_live_response_maps_real_bse_facts():
    transport, _ = transport_for(
        [RECORDED_LIVE.read_text(encoding="utf-8")]
    )
    result = bse.BseAdapter(transport=transport).fetch(LIVE_ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == LIVE_COMPANY
    assert result.face_value == 100000.0
    assert result.listing_status == "listed"
    assert result.issuer_type == "debentures and bonds"
    assert result.coupon is None
    assert result.rating is None
    assert result.maturity is None
    assert result.source_of("company") == "BSE"


def test_v1_default_endpoint_and_browser_fingerprint():
    assert bse.BSE_LIST_OF_SCRIP_URL == (
        "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w"
    )
    headers = bse.REQUEST_HEADERS
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert headers["Referer"] == "https://www.bseindia.com/"
    assert headers["Origin"] == "https://www.bseindia.com/"
    assert headers["Accept-Language"] == "en-US,en;q=0.5"
    assert headers["Accept"] == "application/json, text/plain, */*"
    assert headers["Sec-Fetch-Site"] == "same-site"
    assert bse.COOKIE_PRIME_URL == "https://www.bseindia.com/"


@pytest.mark.skipif(
    os.environ.get("BSE_LIVE") != "1",
    reason="live smoke is opt-in; set BSE_LIVE=1 to hit api.bseindia.com",
)
def test_v1_live_smoke_with_browser_fingerprint():
    result = bse.BseAdapter(transport=FingerprintedGet()).fetch(LIVE_ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == LIVE_COMPANY
    assert result.face_value == 100000.0
    assert result.listing_status == "listed"


def test_v2_wrapped_data_envelope_is_parsed():
    document = {"data": json.loads(recorded_body()), "count": "3"}
    transport, _ = transport_for([json.dumps(document)])
    result = bse.BseAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == EXPECTED_COMPANY


def test_v2_alias_keys_and_percent_and_legacy_date_are_mapped():
    payload = json.dumps(
        [
            {
                "isin": PARTIAL_ISIN,
                "name": "Alias Issuer Ltd",
                "coupon_rate": "8.75%",
                "interest_frequency": "yearly",
                "face_value": "10,000",
                "credit_rating": "CRISIL AA-",
                "security_type": "NCD",
                "secured": "1",
                "listing_status": "Active",
                "maturity_date": "05-Sep-2030",
            }
        ]
    )
    transport, _ = transport_for([payload])
    result = bse.BseAdapter(transport=transport).fetch(PARTIAL_ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == "Alias Issuer Ltd"
    assert result.coupon == 8.75
    assert result.payout_cycle == "annual"
    assert result.face_value == 10000.0
    assert result.rating == "AA-"
    assert result.rating_agency == "CRISIL"
    assert result.issuer_type == "ncd"
    assert result.secured == 1
    assert result.listing_status == "listed"
    assert result.maturity == "2030-09-05"


def test_v2_bytes_payload_is_decoded():
    transport, _ = transport_for([recorded_body().encode("utf-8")])
    result = bse.BseAdapter(transport=transport).fetch(OTHER_ISIN)
    assert result.failure_code == FAILURE_OK
    assert result.company == "Omega Telecom Ltd"


def test_v3_http_403_maps_to_blocked_without_crash():
    def fake_opener(request, timeout=None):
        raise http_error(403)

    getter = FingerprintedGet(opener=fake_opener)
    result = bse.BseAdapter(transport=getter).fetch(ISIN)
    assert result.failure_code == FAILURE_BLOCKED
    assert result.has_facts() is False
    assert getter.calls[0][0] == bse.COOKIE_PRIME_URL


def test_v3_http_404_maps_to_not_found():
    def fake_opener(request, timeout=None):
        raise http_error(404)

    getter = FingerprintedGet(opener=fake_opener)
    assert bse.BseAdapter(transport=getter).fetch(ISIN).failure_code == FAILURE_NOT_FOUND


def test_v3_http_500_maps_to_unreachable():
    def fake_opener(request, timeout=None):
        raise http_error(500)

    getter = FingerprintedGet(opener=fake_opener)
    assert bse.BseAdapter(transport=getter).fetch(ISIN).failure_code == FAILURE_UNREACHABLE


def test_v3_cookie_prime_hits_base_before_the_api():
    getter = FingerprintedGet(opener=lambda request, timeout=None: FakeResponse())
    getter(bse.build_url(), timeout=3.0)
    assert getter.calls[0][0] == bse.BSE_BASE_URL
    assert getter.calls[1][0].startswith(bse.BSE_LIST_OF_SCRIP_URL)
    assert getter.calls[0][1]["referer"] == bse.BSE_BASE_URL
    assert getter.calls[1][1]["user-agent"].startswith("Mozilla/5.0")


def test_v3_waf_html_page_is_blocked():
    transport, _ = transport_for(["<html><body>Akamai Access Denied</body></html>"])
    result = bse.BseAdapter(transport=transport).fetch(ISIN)
    assert result.failure_code == FAILURE_BLOCKED
    assert result.has_facts() is False


def test_v3_transport_exceptions_are_contained():
    cases = [
        (TimeoutError("slow"), FAILURE_TIMEOUT),
        (FileNotFoundError("404"), FAILURE_NOT_FOUND),
        (OSError("refused"), FAILURE_UNREACHABLE),
        (RuntimeError("boom"), FAILURE_UNREACHABLE),
        (bse.SourceError(FAILURE_BLOCKED), FAILURE_BLOCKED),
    ]
    for error, expected in cases:
        def transport(url, timeout, error=error):
            raise error

        result = bse.BseAdapter(transport=transport).fetch(ISIN)
        assert result.failure_code == expected, type(error).__name__
        assert result.isin == ISIN


def test_v4_fetchresult_and_sources_contract_unchanged():
    transport, _ = transport_for([recorded_body()])
    result = bse.BseAdapter(transport=transport).fetch(ISIN)
    assert isinstance(result, FetchResult)
    assert result.failure_code == FAILURE_OK
    assert result.sources
    assert all(source == "BSE" for source in result.sources.values())
    assert "isin" not in result.sources
    assert result.source_of("company") == "BSE"
    assert set(result.facts()) == {
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


def test_v4_invalid_isin_never_calls_the_transport():
    transport, calls = transport_for([recorded_body()])
    result = bse.BseAdapter(transport=transport).fetch("INE205A07DZX")
    assert result.failure_code == FAILURE_INVALID_ISIN
    assert calls["n"] == 0


def test_v4_snapshot_fallback_and_wiring_intact():
    assert "BSE" in SOURCE_PRIORITY
    assert service._ADAPTER_CLASS["BSE"] == "BseAdapter"
    assert len(snapshot.rows()) > 0
    assert snapshot.snapshot_lookup("IN0019790024") is not None


def test_v5_state_matrix():
    states = [
        ("live-ok", recorded_body(), FAILURE_OK),
        ("waf-html", "<!DOCTYPE html><html>blocked</html>", FAILURE_BLOCKED),
        ("empty", "", FAILURE_MALFORMED),
        ("bad-json", "{broken", FAILURE_PARSE_ERROR),
        ("empty-list", "[]", FAILURE_NOT_FOUND),
    ]
    for label, body, expected in states:
        transport, _ = transport_for([body])
        result = bse.BseAdapter(transport=transport).fetch(ISIN)
        assert result.failure_code == expected, label
