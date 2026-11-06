import re

import pytest

from conftest import bond_count
from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def candidate_form(**overrides):
    data = {
        "company": "Quantity Ltd",
        "isin": "INE9000A0300",
        "rating": "AA",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def candidate_row(db_path, isin):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id, qty, watch_state FROM bonds WHERE isin = ?", (isin.upper(),)
        ).fetchone()


def move_payload(**overrides):
    data = {
        "purchase_date": "2026-08-01",
        "start_date": "2026-08-01",
        "end_date": "2028-08-01",
        "credit_day": "5",
        "qty": "100",
        "amount": "100000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def ledger_count(db_path):
    with get_conn(db_path) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"]


def move_panel(html, candidate_id):
    match = re.search(
        r'<tr class="move-row" id="move-panel-' + str(candidate_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert match, "move panel must render as a hidden row"
    return match.group(1)


def test_fr79_ac1_candidate_qty_stored_and_watchlist_renders_it(client, db_path):
    response = client.post("/watch", data=candidate_form(qty="200"))
    assert response.status_code == 302
    row = candidate_row(db_path, "INE9000A0300")
    assert row["watch_state"] == "watching"
    assert row["qty"] == 200

    html = client.get("/watch").get_data(as_text=True)
    assert "Quantity Ltd" in html
    panel = move_panel(html, row["id"])
    assert 'name="qty"' in panel
    assert 'value="200' in panel


def test_fr79_ac2_candidate_without_qty_stored_null(client, db_path):
    response = client.post("/watch", data=candidate_form())
    assert response.status_code == 302
    row = candidate_row(db_path, "INE9000A0300")
    assert row["watch_state"] == "watching"
    assert row["qty"] is None
    assert "Quantity Ltd" in client.get("/watch").get_data(as_text=True)


def test_fr79_ac2_candidate_with_blank_qty_stored_null(client, db_path):
    response = client.post("/watch", data=candidate_form(qty="   "))
    assert response.status_code == 302
    assert candidate_row(db_path, "INE9000A0300")["qty"] is None


@pytest.mark.parametrize("bad_value", ["abc", "0", "-5", "2.5", "1e3"])
def test_fr79_ac1_candidate_bad_qty_rejected_with_zero_writes(client, db_path, bad_value):
    response = client.post("/watch", data=candidate_form(qty=bad_value))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-watch-add" in html
    assert "qty must be a positive integer" in html
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


def test_fr79_candidate_form_has_optional_qty_field(client, db_path):
    html = client.get("/watch").get_data(as_text=True)
    assert "Quantity (no. of bonds)" in html
    tag = re.search(r'<input[^>]*id="c-qty"[^>]*>', html)
    assert tag, "Add Candidate form must carry a qty input"
    assert 'name="qty"' in tag.group(0)
    assert "required" not in tag.group(0)


def test_fr79_candidate_form_retains_qty_on_error_render(client, db_path):
    response = client.post("/watch", data=candidate_form(company="", qty="200"))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert re.search(r'<input[^>]*id="c-qty"[^>]*value="200"', html)


def test_fr79_ac3_move_without_qty_rejected_with_zero_writes(client, db_path):
    client.post("/watch", data=candidate_form())
    bond_id = candidate_row(db_path, "INE9000A0300")["id"]
    response = client.post(f"/watch/{bond_id}/move", data=move_payload(qty=""))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-move-watching" in html
    assert "qty must be a positive integer" in html
    assert candidate_row(db_path, "INE9000A0300")["watch_state"] == "watching"
    assert ledger_count(db_path) == 0


@pytest.mark.parametrize("bad_value", ["0", "-1", "2.5"])
def test_fr79_ac4_move_bad_qty_rejected_with_zero_writes(client, db_path, bad_value):
    client.post("/watch", data=candidate_form())
    bond_id = candidate_row(db_path, "INE9000A0300")["id"]
    response = client.post(f"/watch/{bond_id}/move", data=move_payload(qty=bad_value))
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-move-watching" in html
    assert "qty must be a positive integer" in html
    assert candidate_row(db_path, "INE9000A0300")["watch_state"] == "watching"
    assert ledger_count(db_path) == 0


def test_fr79_move_with_qty_stored_on_holding_row(client, db_path):
    client.post("/watch", data=candidate_form())
    bond_id = candidate_row(db_path, "INE9000A0300")["id"]
    response = client.post(f"/watch/{bond_id}/move", data=move_payload(qty="200"))
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT watch_state, qty FROM bonds WHERE id = ?", (bond_id,)
        ).fetchone()
    assert row["watch_state"] == "holding"
    assert row["qty"] == 200


def test_fr79_move_panel_qty_required_and_prefilled_from_candidate(client, db_path):
    client.post("/watch", data=candidate_form(qty="175"))
    bond_id = candidate_row(db_path, "INE9000A0300")["id"]
    panel = move_panel(client.get("/watch").get_data(as_text=True), bond_id)
    assert re.search(r'<input[^>]*name="qty"[^>]*required', panel)
    assert 'value="175' in panel
