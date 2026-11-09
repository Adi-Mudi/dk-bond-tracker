import re
from datetime import date
from pathlib import Path

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.queries import position_detail
from src.validators import add_months

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "src" / "templates" / "portfolio.html").read_text(encoding="utf-8")
DETAIL_TEMPLATE = (ROOT / "src" / "templates" / "portfolio_detail.html").read_text(
    encoding="utf-8"
)
GROUP_IDS = (
    "grp-identity",
    "grp-investment",
    "grp-returns",
    "grp-schedule",
    "grp-classification",
    "grp-payment-history",
)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def holdings_table(html):
    match = re.search(r'<table id="holdings-table">(.*?)</table>', html, re.S)
    assert match, "holdings table must render"
    return match.group(1)


def month_of(day):
    return f"{day.year:04d}-{day.month:02d}"


def seed_two_holdings(db_path):
    base = date.today().replace(day=1)
    with get_conn(db_path) as conn:
        first = add_bond(
            conn, "Row Co A", "INE2000A1001", add_months(base, -2).isoformat(), 6, credit_day=5
        )
        second = add_bond(
            conn, "Row Co B", "INE2000A1002", add_months(base, -1).isoformat(), 6, credit_day=5
        )
    return first, second


def seed_payment_chips(db_path):
    base = date.today().replace(day=1)
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "Chip Co", "INE2000A1003", add_months(base, -2).isoformat(), 12, credit_day=5
        )
        add_payment(conn, bond_id, month_of(add_months(base, -2)), 1000.0, paid=1)
    return bond_id


def test_ui02_one_row_per_bond(client, db_path):
    first, second = seed_two_holdings(db_path)
    table = holdings_table(client.get("/portfolio").get_data(as_text=True))
    rows = re.findall(r'<tr [^>]*class="position-row"[^>]*>', table)
    assert len(rows) == 2
    for bond_id in (first, second):
        assert len(re.findall(r'<tr [^>]*data-id="' + str(bond_id) + r'"', table)) == 1


def test_ui02_holdings_table_sticky_classes_present(client, db_path):
    seed_two_holdings(db_path)
    html = client.get("/portfolio").get_data(as_text=True)
    table = holdings_table(html)
    thead = table[: table.index("</thead>")]
    assert 'class="cell-sticky cell-left"' in thead
    assert 'class="cell-sticky cell-right"' in thead
    assert table.count("cell-sticky cell-left") >= 2
    assert table.count("cell-sticky cell-right") >= 2
    assert "table-wrap holdings-scroll" in html
    assert 'tabindex="0"' in html
    assert 'role="region"' in html
    assert "aria-label=\"Holdings table" in html


def test_ui02_sticky_cells_have_opaque_background_and_zindex_ladder(client, db_path):
    seed_two_holdings(db_path)
    assert "#holdings-table td.cell-sticky { position: sticky; background: var(--card); z-index: 1; }" in TEMPLATE
    assert "#holdings-table thead th.cell-sticky { position: sticky; background: var(--card); z-index: 3; }" in TEMPLATE
    assert "#holdings-table td.cell-left { z-index: 2; }" in TEMPLATE
    assert "#holdings-table td.cell-right { z-index: 2; }" in TEMPLATE
    assert "#holdings-table thead th.cell-left { left: 0; z-index: 4; }" in TEMPLATE
    assert "#holdings-table thead th.cell-right { right: 0; z-index: 5; }" in TEMPLATE


def test_ui02_no_visible_meta_strip_under_rows(client, db_path):
    seed_two_holdings(db_path)
    table = holdings_table(client.get("/portfolio").get_data(as_text=True))
    assert "detail-row" not in table
    assert re.search(
        r'<tr class="attr-row-hidden" hidden><td colspan="10" class="attr-strip">', table
    )


def test_ui02_detail_page_renders_six_groups_and_back(client, db_path):
    first, _second = seed_two_holdings(db_path)
    page = client.get(f"/portfolio/{first}").get_data(as_text=True)
    for group_id in GROUP_IDS:
        assert f'id="{group_id}"' in page, group_id
    assert "&#8592; Portfolio" in page
    assert 'id="detail-back"' in page


def test_ui02_drawer_source_mirrors_six_groups(client, db_path):
    seed_two_holdings(db_path)
    for group_id in GROUP_IDS:
        assert f'id="{group_id}"' in TEMPLATE, group_id
    assert "&#183; Identity" in TEMPLATE
    assert "&#183; Payment history" in TEMPLATE


def test_ui02_bond_detail_tabs_markup(client, db_path):
    first, _second = seed_two_holdings(db_path)
    page = client.get(f"/portfolio/{first}").get_data(as_text=True)
    assert page.count('class="dt-tab') == 3
    for name in ("overview", "payments", "goal"):
        assert f'data-dtab="{name}"' in page
    assert "read-only" in page
    for name in ("overview", "payments", "goal"):
        assert f'data-dtab="{name}"' in TEMPLATE


def test_ui02_group_by_toggle_none_default_and_goal_bucket(client, db_path):
    seed_two_holdings(db_path)
    flat = client.get("/portfolio").get_data(as_text=True)
    assert 'id="group-none"' in flat
    assert 'id="group-goal"' in flat
    assert 'href="/portfolio?group=none"' in flat
    assert 'href="/portfolio?group=goal"' in flat
    assert 'class="group-btn active" id="group-none"' in flat
    assert 'class="group-head-row"' not in flat
    grouped = client.get("/portfolio?group=goal").get_data(as_text=True)
    assert 'class="group-head-row"' in grouped
    assert "Ungrouped" in grouped
    assert grouped.count('class="position-row"') == flat.count('class="position-row"')
    assert 'class="group-btn active" id="group-goal"' in grouped


def test_ui02_month_chips_follow_cell_rule(client, db_path):
    bond_id = seed_payment_chips(db_path)
    page = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    chips = re.findall(r'<div class="month-chip (month-\w+)"[^>]*>(.*?)</div>', page, re.S)
    assert chips
    states = {state for state, _body in chips}
    assert "month-paid" in states
    for state, body in chips:
        if state == "month-paid":
            assert "&#8377;" in body
            assert "unpaid" not in body
            assert "due soon" not in body
        elif state == "month-unpaid":
            assert "unpaid" in body
            assert "&#8377;" not in body
        elif state == "month-soon":
            assert "due soon" in body
            assert "&#8377;" not in body


def test_ui02_payment_month_states_unit(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Unit Co", "INE2000A1099", "2026-05-01", 6, credit_day=31)
    with get_conn(db_path) as conn:
        detail = position_detail(conn, bond_id, today=date(2026, 6, 10))
    states = {chip["key"]: chip["state"] for chip in detail["payment_months"]}
    assert states == {"2026-05": "unpaid", "2026-06": "soon"}
    assert all(chip["amount"] is None for chip in detail["payment_months"])


def test_ui02_detail_route_and_json_agree(client, db_path):
    bond_id = seed_payment_chips(db_path)
    payload = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert payload["credit_day"] == 5
    assert payload["end_date"]
    assert payload["payment_months"]
    assert {chip["state"] for chip in payload["payment_months"]} <= {"paid", "unpaid", "soon"}
