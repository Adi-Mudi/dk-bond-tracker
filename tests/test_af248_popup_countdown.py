"""TC-AF-14 (popup) + TC-AF-15 (countdown) acceptance tests - wave P9-2, issue #248."""
import re
from pathlib import Path

from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.views.watch import FETCH_STATES, POSITION_FIELDS

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
WATCH_TEMPLATE = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")


def _nsdl_transport(calls=None):
    body = (FIXTURES / "nsdl_corporate_bond_master.json").read_text(encoding="utf-8")

    def transport(url, timeout):
        if calls is not None:
            calls.append(url)
        return body

    return transport


# === TC-AF-14 (W1) ===
AF14_ISIN = "INE205A07DV2"
AF14_COMPANY = "Acme Infrastructure Ltd"
AF14_COUPON = "8.75"
AF14_MATURITY = "2030-03-31"
AF14_RATING = "AA+"
AF14_NSDL_MASTER = "nsdl_corporate_bond_master.json"
AF14_ROOT = Path(__file__).resolve().parents[1]
AF14_FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
AF14_TEMPLATE = (AF14_ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")
AF14_APPLY_FIELDS = (
    "company",
    "rating",
    "rating_agency",
    "coupon_pct",
    "face_value",
    "issuer_type",
    "payout_cycle",
    "secured",
)


def _af14_transport():
    payload = (AF14_FIXTURES / AF14_NSDL_MASTER).read_text(encoding="utf-8")

    def transport(url, timeout):
        return payload

    return transport


def _af14_client(db_path, body=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = (
        _af14_transport() if body is None else (lambda url, timeout: body)
    )
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client()


def _af14_found_html(db_path):
    return _af14_client(db_path).get(f"/watch?isin={AF14_ISIN}").get_data(as_text=True)


def _af14_popup(html):
    start = html.index('id="fetch-details"')
    end = html.index("table-wrap watch-scroll", start)
    return html[start:end]


def test_tc_af_14_popup_carries_facts_source_badge_and_asof(db_path):
    popup = _af14_popup(_af14_found_html(db_path))
    assert 'id="fetch-details-apply"' in popup
    assert 'id="fetch-details-dismiss"' in popup
    assert 'id="fetch-details-asof"' in popup and "As of" in popup
    for fact in ("company", "coupon", "maturity", "rating"):
        assert f'data-fetch-detail="{fact}"' in popup, fact
    assert AF14_COMPANY in popup
    assert AF14_COUPON in popup
    assert AF14_MATURITY in popup
    assert AF14_RATING in popup
    assert 'data-fetch-source="company">NSDL<' in popup
    assert 'data-fetch-source="coupon">NSDL<' in popup
    assert 'data-fetch-source="maturity">NSDL<' in popup
    assert 'data-fetch-source="rating">NSDL<' in popup


def test_tc_af_14_popup_is_keyed_to_the_fetched_isin(db_path):
    html = _af14_found_html(db_path)
    popup = _af14_popup(html)
    assert f'data-fetch-isin="{AF14_ISIN}"' in popup


def test_tc_af_14_apply_writes_only_instrument_fact_fields(db_path):
    html = _af14_found_html(db_path)
    popup = _af14_popup(html)
    applied = re.findall(r'data-apply-field="([a-z_]+)"', popup)
    assert applied
    assert set(applied) <= set(AF14_APPLY_FIELDS)
    assert "qty" not in applied
    assert set(applied).isdisjoint(POSITION_FIELDS)
    assert re.search(r'data-apply-field="coupon_pct" data-apply-value="8\.75"', popup)
    assert re.search(r'data-apply-field="company" data-apply-value="Acme Infrastructure Ltd"', popup)


def test_tc_af_14_position_facts_stay_empty_in_the_popup_path(db_path):
    html = _af14_found_html(db_path)
    assert 'name="watch_investment" step="any" min="0" placeholder="0.00" value=""' in html
    assert 'name="qty" step="1" min="1" placeholder="1" value=""' in html
    for name in ("amount", "start_date", "end_date", "credit_day"):
        assert f'name="{name}"' not in html, name


def test_tc_af_14_popup_is_absent_when_the_fetch_returns_no_facts(db_path):
    html = _af14_client(db_path, body='{"records": []}').get(
        f"/watch?isin={AF14_ISIN}"
    ).get_data(as_text=True)
    assert 'id="fetch-details"' not in html
    assert 'data-fetch-state="notfound" hidden' not in html


def test_tc_af_14_template_declares_apply_and_dismiss_wiring():
    assert 'id="fetch-details-apply"' in AF14_TEMPLATE
    assert 'id="fetch-details-dismiss"' in AF14_TEMPLATE
    assert "function applyFetchedFacts()" in AF14_TEMPLATE
    assert "function clearFetchedFacts()" in AF14_TEMPLATE
    assert 'applyButton.addEventListener("click"' in AF14_TEMPLATE
    assert 'dismissButton.addEventListener("click"' in AF14_TEMPLATE
    assert 'popup.querySelectorAll("[data-apply-field]")' in AF14_TEMPLATE


def test_tc_af_13_client_half_payload_is_isin_plus_dirty_only():
    assert '"isin=" + encodeURIComponent(isinValue())' in AF14_TEMPLATE
    assert '"dirty=" + encodeURIComponent(Object.keys(dirty).join(","))' in AF14_TEMPLATE
    assert "Object.keys(dirty).forEach" in AF14_TEMPLATE
    assert 'query += encodeURIComponent(element.name)' not in AF14_TEMPLATE


def test_tc_af_13_client_half_isin_change_invalidates_facts_before_response():
    assert "function invalidateOnIsinChange()" in AF14_TEMPLATE
    assert 'isin.addEventListener("input", invalidateOnIsinChange)' in AF14_TEMPLATE
    assert "closePopup();" in AF14_TEMPLATE
    assert "clearFetchedFacts();" in AF14_TEMPLATE
    assert 'showState("idle")' in AF14_TEMPLATE
    assert 'data-fetch-isin="{{ fetch.isin }}"' in AF14_TEMPLATE


# === end TC-AF-14 (W1) ===
# === TC-AF-15 (W2) ===

COUNTDOWN_ISIN = "INE205A07DW3"
FOUND_ISIN = "INE205A07DV2"
COUNTDOWN_ID = "c-isin-countdown"
COUNTDOWN_SECONDS_ID = "c-isin-countdown-seconds"
COUNTDOWN_FULL = 60
PACING_COPY = "free, unofficial source"
POPUP_TOKENS = ("popup", "dialog", "modal", "overlay")


def _watch_client(db_path, transport=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    if transport is not None:
        app.config["BOND_MASTER_TRANSPORT"] = transport
    return app.test_client(), app


def _warm_cooldown_client(db_path, transport=None):
    client, app = _watch_client(db_path, transport)
    cache = BondMasterCache(db_path)
    cache.begin_refresh()
    app.extensions["bond_master_cache"] = cache
    app.extensions.pop("bond_master_service", None)
    return client, cache


def _countdown_script():
    blocks = re.findall(r"<script>(.*?)</script>", WATCH_TEMPLATE, re.S)
    matches = [block for block in blocks if COUNTDOWN_ID in block and "setInterval" in block]
    assert len(matches) == 1
    return matches[0]


def _countdown_chip_visible(html):
    return re.search(r'id="' + COUNTDOWN_ID + r'"[^>]*\shidden', html) is None


def test_tc_af_15_countdown_renders_60_to_0_with_pacing_copy(db_path):
    client, _ = _warm_cooldown_client(db_path, _nsdl_transport())
    html = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
    assert 'data-fetch-state="offline" hidden' not in html
    assert 'id="' + COUNTDOWN_ID + '"' in html
    assert _countdown_chip_visible(html) is True
    assert 'data-countdown-seconds="' + str(COUNTDOWN_FULL) + '"' in html
    assert 'id="' + COUNTDOWN_SECONDS_ID + '">' + str(COUNTDOWN_FULL) + "<" in html
    assert PACING_COPY in html
    assert "paces lookups" in html
    script = _countdown_script()
    assert "remaining -= 1" in script
    assert "window.setInterval" in script
    assert "window.clearInterval" in script
    assert "data-countdown-seconds" in script


def test_tc_af_15_countdown_is_hidden_when_the_cooldown_blocks_nothing(db_path):
    idle = _watch_client(db_path)[0].get("/watch").get_data(as_text=True)
    assert _countdown_chip_visible(idle) is False
    client, app = _watch_client(db_path, _nsdl_transport())
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    app.extensions.pop("bond_master_service", None)
    found = client.get("/watch", query_string={"isin": FOUND_ISIN}).get_data(as_text=True)
    assert 'data-fetch-state="found" hidden' not in found
    assert _countdown_chip_visible(found) is False


def test_tc_af_15_blocked_render_seeds_the_true_remaining_and_resets_on_claim(db_path):
    now = [1000000.0]
    client, app = _watch_client(db_path, _nsdl_transport())
    cache = BondMasterCache(db_path, clock=lambda: now[0])
    cache.begin_refresh()
    app.extensions["bond_master_cache"] = cache
    app.extensions.pop("bond_master_service", None)

    fresh = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
    assert _countdown_chip_visible(fresh) is True
    assert 'data-countdown-seconds="' + str(COUNTDOWN_FULL) + '"' in fresh
    assert 'id="' + COUNTDOWN_SECONDS_ID + '">' + str(COUNTDOWN_FULL) + "<" in fresh

    now[0] += 30
    mid = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
    assert _countdown_chip_visible(mid) is True
    assert 'data-countdown-seconds="30"' in mid
    assert 'id="' + COUNTDOWN_SECONDS_ID + '">30<' in mid

    now[0] += 60
    cache.begin_refresh()
    reclaim = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
    assert _countdown_chip_visible(reclaim) is True
    assert 'data-countdown-seconds="' + str(COUNTDOWN_FULL) + '"' in reclaim


def test_tc_af_15_countdown_survives_popup_open_apply_dismiss():
    start = WATCH_TEMPLATE.index('for="c-isin"')
    end = WATCH_TEMPLATE.index('for="c-rating"')
    chip = WATCH_TEMPLATE.index('id="' + COUNTDOWN_ID + '"')
    assert start < chip < end
    assert chip > WATCH_TEMPLATE.index('id="c-fetch-states"')
    script = _countdown_script()
    assert COUNTDOWN_ID in script
    assert COUNTDOWN_SECONDS_ID in script
    lowered = script.lower()
    for token in POPUP_TOKENS:
        assert token not in lowered, token


def test_tc_af_15_no_source_request_is_made_while_the_countdown_runs(db_path):
    calls = []
    client, _ = _warm_cooldown_client(db_path, _nsdl_transport(calls))
    for _ in range(2):
        html = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
        assert _countdown_chip_visible(html) is True
    assert calls == []


def test_tc_af_15_render_keeps_exactly_the_six_fetch_states(db_path):
    client, _ = _warm_cooldown_client(db_path, _nsdl_transport())
    html = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
    assert re.findall(r'data-fetch-state="([a-z]+)"', html) == list(FETCH_STATES)
    assert re.findall(r'data-fetch-state="([a-z]+)"', WATCH_TEMPLATE) == list(FETCH_STATES)
