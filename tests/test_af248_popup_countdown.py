"""TC-AF-14 (popup) + TC-AF-15 (countdown) acceptance tests - wave P9-2, issue #248."""
import re
from pathlib import Path

from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.views.watch import FETCH_STATES

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


def test_tc_af_15_each_blocked_render_resets_the_chip_to_a_full_60(db_path):
    client, _ = _warm_cooldown_client(db_path, _nsdl_transport())
    for _ in range(2):
        html = client.get("/watch", query_string={"isin": COUNTDOWN_ISIN}).get_data(as_text=True)
        assert _countdown_chip_visible(html) is True
        assert 'id="' + COUNTDOWN_SECONDS_ID + '">' + str(COUNTDOWN_FULL) + "<" in html
        assert 'data-countdown-seconds="' + str(COUNTDOWN_FULL) + '"' in html


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
