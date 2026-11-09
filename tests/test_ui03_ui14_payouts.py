import re
from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.phase4 import payout_schedule, tds_breakdown
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def visible_text(fragment):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", fragment)).strip()


def grid_cell(html, bond_id, month):
    match = re.search(
        rf'<td class="cell cell-(\w+)" data-bond="{bond_id}" data-month="{month}"[^>]*>(.*?)</td>',
        html,
        re.S,
    )
    assert match, f"grid cell missing for bond {bond_id} month {month}"
    return match.group(1), visible_text(match.group(2))


def payout_cell(html, bond_id, month):
    marker = f'id="cell-{bond_id}-{month}"'
    assert marker in html, f"payout cell missing for bond {bond_id} month {month}"
    index = html.index(marker)
    start = html.rindex("<td", 0, index)
    end = html.index("</td>", index)
    return html[start:end]


class SimDate(date):
    @classmethod
    def today(cls):
        return date(2026, 10, 10)


def test_ui03_grid_paid_cell_shows_value_only_due_cell_shows_unpaid(client, db_path, monkeypatch):
    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "GridCo", "INE0000001381", "2026-07-01", 6, credit_day=5)
        add_payment(conn, bond_id, "2026-07", 1234.0)
    html = client.get("/grid").get_data(as_text=True)

    state, text = grid_cell(html, bond_id, "2026-07")
    assert state == "paid"
    assert "1234.00" in text
    assert "paid" not in text
    assert "&#10003;" not in text
    assert "\u2713" not in text

    state, text = grid_cell(html, bond_id, "2026-08")
    assert state == "due"
    assert text == "unpaid"

    state, text = grid_cell(html, bond_id, "2026-11")
    assert state == "future"
    assert text == "not due yet"


def test_ui03_grid_has_no_paid_or_due_words(client, db_path, monkeypatch):
    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "WordCo", "INE0000001382", "2026-07-01", 6, credit_day=5)
        add_payment(conn, bond_id, "2026-07", 900.0)
    html = client.get("/grid").get_data(as_text=True)
    assert 'content: "paid"' not in html
    assert 'content: "due"' not in html


def test_ui03_portfolio_payouts_cells_follow_green_red_amber_rule(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    start = add_months(base, -3)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "RuleCo", "INE0000001383", start.isoformat(), 8, credit_day=1)
        add_payment(conn, bond_id, f"{start.year:04d}-{start.month:02d}", 5000.0)
        pending_month = f"{base.year:04d}-{base.month:02d}"
        add_payment(conn, bond_id, pending_month, 8000.0, paid=0)
    missed = add_months(base, -1)
    missed_month = f"{missed.year:04d}-{missed.month:02d}"

    html = client.get("/portfolio?tab=payouts").get_data(as_text=True)

    received = payout_cell(html, bond_id, f"{start.year:04d}-{start.month:02d}")
    assert "month paid" in received
    assert "5000.00" in visible_text(received)
    assert "&#10003;" not in received
    assert "\u2713" not in received
    assert ">paid<" not in received

    soon = payout_cell(html, bond_id, pending_month)
    assert "month soon" in soon
    assert "due soon" in visible_text(soon)
    assert "data-amount" not in soon
    assert "8000" not in visible_text(soon)

    unpaid = payout_cell(html, bond_id, missed_month)
    assert "month unpaid" in unpaid
    assert "unpaid" in visible_text(unpaid)
    assert "Missed" not in unpaid


def test_ui03_portfolio_payouts_prestart_cells_show_neutral_dash(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    early = add_months(base, -5)
    late = add_months(base, -1)
    with get_conn(db_path) as conn:
        add_bond(conn, "EarlyCo", "INE0000001388", early.isoformat(), 10, credit_day=5)
        late_id = add_bond(conn, "LateCo", "INE0000001389", late.isoformat(), 10, credit_day=5)
    html = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    early_month = f"{early.year:04d}-{early.month:02d}"
    cell = payout_cell(html, late_id, early_month)
    assert "month neutral" in cell
    assert visible_text(cell) == "\u2014"
    assert "not due yet" not in cell


def test_ui03_payout_matrices_have_sticky_company_column(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "StickyCo", "INE0000001384", "2026-07-01", 6, credit_day=5)
    grid = client.get("/grid").get_data(as_text=True)
    payouts = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    assert "position: sticky" in grid
    assert ".grid-table th:first-child" in grid
    assert "position: sticky" in payouts
    assert ".payouts-table th:first-child" in payouts


def test_ui14_tds_math_reuses_phase4_helper():
    assert tds_breakdown(6330) == {"net": 6330, "tds": 703, "gross": 7033}
    assert tds_breakdown(6330, False) == {"net": 6330, "tds": 0, "gross": 6330}


def test_ui14_payment_editor_renders_net_input_toggle_breakdown_and_explainer(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "EditorCo", "INE0000001385", "2026-07-01", 6, credit_day=5)
        add_payment(conn, bond_id, "2026-07", 6330.0)
    html = client.get(f"/payment/{bond_id}/2026-07").get_data(as_text=True)
    assert 'id="tds-toggle"' in html
    assert "TDS deducted (10%" in html
    assert 'id="tds-net" data-amount="6330.00"' in html
    assert 'id="tds-amount" data-amount="703.00"' in html
    assert 'id="tds-gross" data-amount="7033.00"' in html
    assert "Net (you entered)" in html
    assert "Deductions (TDS 10% of interest)" in html
    assert "Gross (net / 0.9)" in html
    assert "You entered the NET credit; gross = net / 0.9 and TDS = net / 9." in html
    assert "interest only" in html
    assert "never to principal" in html
    assert "claimable tax credit" in html
    assert "Official TDS deposits round to the nearest Rs 10 (s.288B); this app shows exact whole-rupee values for clarity." in html


def test_ui14_dashboard_kpi_shows_net_plus_tds_equals_gross(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "KpiCo", "INE0000001386", add_months(base, -2).isoformat(), 6, credit_day=5)
        add_payment(conn, bond_id, f"{add_months(base, -1).year:04d}-{add_months(base, -1).month:02d}", 4500.0)
    html = client.get("/").get_data(as_text=True)
    assert 'id="received-total" data-amount="4500.00"' in html
    assert 'id="received-net" data-amount="4500.00"' in html
    assert 'id="received-tds" data-amount="500.00"' in html
    assert 'id="received-gross" data-amount="5000.00"' in html


def test_ui14_accuracy_gate_dashboard_portfolio_payouts_agree(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    off_month = base
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "AgreeCo", "INE0000001387", add_months(base, -3).isoformat(), 10, credit_day=5)
        conn.execute(
            "UPDATE bonds SET interest_payout = ?, payment_type = ? WHERE id = ?",
            (90000.0, "Monthly", bond_id),
        )
        for offset in range(3):
            month = add_months(base, -3 + offset)
            add_payment(conn, bond_id, f"{month.year:04d}-{month.month:02d}", 9000.0)
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid, tds_applied) VALUES (?, ?, ?, 1, 0)",
            (bond_id, f"{off_month.year:04d}-{off_month.month:02d}", 5000.0),
        )

    net_total = 32000.0
    expected_tds = 3000
    expected_gross = 35000

    dashboard = client.get("/").get_data(as_text=True)
    assert f'id="received-total" data-amount="{net_total:.2f}"' in dashboard
    assert f'id="received-tds" data-amount="{expected_tds:.2f}"' in dashboard
    assert f'id="received-gross" data-amount="{expected_gross:.2f}"' in dashboard

    detail = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert detail["received"] == net_total
    assert detail["tds"] == expected_tds
    assert detail["gross"] == expected_gross
    off_rows = [row for row in detail["payments"] if row["tds_applied"] is False]
    assert len(off_rows) == 1
    assert off_rows[0]["amount"] == 5000.0
    assert tds_breakdown(off_rows[0]["amount"], off_rows[0]["tds_applied"]) == {
        "net": 5000,
        "tds": 0,
        "gross": 5000,
    }
    on_rows = [row for row in detail["payments"] if row["tds_applied"] is True]
    assert len(on_rows) == 3
    assert tds_breakdown(on_rows[0]["amount"], on_rows[0]["tds_applied"]) == {
        "net": 9000,
        "tds": 1000,
        "gross": 10000,
    }

    with get_conn(db_path) as conn:
        schedule = payout_schedule(conn, bond_id, "monthly")
    instance = schedule["instances"][0]
    instance_breakdown = tds_breakdown(instance["net"])
    assert instance_breakdown["net"] == instance["net"]
    assert instance_breakdown["tds"] == instance["tds"]
    assert instance_breakdown["gross"] == instance["amount"]
    assert schedule["total_amount"] == 90000.0
    assert tds_breakdown(schedule["total_net"])["gross"] == schedule["total_amount"]


def test_ui14_payment_toggle_persists_per_row(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "ToggleCo", "INE0000001390", "2026-07-01", 6, credit_day=5)

    response = client.post(
        f"/payment/{bond_id}/2026-07",
        data={"amount": "9000", "paid": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT amount, paid, tds_applied FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, "2026-07"),
        ).fetchone()
    assert row["tds_applied"] == 0
    editor = client.get(f"/payment/{bond_id}/2026-07").get_data(as_text=True)
    assert 'name="tds"' in editor
    assert 'name="tds" checked' not in editor
    assert 'id="tds-amount" data-amount="0.00"' in editor
    assert 'id="tds-gross" data-amount="9000.00"' in editor

    response = client.post(
        f"/payment/{bond_id}/2026-07",
        data={"amount": "9000", "paid": "on", "tds": "on"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT tds_applied FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, "2026-07"),
        ).fetchone()
    assert row["tds_applied"] == 1
    editor = client.get(f"/payment/{bond_id}/2026-07").get_data(as_text=True)
    assert 'name="tds" checked' in editor
    assert 'id="tds-amount" data-amount="1000.00"' in editor
    assert 'id="tds-gross" data-amount="10000.00"' in editor
