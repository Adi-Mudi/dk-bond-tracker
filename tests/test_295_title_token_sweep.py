"""Issue #295: title + token consistency sweep (Q2-Q7).

F1 /grid body h1 -> page-title pattern
F2 /portfolio list body h1 (x2) -> page-title pattern
F3 /share body h1 -> page-title pattern
F5 per-page tab titles on every route
F8 --info-*/--ok-* tokens defined in theme.css (light+dark+system-dark)
F4 /print per-page <title> + page-title element, A4 paper output unchanged
"""
import re
from pathlib import Path

import pytest

from src.app import create_app
from src.print_palette import PRINT_PALETTE

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"
THEME_CSS = (ROOT / "src" / "static" / "theme.css").read_text(encoding="utf-8")

H1_ROUTES = ("/grid", "/portfolio", "/share", "/print")

PAGE_TITLES = {
    "/": "Dashboard",
    "/grid": "Payout Grid",
    "/portfolio": "Portfolio",
    "/share": "Share snapshot",
    "/print": "Monthly Print — A4 statement",
    "/about": "About",
    "/search": "Search",
    "/watch": "Watchlist",
    "/goals": "Goals",
    "/notifications": "Alerts",
    "/settings": "Settings",
}

PRINT_PAPER_RULES = {
    ".st-app { font-size: 19px; font-weight: 800; letter-spacing: 0.02em; }": "statement title size",
    ".st-doc { font-size: 13.5px; font-weight: 700; margin-top: 1px; }": "statement doc line",
    ".st-title-block {": "statement header block",
    "@page {\n    size: A4 portrait;\n    margin: 12mm;\n  }": "A4 page geometry",
    ".a4 {\n    width: 210mm;\n    min-height: 297mm;\n    margin: 0 auto 12px;\n    padding: 14mm 14mm 12mm;": "A4 sheet geometry",
}

TOKEN_BLOCKS = (
    ':root, html[data-theme="light"]',
    'html[data-theme="dark"]',
    'html[data-theme="system"]',
)

INFO_OK_TOKENS = {
    "--info-fg": ("#1f4f9a", "#79c0ff"),
    "--info-bg": ("#e8f0fb", "#12233d"),
    "--ok-fg": ("#1d6b3a", "#56d364"),
    "--ok-bg": ("#e6f6ec", "#10251a"),
}

PRINT_BODY_TOKENS = {
    "--border": PRINT_PALETTE["ink"],
    "--text": PRINT_PALETTE["ink"],
    "--muted": PRINT_PALETTE["sub"],
    "--header-row": PRINT_PALETTE["th_bg"],
    "--due": PRINT_PALETTE["due"],
    "--ongoing-light": PRINT_PALETTE["ongoing_light"],
    "--completed-light": PRINT_PALETTE["completed_light"],
    "--blue-light": PRINT_PALETTE["blue_light"],
    "--white": PRINT_PALETTE["paper"],
    "--card-bg": PRINT_PALETTE["card_bg"],
    "--screen-bg": PRINT_PALETTE["screen_bg"],
    "--badge-bg": PRINT_PALETTE["badge_bg"],
    "--sheet-border": PRINT_PALETTE["sheet_border"],
    "--shadow-overlay": PRINT_PALETTE["shadow_overlay"],
    "--shadow-soft": PRINT_PALETTE["shadow_soft"],
}


def block_tokens(block_selector):
    start = THEME_CSS.index(block_selector)
    end = THEME_CSS.index("}", start)
    return THEME_CSS[start:end]


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def rendered(client, route):
    response = client.get(route)
    assert response.status_code == 200, route
    return response.get_data(as_text=True)


@pytest.mark.parametrize("route", H1_ROUTES)
def test_295_swept_routes_have_no_body_h1(client, route):
    html = rendered(client, route)
    body = html.split("<body", 1)[1]
    assert "<h1" not in body, route


@pytest.mark.parametrize("route", H1_ROUTES)
def test_295_swept_routes_show_page_title_element(client, route):
    html = rendered(client, route)
    assert 'class="page-title"' in html, route


def test_295_portfolio_drawer_uses_page_title_and_muted_isin():
    js = (TEMPLATES / "portfolio.html").read_text(encoding="utf-8")
    assert '<div class="detail-head"><h1>' not in js
    assert '<div class="detail-title"><div class="page-title">' in js
    assert '<span class="co-isin">' in js


@pytest.mark.parametrize("route", sorted(PAGE_TITLES))
def test_295_every_route_has_per_page_tab_title(client, route):
    html = rendered(client, route)
    expected = f"<title>{PAGE_TITLES[route]} — DK Bond Tracker</title>"
    assert expected in html, route


@pytest.mark.parametrize("route", sorted(PAGE_TITLES))
def test_295_tab_title_matches_page_title_text(client, route):
    html = rendered(client, route)
    title = re.search(r"<title>(.*?)</title>", html, re.S).group(1)
    assert title.endswith(" — DK Bond Tracker"), route
    assert title.split(" — DK Bond Tracker")[0].startswith(PAGE_TITLES[route]), route


@pytest.mark.parametrize("block", TOKEN_BLOCKS)
def test_295_info_ok_tokens_defined_in_every_theme_block(block):
    tokens = block_tokens(block)
    light_values = {name: values[0] for name, values in INFO_OK_TOKENS.items()}
    dark_values = {name: values[1] for name, values in INFO_OK_TOKENS.items()}
    expected = light_values if block == TOKEN_BLOCKS[0] else dark_values
    for name, value in expected.items():
        match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})", tokens)
        assert match, f"{name} missing in {block}"
        assert match.group(1).lower() == value


def test_295_info_ok_tokens_used_without_fallbacks():
    about = (TEMPLATES / "about.html").read_text(encoding="utf-8")
    assert "var(--ok-bg)" in about and "var(--ok-fg)" in about
    assert "var(--info-bg)" in about and "var(--info-fg)" in about
    assert not re.search(r"var\(--(?:info|ok)-(?:bg|fg),", about)


def test_295_no_template_defines_tokens_inline():
    offenders = []
    for template in sorted(TEMPLATES.glob("*.html")):
        for line in template.read_text(encoding="utf-8").splitlines():
            if re.match(r"\s*--[a-z-]+\s*:", line):
                offenders.append(f"{template.name}: {line.strip()}")
    assert not offenders, offenders


def test_295_theme_css_carries_print_palette_tokens():
    tokens = block_tokens("body.print-statement")
    for name, value in PRINT_BODY_TOKENS.items():
        match = re.search(rf"{re.escape(name)}:\s*([^;]+);", tokens)
        assert match, f"{name} missing in body.print-statement"
        actual = re.sub(r"\s+", "", match.group(1)).lower()
        assert actual == re.sub(r"\s+", "", value).lower()


def test_295_print_template_uses_statement_scope_class():
    html = (TEMPLATES / "monthly_print.html").read_text(encoding="utf-8")
    assert '<body class="print-statement' in html
    assert ":root {" not in html


def test_295_print_keeps_a4_paper_rules_unchanged():
    html = (TEMPLATES / "monthly_print.html").read_text(encoding="utf-8")
    for rule, reason in PRINT_PAPER_RULES.items():
        assert rule in html, reason


def test_295_print_statement_header_tokens_resolve_from_theme():
    html = (TEMPLATES / "monthly_print.html").read_text(encoding="utf-8")
    for name in re.findall(r"var\((--[a-z-]+)\)", html):
        assert f"{name}:" in THEME_CSS, name


def test_295_print_renders_statement_header_unchanged(client):
    html = rendered(client, "/print")
    assert '<div class="st-app">DK Bond Tracker</div>' in html
    assert 'id="print-header"' in html
    assert '<div class="page-title" id="print-page-title">Monthly Print — A4 statement</div>' in html
    assert "<h1" not in html
