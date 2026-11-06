import re
from datetime import date
from html.parser import HTMLParser

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.validators import add_months

VOID_ELEMENTS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "param", "source", "track", "wbr"}


class MoneyAudit(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.violations = []

    def handle_starttag(self, tag, attrs):
        if tag in VOID_ELEMENTS:
            return
        self.stack.append(dict(attrs))

    def handle_endtag(self, tag):
        if tag in VOID_ELEMENTS:
            return
        if self.stack:
            self.stack.pop()

    def handle_data(self, data):
        if "₹" not in data:
            return
        if not any("money" in (entry.get("class") or "") for entry in self.stack):
            self.violations.append(data.strip())


def audit_money(html):
    parser = MoneyAudit()
    parser.feed(html)
    return parser.violations


def data_amount_tags(html):
    return re.findall(r"<[^>]*data-amount=[^>]*>", html)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_sample(db_path):
    with get_conn(db_path) as conn:
        base = date.today().replace(day=1)
        bond_id = add_bond(conn, "PrivacyCo", "INE0000000741", base.isoformat(), 12, amount=123456.0)
        add_payment(conn, bond_id, f"{base.year:04d}-{base.month:02d}", 9876.0)
        add_bond(conn, "PrivacyCo2", "INE0000000742", add_months(base, -3).isoformat(), 6, amount=55555.0)


def test_tc74_dashboard_money_elements_all_classed(client, db_path):
    seed_sample(db_path)
    html = client.get("/").get_data(as_text=True)
    assert audit_money(html) == []
    tags = data_amount_tags(html)
    assert len(tags) >= 4
    for tag in tags:
        assert "money" in tag, tag
    assert html.count('class="value money"') == 6
    assert any('data-amount="179011.00"' in tag for tag in tags)


def test_tc74_watch_money_elements_all_classed(client, db_path):
    seed_sample(db_path)
    html = client.get("/watch").get_data(as_text=True)
    assert audit_money(html) == []
    tags = data_amount_tags(html)
    assert len(tags) >= 2
    for tag in tags:
        assert "money" in tag, tag


def test_tc74_grid_has_no_unmasked_money_and_privacy_chrome(client, db_path):
    seed_sample(db_path)
    html = client.get("/grid").get_data(as_text=True)
    assert audit_money(html) == []
    for tag in data_amount_tags(html):
        assert "money" in tag, tag
    assert 'id="privacyToggle"' in html


def test_tc74_privacy_toggle_inline_js_and_localstorage_key_on_every_surface(client, db_path):
    seed_sample(db_path)
    for path in ("/", "/grid", "/watch", "/notifications"):
        html = client.get(path).get_data(as_text=True)
        assert 'id="privacyToggle"' in html, path
        assert "privacy_mode" in html, path
        assert "localStorage" in html, path
        assert "privacy-on" in html, path
        assert "<script>" in html, path


def test_tc74_mask_css_present(client, db_path):
    html = client.get("/").get_data(as_text=True)
    assert ".privacy-on .money { font-size: 0; }" in html
    assert '.privacy-on .money::after { content: "••••"; font-size: 14px; letter-spacing: 0.14em; }' in html
    assert ".privacy-on .money-input { color: transparent; }" in html
    assert "••••" in html


def test_tc74_money_values_carry_data_amount_for_masking(client, db_path):
    seed_sample(db_path)
    dashboard = client.get("/").get_data(as_text=True)
    values = re.findall(r'data-amount="(-?[\d.]+)"', dashboard)
    assert values
    assert 'data-amount="179011.00"' in dashboard
    watch = client.get("/watch").get_data(as_text=True)
    assert 'data-amount="123456.00"' in watch
