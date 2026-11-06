import re
from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def cell_class(html, bond_id, month):
    match = re.search(
        rf'<td class="cell cell-(\w+)" data-bond="{bond_id}" data-month="{month}"',
        html,
    )
    return match.group(1) if match else None


def test_tc35_paid_due_zero_future_cells_and_status_colors(db_path, monkeypatch):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 10)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        danger_id = add_bond(conn, "DangerCo", "INE0000000351", "2026-07-01", 6, credit_day=5)
        add_payment(conn, danger_id, "2026-07", 1000.0)
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            (danger_id, "2026-08", 0.0, 1),
        )
        ongoing_id = add_bond(conn, "OngoingCo", "INE0000000352", "2026-10-01", 6, credit_day=15)
        completed_id = add_bond(conn, "DoneCo", "INE0000000353", "2026-08-01", 2, credit_day=5)
        add_payment(conn, completed_id, "2026-08", 1000.0)
        add_payment(conn, completed_id, "2026-09", 1000.0)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/grid")
    assert response.status_code == 200
    html = response.get_data(as_text=True)

    assert cell_class(html, danger_id, "2026-07") == "paid"
    assert cell_class(html, danger_id, "2026-08") == "due"
    assert cell_class(html, danger_id, "2026-09") == "due"
    assert cell_class(html, danger_id, "2026-10") == "due"
    assert cell_class(html, danger_id, "2026-11") == "future"
    assert cell_class(html, ongoing_id, "2026-11") == "future"
    assert cell_class(html, completed_id, "2026-08") == "paid"

    assert 'cell cell-paid' in html
    assert 'cell cell-due' in html
    assert 'cell cell-future' in html
    css = app.test_client().get("/static/theme.css").get_data(as_text=True)
    assert "--page-bg: #f8f9fa" in css
    assert "--card-bg: #f1f3f5" in css
    assert "--white: #ffffff" in css
    assert "--blue-light: #d0ebff" in css
    assert "--paid: #d3f9d8" in css
    assert "--due: #ffc9c9" in css
    assert "--danger: #ff8787" in css
    assert "--ongoing: #ff922b" in css
    assert "--completed: #69db7c" in css
    assert "--current-month: #fff3bf" in css
    assert "--header-row: #e9ecef" in css
    assert "--paid: #10251a" in css
    assert "--due: #2b1519" in css
    assert ".cell-paid { background: var(--paid); }" in html
    assert ".cell-due { background: var(--due); font-weight: 700; }" in html

    assert 'data-status="Danger"' in html
    assert 'data-status="On-going"' in html
    assert 'data-status="Completed"' in html
    assert 'chip chip-danger' in html
    assert 'chip chip-ongoing' in html
    assert 'chip chip-completed' in html

    assert 'th class="month-col now" data-month="2026-10"' in html


def test_tc35_zero_amount_cell_never_renders_green(db_path, monkeypatch):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2026, 10, 10)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "ZeroCo", "INE0000000354", "2026-07-01", 6, credit_day=5)
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            (bond_id, "2026-08", 0.0, 1),
        )
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/grid").get_data(as_text=True)
    assert cell_class(html, bond_id, "2026-08") == "due"
    assert f'cell cell-paid" data-bond="{bond_id}" data-month="2026-08"' not in html
