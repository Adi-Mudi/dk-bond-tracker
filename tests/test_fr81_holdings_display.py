import re
from pathlib import Path

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.engine import purchase_date_label, purchase_qty_value

PURCHASE_DATE = "2026-11-03"
START_DATE = "2026-10-01"
END_DATE = "2028-10-01"
TEMPLATE = Path(__file__).resolve().parents[1] / "src" / "templates" / "portfolio.html"


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def make_candidate(client, db_path, isin):
    response = client.post(
        "/watch",
        data={
            "company": "Purchased Ltd",
            "isin": isin,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def move_to_holding(client, candidate_id, **overrides):
    data = {
        "purchase_date": PURCHASE_DATE,
        "start_date": START_DATE,
        "end_date": END_DATE,
        "credit_day": "5",
        "qty": "200",
        "amount": "200000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return client.post(f"/watch/{candidate_id}/move", data=data)


def holdings_table(html):
    match = re.search(r'<table id="holdings-table">(.*?)</table>', html, re.S)
    assert match, "holdings table must render"
    return match.group(1)


def holding_row(table_html, bond_id):
    match = re.search(
        r'<tr [^>]*data-id="' + str(bond_id) + r'"[^>]*>(.*?)</tr>', table_html, re.S
    )
    assert match, "holding row must render"
    return match.group(1)


def test_fr81_ac1_qty_column_and_secondary_line_render(client, db_path):
    candidate_id = make_candidate(client, db_path, "INE9000A8100")
    assert move_to_holding(client, candidate_id).status_code == 302
    table = holdings_table(client.get("/portfolio").get_data(as_text=True))
    assert '<th class="num">Qty</th>' in table
    row = holding_row(table, candidate_id)
    assert '<td class="num">200</td>' in row
    assert (
        '<span class="co-purchased">purchased 03 Nov 2026 · 200 units</span>' in row
    )


def test_fr81_ac2_legacy_holding_omits_line_and_shows_em_dash(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Legacy Ltd", "INE9000A8101", "2024-01-01", 60)
    table = holdings_table(client.get("/portfolio").get_data(as_text=True))
    row = holding_row(table, bond_id)
    assert "purchased" not in table
    assert '<td class="num">—</td>' in row
    assert "null" not in table.lower()
    assert "None" not in table


def test_fr81_ac3_detail_exposes_purchase_facts_and_drawer_rows(client, db_path):
    candidate_id = make_candidate(client, db_path, "INE9000A8102")
    assert move_to_holding(client, candidate_id).status_code == 302
    data = client.get(f"/portfolio/{candidate_id}/detail").get_json()
    assert data["purchase_date"] == "03 Nov 2026"
    assert data["qty"] == 200
    source = TEMPLATE.read_text(encoding="utf-8")
    assert 'factRow("Purchase date", data.purchase_date)' in source
    assert 'factRow("Quantity", data.qty)' in source


def test_fr81_legacy_detail_returns_null_purchase_facts(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Legacy Ltd", "INE9000A8103", "2024-01-01", 60)
    data = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert data["purchase_date"] is None
    assert data["qty"] is None


def test_fr81_holdings_context_exposes_purchase_keys(client, db_path):
    candidate_id = make_candidate(client, db_path, "INE9000A8104")
    assert move_to_holding(client, candidate_id, qty="350").status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT purchase_date, qty FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row["purchase_date"] == PURCHASE_DATE
    assert row["qty"] == 350
    table = holdings_table(client.get("/portfolio").get_data(as_text=True))
    assert "purchased 03 Nov 2026 · 350 units" in holding_row(table, candidate_id)


def test_fr81_qty_value_formats_whole_numbers_as_int():
    assert purchase_qty_value(200.0) == 200
    assert isinstance(purchase_qty_value(200.0), int)
    assert purchase_qty_value("200") == 200
    assert purchase_qty_value(2.5) == 2.5
    assert purchase_qty_value(None) is None
    assert purchase_qty_value("abc") is None


def test_fr81_purchase_date_label_formats_and_handles_nulls():
    assert purchase_date_label("2026-11-03") == "03 Nov 2026"
    assert purchase_date_label(None) is None
    assert purchase_date_label("") is None
