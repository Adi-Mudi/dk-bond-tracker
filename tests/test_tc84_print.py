from datetime import date

import pytest

from conftest import add_bond, add_payment, pay_range
from src.app import create_app
from src.db import get_conn
from src.validators import add_months

SECTION_IDS = (
    'id="print-header"',
    'id="print-summary"',
    'id="print-payments"',
    'id="print-status"',
    'id="print-alerts"',
)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_statement(db_path, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    with get_conn(db_path) as conn:
        danger_id = add_bond(conn, "Danger Co", "INE0000000841", add_months(base, -3).isoformat(), 6, credit_day=12, amount=100000.0)
        ongoing_id = add_bond(conn, "Ongoing Co", "INE0000000842", add_months(base, -2).isoformat(), 6, credit_day=7, amount=60000.0)
        completed_start = add_months(base, -2)
        completed_id = add_bond(conn, "Done Co", "INE0000000843", completed_start.isoformat(), 1, credit_day=3, amount=20000.0)
        pay_range(conn, completed_id, f"{completed_start.year:04d}-{completed_start.month:02d}", 1, amount=1000.0)
        danger_start = add_months(base, -3)
        add_payment(conn, danger_id, f"{danger_start.year:04d}-{danger_start.month:02d}", 1500.0)
        ongoing_start = add_months(base, -2)
        pay_range(conn, ongoing_id, f"{ongoing_start.year:04d}-{ongoing_start.month:02d}", 3, amount=900.0)
        month_prefix = current
        conn.execute(
            "INSERT INTO notifications (created_at, severity, message, read) VALUES (?, 'danger', ?, 0)",
            (f"{month_prefix}-05 09:00:00", "Danger Co credit day 12 missed"),
        )
        conn.execute(
            "INSERT INTO notifications (created_at, severity, message, read) VALUES (?, 'reminder', ?, 0)",
            (f"{month_prefix}-11 09:00:00", "Ongoing Co payment due in 2 days"),
        )
        conn.execute(
            "INSERT INTO notifications (created_at, severity, message, read) VALUES ('2020-01-05 09:00:00', 'info', 'old alert', 0)"
        )


def money_values_present(html):
    return "100000.00" in html or "60000.00" in html or "₹" in html


def test_tc84_print_has_exactly_five_section_markers(client, db_path):
    seed_statement(db_path, date.today())
    response = client.get("/print")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    positions = []
    for marker in SECTION_IDS:
        assert marker in html, marker
        positions.append(html.index(marker))
    assert positions == sorted(positions)
    assert html.count('class="sec"') + html.count('st-title-block') + html.count('st-footer') >= 5


def test_tc84_month_header_present(client, db_path):
    today = date.today()
    seed_statement(db_path, today)
    html = client.get("/print").get_data(as_text=True)
    month_label = f"{today.strftime('%B')} {today.year}"
    assert f"Monthly Statement — {month_label}" in html
    assert month_label in html
    assert today.strftime("%d-%b-%Y") in html


def test_tc84_all_bond_rows_present(client, db_path):
    seed_statement(db_path, date.today())
    html = client.get("/print").get_data(as_text=True)
    for company, isin in (
        ("Danger Co", "INE0000000841"),
        ("Ongoing Co", "INE0000000842"),
        ("Done Co", "INE0000000843"),
    ):
        assert company in html
        assert isin in html
    assert 'id="print-payments"' in html
    assert "no payments this month" not in html


def test_tc84_due_dates_are_credit_day_iso_dates(client, db_path):
    today = date.today()
    seed_statement(db_path, today)
    html = client.get("/print").get_data(as_text=True)
    for credit_day in (12, 7, 3):
        expected = f"{today.year:04d}-{today.month:02d}-{credit_day:02d}"
        assert expected in html


def test_tc84_status_groups_ordered_danger_first(client, db_path):
    seed_statement(db_path, date.today())
    html = client.get("/print").get_data(as_text=True)
    danger = html.index('id="status-group-danger"')
    ongoing = html.index('id="status-group-ongoing"')
    completed = html.index('id="status-group-completed"')
    assert danger < ongoing < completed
    assert "Danger Co (INE0000000841)" in html


def test_tc84_payment_rows_ordered_danger_first(client, db_path):
    seed_statement(db_path, date.today())
    html = client.get("/print").get_data(as_text=True)
    table = html[html.index('id="print-payments"') : html.index('id="print-status"')]
    assert table.index("Danger Co") < table.index("Ongoing Co") < table.index("Done Co")


def test_tc84_bw_markers_present(client, db_path):
    seed_statement(db_path, date.today())
    html = client.get("/print").get_data(as_text=True)
    for marker in ("● D", "○ O", "● C"):
        assert marker in html, marker
    assert "Legend" in html
    assert "row-danger" in html
    assert "row-completed" in html


def test_tc84_a4_page_css_and_print_button(client, db_path):
    seed_statement(db_path, date.today())
    html = client.get("/print").get_data(as_text=True)
    assert "@page" in html
    assert "size: A4" in html
    assert "A4 portrait" in html
    assert "window.print()" in html
    assert 'class="a4"' in html


def test_tc84_alerts_footer_counts_and_last_sweep(client, db_path):
    today = date.today()
    seed_statement(db_path, today)
    html = client.get("/print").get_data(as_text=True)
    assert 'id="print-alerts"' in html
    assert "2 alerts this month" in html
    assert "Danger Co credit day 12 missed" in html
    assert "old alert" not in html
    assert f"last sweep {today.isoformat()}" in html


def test_tc84_privacy_off_shows_real_amounts(client, db_path):
    seed_statement(db_path, date.today())
    html = client.get("/print").get_data(as_text=True)
    assert "privacy-on" not in html.split("<body", 1)[1].split(">", 1)[0]
    assert "₹180000.00" in html
    assert 'data-amount="180000.00"' in html
    assert "₹900.00" in html
    assert "••••" in html


def test_tc84_privacy_1_masks_all_money(client, db_path):
    seed_statement(db_path, date.today())
    response = client.get("/print?privacy=1")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    body_tag = html.split("<body", 1)[1].split(">", 1)[0]
    assert "privacy-on" in body_tag
    assert "••••" in html
    assert "₹" not in html
    assert "data-amount" not in html
    for raw in ("180000.00", "5200.00", "1500.00", "900.00", "-7800.00"):
        assert raw not in html, raw
    assert ".privacy-on .money" in html
    assert "Danger Co" in html
    assert "INE0000000842" in html
    assert "On-going" in html


def test_tc84_privacy_1_masks_printed_sections_only_money(client, db_path):
    today = date.today()
    seed_statement(db_path, today)
    html = client.get("/print?privacy=1").get_data(as_text=True)
    assert f"{today.year:04d}-{today.month:02d}-12" in html
    assert "12" in html
    assert "2 alerts this month" in html
    assert "2026" in html or f"{today.year:04d}" in html


def test_tc84_empty_portfolio_renders_sections(client, db_path):
    response = client.get("/print")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    for marker in SECTION_IDS:
        assert marker in html, marker
    assert "no payments this month" in html
    assert "no alerts this month" in html
    assert "none" in html
