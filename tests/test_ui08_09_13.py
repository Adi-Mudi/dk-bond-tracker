import re
from pathlib import Path

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn

ROOT = Path(__file__).resolve().parents[1]
BASE = (ROOT / "src" / "templates" / "base.html").read_text(encoding="utf-8")
GUIDE_CSS = (ROOT / "src" / "static" / "guide.css").read_text(encoding="utf-8")
GUIDE_JS = (ROOT / "src" / "static" / "guide.js").read_text(encoding="utf-8")
TOOLTIP_TPL = (ROOT / "src" / "templates" / "_tooltip.html").read_text(encoding="utf-8")

PAGES = ("/", "/portfolio", "/watch", "/goals", "/notifications", "/settings")
GUIDE_TITLES = {
    "/": "Dashboard guide",
    "/portfolio": "Portfolio guide",
    "/watch": "Watchlist guide",
    "/goals": "Goals guide",
    "/notifications": "Alerts guide",
    "/settings": "Settings guide",
}
DISCLAIMER_PHRASES = (
    "information-only",
    "not investment advice",
    "no advisory relationship",
    "risk of loss",
)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_holding(db_path, company, isin):
    with get_conn(db_path) as conn:
        return add_bond(conn, company, isin, "2026-01-01", 12)


def seed_watching(db_path, company, isin, rating="AA"):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, rating, watch_state) "
            "VALUES (?, ?, ?, ?, 'watching')",
            (company, isin, company, rating),
        )
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def test_ui08_bulb_present_on_every_page_with_that_page_guide(client, db_path):
    for path in PAGES:
        html = client.get(path).get_data(as_text=True)
        assert 'id="guideBtn"' in html, path
        assert 'id="pageGuide"' in html, path
        assert 'aria-label="Page guide"' in html, path
        assert GUIDE_TITLES[path] in html, path


def test_ui08_guide_sits_in_the_same_topbar_spot(client, db_path):
    for path in PAGES:
        html = client.get(path).get_data(as_text=True)
        assert html.index('id="guideBtn"') > html.index('id="searchBtn"'), path
        assert html.index('id="guideBtn"') < html.index('id="overflowToggle"'), path


def test_ui08_watch_guide_explains_blocking_rules_in_plain_language(client, db_path):
    html = client.get("/watch").get_data(as_text=True)
    assert "guide-rule guide-blocking" in html
    assert "One ISIN, one entry" in html
    assert "Investment grade only" in html
    assert "Move to Portfolio" in html


def test_ui08_tooltip_a11y_attributes_present(client, db_path):
    html = client.get("/").get_data(as_text=True)
    assert html.count('role="tooltip"') >= 4
    assert html.count('aria-describedby="tip-') >= 4
    for kind in ("blocking", "status", "howto", "warning"):
        assert f'tip-bubble tip-{kind}"' in html, kind
    assert 'role="tooltip"' in TOOLTIP_TPL
    assert 'aria-describedby="tip-' in TOOLTIP_TPL


def test_ui08_tooltip_tints_use_darker_text_tokens(client, db_path):
    for token in (
        "--tip-red-bg",
        "--tip-red-text",
        "--tip-green-bg",
        "--tip-green-text",
        "--tip-blue-bg",
        "--tip-blue-text",
        "--tip-amber-bg",
        "--tip-amber-text",
    ):
        assert token in GUIDE_CSS, token
    assert ".tip-bubble.tip-blocking { background: var(--tip-red-bg);" in GUIDE_CSS
    assert "color: var(--tip-red-text);" in GUIDE_CSS
    assert ".tip-bubble.tip-status" in GUIDE_CSS
    assert ".tip-bubble.tip-howto" in GUIDE_CSS
    assert ".tip-bubble.tip-warning" in GUIDE_CSS
    html = client.get("/").get_data(as_text=True)
    for word in ("Blocking rule", "Status rule", "How to", "Warning"):
        assert word in html, word


def test_ui08_tooltips_open_on_focus_and_dismiss_on_escape(client, db_path):
    assert ":focus + .tip-bubble" in GUIDE_CSS
    assert ":hover .tip-bubble" in GUIDE_CSS
    assert "Escape" in GUIDE_JS
    assert "tip-open" in GUIDE_JS
    html = client.get("/").get_data(as_text=True)
    texts = re.findall(r'<span class="tip-text">(.*?)</span>', html, re.S)
    assert texts
    for text in texts:
        assert len(re.sub(r"<[^>]+>", "", text).strip()) <= 150


def test_ui09_search_groups_holdings_and_watchlist_with_chips(client, db_path):
    holding_id = seed_holding(db_path, "Alpha Holdings Ltd", "INE8000A1001")
    watch_id = seed_watching(db_path, "Alpha Watched Ltd", "INE8000A1002")
    html = client.get("/search?q=Alpha").get_data(as_text=True)
    assert 'data-source="Holdings"' in html
    assert 'data-source="Watchlist"' in html
    assert f'href="/portfolio/{holding_id}"' in html
    assert f'href="/watch#candidate-{watch_id}"' in html
    assert "chip-ongoing" in html
    assert "chip-watching" in html
    assert "2 matches" in html


def test_ui09_search_matches_partial_isin(client, db_path):
    seed_holding(db_path, "Isin Match Co", "INE8123456789")
    html = client.get("/search?q=8123456").get_data(as_text=True)
    assert "Isin Match Co" in html
    assert 'data-source="Holdings"' in html


def test_ui09_search_designed_no_results_state(client, db_path):
    seed_holding(db_path, "Quiet Co", "INE8000A1004")
    html = client.get("/search?q=nothingmatcheshere").get_data(as_text=True)
    assert 'id="search-no-results"' in html
    assert "No matches for" in html
    assert "data-source=" not in html


def test_ui09_search_prompt_before_typing(client, db_path):
    html = client.get("/search").get_data(as_text=True)
    assert 'id="search-prompt"' in html
    assert 'id="searchPageInput"' in html


def test_ui09_topbar_search_combobox_and_keyboard_nav(client, db_path):
    html = client.get("/").get_data(as_text=True)
    assert 'role="combobox"' in html
    assert 'aria-controls="searchResults"' in html
    assert 'aria-autocomplete="list"' in html
    assert 'id="searchResults"' in html
    assert 'role="listbox"' in html
    assert 'id="searchPanel"' in html
    assert 'id="searchBtn"' in html
    assert "aria-activedescendant" in GUIDE_JS
    assert "ArrowDown" in GUIDE_JS and "ArrowUp" in GUIDE_JS
    assert "/search?format=json" in GUIDE_JS


def test_ui09_search_json_endpoint_groups_by_source(client, db_path):
    seed_holding(db_path, "Json Co", "INE8000A1003")
    seed_watching(db_path, "Json Watch Co", "INE8000A1005")
    payload = client.get("/search?q=Json&format=json").get_json()
    assert payload["total"] == 2
    assert [group["source"] for group in payload["groups"]] == ["Holdings", "Watchlist"]
    hit = payload["groups"][0]["hits"][0]
    assert hit["company"] == "Json Co"
    assert hit["href"].startswith("/portfolio/")


def test_ui13_disclaimer_in_popover_not_in_footer(client, db_path):
    for path in ("/", "/portfolio", "/notifications", "/settings"):
        html = client.get(path).get_data(as_text=True)
        assert 'id="whyBondsBtn"' in html, path
        assert 'id="whyBonds"' in html, path
        assert 'class="disclaimer-box" id="why-disclaimer"' in html, path
        assert 'id="app-disclaimer"' not in html, path
        assert 'class="disclaimer-line"' not in html, path
        for phrase in DISCLAIMER_PHRASES:
            assert phrase in html, (path, phrase)


def test_ui13_why_bonds_popover_content(client, db_path):
    html = client.get("/").get_data(as_text=True)
    assert "Why bonds?" in html
    assert "Fixed, predictable returns" in html
    assert "Expectation check" in html
    assert "10&#8211;12%" in html
    assert "Flip side" in html
    assert "We do not recommend any bonds." in html
    assert 'id="why-about-link"' in html


def test_ui13_disclaimer_is_separate_from_any_referral(client, db_path):
    html = client.get("/").get_data(as_text=True)
    assert "referral" not in html.lower()
    assert "disclaimer-box" in html
    assert 'id="app-disclaimer"' not in html


def test_ui13_disclaimer_not_only_in_the_popover(client, db_path):
    about = client.get("/about").get_data(as_text=True)
    assert 'id="about-disclaimer"' in about
    portfolio = client.get("/portfolio").get_data(as_text=True)
    assert 'id="why-disclaimer"' in portfolio
    for phrase in DISCLAIMER_PHRASES:
        assert phrase in about, phrase
        assert phrase in portfolio, phrase
