import re
from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.status import month_key
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def month_key_of(day):
    return f"{day.year:04d}-{day.month:02d}"


def norm_markup(text):
    without_tags = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", without_tags).strip()


def facts_value(html, label):
    match = re.search(
        r'<span class="fact-label">'
        + re.escape(label)
        + r'</span><span class="fact-value">(.*?)</span></div>',
        html,
        re.S,
    )
    assert match, f"fact label missing: {label}"
    return norm_markup(match.group(1))


def strip_value(strip_html, label):
    match = re.search(
        r'<span class="attr-row"><b>'
        + re.escape(label)
        + r":</b>\s*(.*?)</span>",
        strip_html,
        re.S,
    )
    assert match, f"strip label missing: {label}"
    return norm_markup(match.group(1))


def single_strip(html):
    match = re.search(r'<td colspan="10" class="attr-strip">(.*?)</td>', html, re.S)
    assert match, "holdings attribute strip missing"
    return match.group(1)


def single_details(html):
    match = re.search(
        r'<tr class="details-row" id="details-\d+" hidden>\s*<td colspan="8">(.*?)</td>\s*</tr>',
        html,
        re.S,
    )
    assert match, "watchlist details grid missing"
    return match.group(1)


def seed_missed_current_month(db_path):
    today = date.today()
    base = today.replace(day=1)
    start = add_months(base, -2)
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "Edit Co", "INE1290000001", start.isoformat(), 6, credit_day=1
        )
        add_payment(conn, bond_id, month_key(start), 1000.0, paid=1)
        add_payment(conn, bond_id, month_key(add_months(start, 1)), 1000.0, paid=1)
    return bond_id, base


def test_tc129_payout_edit_saves_via_existing_payment_route_and_status_rerederives(
    client, db_path
):
    bond_id, base = seed_missed_current_month(db_path)
    current = month_key(base)
    holdings_before = client.get("/portfolio").get_data(as_text=True)
    assert f'data-isin="INE1290000001" data-status="Danger"' in holdings_before
    response = client.post(
        f"/payment/{bond_id}/{current}",
        data={"amount": "7500", "paid": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/grid"
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, current),
        ).fetchall()
    assert len(rows) == 1
    assert float(rows[0]["amount"]) == 7500.0
    assert rows[0]["paid"] == 1
    payouts = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    cell_marker = f'id="cell-{bond_id}-{current}"'
    assert cell_marker in payouts
    cell_index = payouts.index(cell_marker)
    cell_slice = payouts[cell_index : cell_index + 400]
    assert 'data-amount="7500.00" data-received="1"' in cell_slice
    assert "&#8377;7500.00" in cell_slice
    assert "&#10003;" not in cell_slice
    assert ">paid<" not in cell_slice
    holdings_after = client.get("/portfolio").get_data(as_text=True)
    assert 'data-isin="INE1290000001" data-status="On-going"' in holdings_after
    response = client.post(
        f"/payment/{bond_id}/{month_key(add_months(base, -1))}",
        data={"amount": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, month_key(add_months(base, -1))),
        ).fetchall()
    assert len(rows) == 1
    assert float(rows[0]["amount"]) == 0.0
    assert rows[0]["paid"] == 0
    payouts_after = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    cleared_index = payouts_after.index(f'id="cell-{bond_id}-{month_key(add_months(base, -1))}"')
    cleared_slice = payouts_after[cleared_index : cleared_index + 400]
    assert 'data-amount="" data-received="0"' in cleared_slice
    assert ">unpaid<" in cleared_slice
    holdings_cleared = client.get("/portfolio").get_data(as_text=True)
    assert 'data-isin="INE1290000001" data-status="Danger"' in holdings_cleared


def test_tc130_payouts_month_headers_newest_first_and_never_future(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    start = add_months(base, -3)
    future_key = month_key(add_months(base, 1))
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "Window Co", "INE1300000001", start.isoformat(), 12, credit_day=5
        )
        for offset in range(3):
            add_payment(conn, bond_id, month_key(add_months(start, offset)), 500.0, paid=1)
        add_payment(conn, bond_id, future_key, 100.0, paid=1)
    html = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    headers = re.findall(r'<th data-month="(\d{4}-\d{2})">', html)
    assert headers, "payouts grid must render month columns"
    current = month_key_of(base)
    assert headers[0] == current
    assert headers == sorted(headers, reverse=True)
    assert len(headers) == len(set(headers))
    assert all(header <= current for header in headers)
    assert future_key not in headers
    assert "newest month first" in html
    assert "Future months are never shown" in html


def test_tc133_attribute_parity_roundtrip_candidate_move_holdings_strip(client, db_path):
    response = client.post(
        "/watch",
        data={
            "company": "Parity Co",
            "isin": "INE133000001",
            "rating": "AA",
            "rating_agency": "CRISIL",
            "coupon_pct": "8.5",
            "expected_yield_pct": "9.1",
            "issuer_type": "ncd",
            "secured": "0",
            "face_value": "1000",
            "payout_cycle": "monthly",
            "watch_investment": "50000",
            "source_note": "saw in grip",
            "broker": "HDFC Securities",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    watch_html = client.get("/watch").get_data(as_text=True)
    details = single_details(watch_html)
    labels = (
        "Rating agency",
        "Issuer type",
        "Secured",
        "Face value",
        "Payout cycle",
        "Broker",
        "Source note",
    )
    details_values = {label: facts_value(details, label) for label in labels}
    assert details_values["Rating agency"] == "CRISIL"
    assert details_values["Issuer type"] == "NCD"
    assert details_values["Secured"] == "Not secured"
    assert details_values["Face value"] == "&#8377;1000.00"
    assert details_values["Payout cycle"] == "Monthly"
    assert details_values["Broker"] == "HDFC Securities"
    assert details_values["Source note"] == "saw in grip"
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE133000001'"
        ).fetchone()["id"]
    today = date.today()
    base = today.replace(day=1)
    response = client.post(
        f"/watch/{candidate_id}/move",
        data={
            "purchase_date": add_months(base, -2).isoformat(),
            "start_date": add_months(base, -1).isoformat(),
            "end_date": add_months(base, 12).isoformat(),
            "credit_day": "5",
            "qty": "50",
            "amount": "50000",
            "broker": "HDFC Securities",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    portfolio_html = client.get("/portfolio").get_data(as_text=True)
    strip = single_strip(portfolio_html)
    strip_values = {label: strip_value(strip, label) for label in labels}
    for label in labels:
        assert strip_values[label] == details_values[label], label
    assert "&#8377;50000.00" in portfolio_html
    detail = client.get(f"/portfolio/{candidate_id}/detail").get_json()
    assert detail["rating_agency"] == "CRISIL"
    assert detail["issuer_type"] == "ncd"
    assert int(detail["secured"]) == 0
    assert float(detail["face_value"]) == 1000.0
    assert detail["source_note"] == "saw in grip"
    assert detail["broker"] == "HDFC Securities"
    assert detail["frequency"] == "monthly"


def test_tc137_move_inline_panel_renders_bound_labels_below_row(client, db_path):
    response = client.post(
        "/watch",
        data={
            "company": "Panel Co",
            "isin": "INE137000001",
            "rating": "AA-",
            "coupon_pct": "8.8",
            "expected_yield_pct": "9.3",
            "broker": "india bonds",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    html = client.get("/watch").get_data(as_text=True)
    assert "Purchase date" in html
    assert "Start date (interest accrual / dated date)" in html
    assert "End date" in html
    assert "Credit day — when the amount is credited each month" in html
    assert ">Broker</label>" in html
    assert "Move to Portfolio" in html
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE137000001'"
        ).fetchone()["id"]
    panel = re.search(
        r'<tr class="move-row" id="move-panel-' + str(candidate_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert panel, "move panel must exist as a hidden row below its candidate"
    panel_html = panel.group(1)
    assert "Purchase date" in panel_html
    assert "Start date (interest accrual / dated date)" in panel_html
    assert "End date" in panel_html
    assert "Credit day — when the amount is credited each month" in panel_html
    assert "Broker" in panel_html
    assert f'action="/watch/{candidate_id}/move"' in panel_html
    assert "move-cancel" in panel_html
    assert ">Cancel</button>" in panel_html
    assert f'id="move-{candidate_id}"' in panel_html
    toggle_index = html.index(f'id="move-toggle-{candidate_id}"')
    panel_index = html.index(f'id="move-panel-{candidate_id}" hidden')
    assert toggle_index < panel_index
    action_cell = re.search(
        r'<td>\s*<button type="button" class="btn btn-sm move-toggle" '
        + f'data-panel="move-panel-{candidate_id}"'
        + r'[^>]*>Move to Portfolio</button>.*?'
        + f'action="/watch/{candidate_id}/delete"'
        + r'.*?</td>',
        html,
        re.S,
    )
    assert action_cell, "Action cell must carry the Move to Portfolio toggle and the Delete control"
