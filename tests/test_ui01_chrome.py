import re
import sys
from html.parser import HTMLParser
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.app import create_app

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "static" / "theme.css").read_text(encoding="utf-8")
VIEWPORT = '<meta name="viewport" content="width=device-width, initial-scale=1.0">'

NEW_FLUID_SELECTORS = (
    ".app-shell",
    ".app-body",
    ".topbar",
    ".topbar-actions",
    ".icon-btn",
    ".overflow-panel",
    ".bottom-tabs",
    ".bottom-tab",
    ".app-footer",
    ".stat-row",
    ".status-legend",
    ".sidebar nav a::before",
    ".sidebar-head",
    ".collapse-btn",
    ".zone",
)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


class PanelCapture(HTMLParser):
    def __init__(self, panel_id):
        super().__init__(convert_charrefs=False)
        self.panel_id = panel_id
        self.depth = 0
        self.capturing = False
        self.capture_depth = None
        self.parts = []

    def handle_starttag(self, tag, attrs):
        if not self.capturing and dict(attrs).get("id") == self.panel_id:
            self.capturing = True
            self.capture_depth = self.depth
        if self.capturing:
            self.parts.append(self.get_starttag_text())
        self.depth += 1

    def handle_startendtag(self, tag, attrs):
        if self.capturing:
            self.parts.append(self.get_starttag_text())

    def handle_endtag(self, tag):
        self.depth -= 1
        if self.capturing and self.depth == self.capture_depth:
            self.capturing = False

    def handle_data(self, data):
        if self.capturing:
            self.parts.append(data)


def overflow_inner(html):
    parser = PanelCapture("overflowPanel")
    parser.feed(html)
    return "".join(parser.parts)


def css_block(selector):
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", CSS)
    assert match, "missing css rule: " + selector
    return match.group(1)


def test_ui01_sidebar_collapse_control_exists(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="sidebarToggle"' in html
    assert 'class="collapse-btn"' in html
    assert "sidebar-collapsed" in html


def test_ui01_overflow_menu_holds_each_control_once(client):
    html = client.get("/").get_data(as_text=True)
    inner = overflow_inner(html)
    assert inner, "overflow panel not found"
    assert inner.count('data-theme-value="system"') == 1
    assert inner.count('data-theme-value="light"') == 1
    assert inner.count('data-theme-value="dark"') == 1
    assert inner.count('id="privacyToggle"') == 1
    assert inner.count('id="notificationsBell"') == 1
    assert html.count('id="privacyToggle"') == 1
    assert html.count('id="notificationsBell"') == 1
    assert html.count('id="overflowPanel"') == 1


def test_ui01_search_and_guide_icons_present(client):
    html = client.get("/").get_data(as_text=True)
    assert 'id="searchBtn"' in html
    assert 'id="guideBtn"' in html


def test_ui01_viewport_meta_present(client):
    html = client.get("/").get_data(as_text=True)
    assert VIEWPORT in html


def test_ui01_bottom_tabs_at_most_five(client):
    html = client.get("/").get_data(as_text=True)
    count = html.count('class="bottom-tab"')
    assert 1 <= count <= 5


def test_ui01_disclaimer_footer_present(client):
    html = client.get("/").get_data(as_text=True)
    assert 'class="disclaimer-line"' in html
    assert "not investment advice" in html


def test_ui01_dashboard_three_zones(client):
    html = client.get("/").get_data(as_text=True)
    assert 'class="zone kpi-zone"' in html
    assert 'class="zone detail-zone"' in html
    assert 'class="zone legend-zone"' in html
    assert 'id="status-legend"' in html


def test_ui01_new_css_rules_have_no_fixed_px_content_widths():
    for selector in NEW_FLUID_SELECTORS:
        block = css_block(selector)
        block = re.sub(r"(min|max)-width\s*:[^;]+;", "", block)
        assert not re.search(r"\bwidth\s*:\s*[0-9.]+px", block), selector


def test_ui01_css_uses_fluid_primitives():
    assert "max-width: 100%" in CSS
    assert "minmax(" in CSS
    assert "clamp(" in CSS


def test_ui01_css_semantic_color_tokens():
    for token in ("--c-green:", "--c-amber:", "--c-red:", "--c-blue:"):
        assert token in CSS


def test_ui01_css_mobile_first_breakpoints():
    for width in ("320px", "360px", "375px", "414px", "480px", "768px", "1024px", "1440px"):
        assert "@media (min-width: " + width + ")" in CSS


def test_ui01_css_touch_targets():
    assert "--touch-min: 48px" in CSS
    assert "min-height: var(--touch-min)" in CSS
