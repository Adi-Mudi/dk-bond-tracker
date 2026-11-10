import importlib
import sys
from pathlib import Path

import pytest

from src.app import create_app

TESTS_DIR = Path(__file__).resolve().parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

GATE = importlib.import_module("test_resizer_gate")

REDESIGNED_SCREENS = {
    "/": "dashboard",
    "/grid": "payouts",
    "/portfolio": "holdings",
    "/watch": "watchlist",
    "/goals": "goals",
    "/notifications": "alerts",
    "/settings": "settings",
    "/about": "about",
    "/feedback": "feedback",
    "/search": "search",
}
OUTSIDE_GATE = {
    "/export.csv": "csvExportNeedsScope",
    "/print": "printLayoutNotInRedesignList",
    "/share": "shareSnapshotNotInRedesignList",
    "/payout": "needsBondIdQueryArgument",
    "/gmail/connect": "oauthRedirectNotAScreen",
    "/auth/google/callback": "oauthCallbackRedirectNotAScreen",
}
DECLARED_WIDTHS = (320, 360, 375, 414, 480, 768, 1024, 1440)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def app_get_routes(app):
    routes = set()
    for rule in app.url_map.iter_rules():
        if rule.arguments:
            continue
        if "GET" not in (rule.methods or set()):
            continue
        if rule.rule.startswith("/static"):
            continue
        routes.add(rule.rule)
    return routes


def test_gate_enumerates_every_redesigned_screen():
    assert set(GATE.CORE_ROUTES) == set(REDESIGNED_SCREENS)


def test_gate_has_no_duplicate_or_stale_entries():
    assert len(list(GATE.CORE_ROUTES)) == len(set(GATE.CORE_ROUTES))


def test_no_app_screen_escapes_the_gate(db_path):
    app = create_app(str(db_path))
    uncovered = app_get_routes(app) - set(GATE.CORE_ROUTES)
    assert uncovered == set(OUTSIDE_GATE), sorted(uncovered)


def test_gate_covers_no_route_the_app_lacks(db_path):
    app = create_app(str(db_path))
    app_routes = app_get_routes(app)
    assert set(GATE.CORE_ROUTES) - app_routes == set()


def test_gate_keeps_the_eight_declared_widths():
    assert tuple(GATE.WIDTHS) == DECLARED_WIDTHS
    assert len(GATE.WIDTHS) == 8


@pytest.mark.parametrize("route", sorted(REDESIGNED_SCREENS))
def test_every_gate_route_renders_with_the_page_guide(client, route):
    response = client.get(route)
    assert response.status_code == 200, route
    html = response.get_data(as_text=True)
    assert 'id="pageGuide"' in html, route
    assert 'id="guideBtn"' in html, route


def test_gate_detector_still_flags_a_real_overflow(client):
    html = (
        "<!doctype html><html><head><style>.escapes { width: 5000px; }</style></head>"
        '<body><div class="escapes">x</div></body></html>'
    )
    assert GATE.overflow_findings(client, html, 320)
