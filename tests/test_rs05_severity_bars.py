import re
from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn
from src.notifications import notify

ROOT = Path(__file__).resolve().parents[1]
CSS = (ROOT / "src" / "static" / "theme.css").read_text(encoding="utf-8")

SEVERITIES = ("danger", "due_today", "warn", "reminder", "maturity_soon")


def token(block_selector, name):
    start = CSS.index(block_selector)
    end = CSS.index("}", start)
    match = re.search(rf"{re.escape(name)}:\s*(#[0-9a-fA-F]{{6}})", CSS[start:end])
    assert match, f"{name} missing in {block_selector}"
    return match.group(1).lower()


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_rs05_all_five_severities_render_a_severity_class(client, db_path):
    with get_conn(db_path) as conn:
        for severity in SEVERITIES:
            notify(conn, severity, f"{severity} row")
    html = client.get("/").get_data(as_text=True)
    for severity in SEVERITIES:
        assert f'class="alert-item-v3 sev-{severity}"' in html


def test_rs05_each_severity_has_a_four_pixel_bar_rule():
    for severity in SEVERITIES:
        rule = re.search(rf"\.alert-item-v3\.sev-{severity}\s*\{{([^}}]*)\}}", CSS)
        assert rule, severity
        assert "border-left" in rule.group(1), severity
    maturity = re.search(r"\.alert-item-v3\.sev-maturity_soon\s*\{([^}]*)\}", CSS)
    assert maturity and "border-left: 4px solid var(--teal-fg)" in maturity.group(1)


def test_rs05_maturity_soon_teal_tokens_in_both_themes():
    assert token('html[data-theme="light"]', "--teal-fg") == "#0f766e"
    assert token('html[data-theme="light"]', "--teal-bg") == "#f0fdfa"
    for block in ('html[data-theme="dark"]', 'html[data-theme="system"]'):
        assert token(block, "--teal-fg") == "#5eead4"
        assert token(block, "--teal-bg") == "#042f2e"
