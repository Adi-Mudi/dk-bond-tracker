import importlib
import re
import sys
from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn
from tests.conftest import add_bond, add_payment, month_sequence

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

GATE = importlib.import_module("test_resizer_gate")

pytestmark = pytest.mark.remote

CORE_ROUTES = GATE.CORE_ROUTES
WIDTHS = GATE.WIDTHS

TOKEN_PX_CEILING = 24
PX_WIDTH = re.compile(r"^(\d+)px$")
VIEWPORT_META = re.compile(r'<meta[^>]*name="viewport"[^>]*content="width=device-width[^"]*"')
COMBINATOR = re.compile(r"\s*[>+~]\s*|\s+")
ATTRIBUTE = re.compile(r"\[[^\]]*\]")
PSEUDO = re.compile(r"::?[\w-]+(\([^)]*\))?")
SIMPLE_TOKEN = re.compile(r"[.#]?[\w-]+")

TOPBAR = "topbar"
SIDEBAR = "sidebar"
APPBAR = "bottom-tabs"

STATUS = "status"
OVERFLOW = "overflow"
LANDMARKS = "landmarks"
CSS = "css"

PAGE_HEAD = (
    "<!doctype html><html><head>"
    '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
)
PAGE_LANDMARKS = (
    '<aside class="sidebar"></aside><header class="topbar"></header>'
    '<main class="main"></main>'
)
TOPBAR_APPBAR_MAIN = (
    '<header class="topbar"></header><main class="main"></main>'
    '<nav class="bottom-tabs"></nav>'
)


@pytest.fixture
def client(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha Bonds Ltd", "INE00010001", "2026-01-05", 60, credit_day=5, amount=100000)
        for month in month_sequence("2026-01", 6):
            add_payment(conn, bond_id, month, 1000.0, paid=1)
        add_payment(conn, bond_id, "2026-07", 1000.0, paid=0)
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, tenure_months, credit_day, status, watch_state, rating, coupon_pct, payout_cycle, broker) "
            "VALUES ('Beta Finance', 'INE000200002', 'Beta Finance', 50000, 120000, '2026-02-01', '2031-02-01', 60, 10, 'On-going', 'watching', 'AA-', 8.5, 'quarterly', 'Zerodha')"
        )
        conn.execute(
            "INSERT INTO financial_goals (name, target_amount, target_end_date, note, saved_amount) "
            "VALUES ('House', 600000, '2026-12-31', '', 50000)"
        )
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def page(style="", body="", landmarks=True):
    return (
        PAGE_HEAD
        + (f"<style>{style}</style>" if style else "")
        + "</head><body>"
        + (PAGE_LANDMARKS if landmarks else "")
        + body
        + "</body></html>"
    )


def has_class(root, name):
    return any(name in GATE.element_classes(node) for node in GATE.walk(root))


def landmark_findings(root):
    findings = []
    if not has_class(root, TOPBAR):
        findings.append("topbar landmark missing")
    if not has_class(root, SIDEBAR) and not has_class(root, APPBAR):
        findings.append("sidebar/appbar landmark missing")
    if not any(node.tag == "main" for node in GATE.walk(root)):
        findings.append("main content landmark missing")
    return findings


def viewport_findings(html):
    return [] if VIEWPORT_META.search(html) else ["viewport meta missing"]


def compound_tokens(part):
    return SIMPLE_TOKEN.findall(PSEUDO.sub("", ATTRIBUTE.sub("", part)))


def token_matches(token, node):
    if token.startswith("#"):
        return node.attrs.get("id") == token[1:]
    if token.startswith("."):
        return token[1:] in GATE.element_classes(node)
    return node.tag == token


def part_matches(part, node):
    tokens = compound_tokens(part)
    return node is not None and bool(tokens) and all(token_matches(token, node) for token in tokens)


def ancestors_match(parts, node):
    if not parts:
        return True
    while node is not None:
        if part_matches(parts[-1], node) and ancestors_match(parts[:-1], node.parent):
            return True
        node = node.parent
    return False


def selector_parts(selector):
    return [part for part in COMBINATOR.split(selector.strip()) if part]


def selector_matches(selector, node):
    parts = selector_parts(selector)
    return bool(parts) and part_matches(parts[-1], node) and ancestors_match(parts[:-1], node.parent)


def selector_subject(root, selector):
    return [node for node in GATE.walk(root) if selector_matches(selector, node)]


def subject_tolerates_wide(selector, root):
    matched = selector_subject(root, selector)
    return not matched or all(GATE.inside_scroll_container(node) for node in matched)


def structural_px_findings(css, root, width):
    findings = []
    for (selector, prop), (raw, body) in GATE.winning_widths(css, width).items():
        match = PX_WIDTH.match(raw or "")
        if not match:
            continue
        pixels = int(match.group(1))
        if pixels <= TOKEN_PX_CEILING:
            continue
        if GATE.body_is_guarded(body, width):
            continue
        if subject_tolerates_wide(selector, root):
            continue
        findings.append(f"{selector} {{{prop}: {pixels}px}}")
    return sorted(findings)


def audit_html(client, html, width):
    root = GATE.build_tree(html)
    found = {}
    overflow = GATE.overflow_findings(client, html, width)
    if overflow:
        found[OVERFLOW] = overflow
    landmarks = landmark_findings(root)
    if landmarks:
        found[LANDMARKS] = landmarks
    css = viewport_findings(html) + structural_px_findings(
        GATE.parse_stylesheets(client, html), root, width
    )
    if css:
        found[CSS] = sorted(css)
    return found


def audit_at_width(client, route, width):
    response = client.get(route)
    if response.status_code != 200:
        return {STATUS: [f"HTTP {response.status_code}"]}
    return audit_html(client, response.get_data(as_text=True), width)


def audit_route(client, route):
    return {width: audit_at_width(client, route, width) for width in WIDTHS}


@pytest.mark.parametrize("route", CORE_ROUTES)
def test_route_passes_the_full_multiwidth_audit(client, route):
    report = audit_route(client, route)
    failed = {width: findings for width, findings in report.items() if findings}
    assert failed == {}, (route, failed)


def test_audit_covers_every_declared_width(client):
    assert set(audit_route(client, CORE_ROUTES[0])) == set(WIDTHS)


def test_audit_accepts_the_full_landmark_set(client):
    assert audit_html(client, page(), 320) == {}


def test_audit_accepts_an_appbar_instead_of_a_sidebar(client):
    html = page(body=TOPBAR_APPBAR_MAIN, landmarks=False)
    assert audit_html(client, html, 320) == {}


def test_audit_accepts_an_icon_sized_fixed_px(client):
    assert audit_html(client, page(style=".dot { width: 16px; height: 16px; }"), 320) == {}


def test_audit_accepts_a_guarded_structural_fixed_px(client):
    style = ".wide-only { width: 4800px; overflow-x: auto; }"
    assert audit_html(client, page(style=style), 320) == {}


def test_audit_accepts_a_fixed_px_inside_a_scroll_container(client):
    style = "#inside-table { min-width: 4800px; }"
    body = '<div class="table-wrap"><table id="inside-table"></table></div>'
    assert audit_html(client, page(style=style, body=body), 320) == {}


def test_audit_ignores_a_rule_that_matches_no_element(client):
    assert audit_html(client, page(style=".chart-label { width: 160px; }"), 320) == {}


def test_audit_ignores_a_descendant_rule_without_its_ancestor(client):
    body = '<span class="chip">chip</span>'
    assert audit_html(client, page(style=".legend-row .chip { width: 96px; }", body=body), 320) == {}


def test_audit_flags_a_descendant_rule_with_its_ancestor(client):
    body = '<div class="legend-row"><span class="chip">chip</span></div>'
    html = page(style=".legend-row .chip { width: 96px; }", body=body)
    assert audit_html(client, html, 320) == {CSS: [".legend-row .chip {width: 96px}"]}


def test_audit_flags_a_missing_viewport_meta(client):
    html = "<!doctype html><html><head></head><body>" + PAGE_LANDMARKS + "</body></html>"
    assert audit_html(client, html, 320) == {CSS: ["viewport meta missing"]}


def test_audit_flags_a_page_without_landmarks(client):
    assert audit_html(client, page(landmarks=False), 320) == {
        LANDMARKS: [
            "topbar landmark missing",
            "sidebar/appbar landmark missing",
            "main content landmark missing",
        ]
    }


def test_audit_flags_an_injected_structural_fixed_px(client):
    html = page(style=".wide-only { width: 300px; }", body='<div class="wide-only">x</div>')
    assert audit_html(client, html, 1024) == {CSS: [".wide-only {width: 300px}"]}


def test_audit_flags_an_injected_horizontal_overflow_marker(client):
    html = page(style=".escapes { width: 5000px; }", body='<div class="escapes">x</div>')
    assert audit_html(client, html, 320) == {
        OVERFLOW: [".escapes {width: 5000px} at 320px"],
        CSS: [".escapes {width: 5000px}"],
    }
