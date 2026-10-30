from datetime import date

import pytest

from conftest import add_bond, add_payment, pay_range
from src.app import create_app
from src.db import get_conn
from src.phase4 import pnl_summary
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_pnl_portfolio(conn, today):
    base = today.replace(day=1)
    ongoing_id = add_bond(
        conn, "OngoingCo", "INETC40001", base.isoformat(), 6, amount=100000.0, maturity=120000.0
    )
    add_payment(conn, ongoing_id, f"{base.year:04d}-{base.month:02d}", 1500.0)
    completed_id = add_bond(
        conn,
        "DoneCo",
        "INETC40002",
        add_months(base, -2).isoformat(),
        1,
        amount=50000.0,
        maturity=60000.0,
    )
    pay_range(conn, completed_id, f"{add_months(base, -2).year:04d}-{add_months(base, -2).month:02d}", 1, amount=800.0)
    danger_id = add_bond(
        conn,
        "DangerCo",
        "INETC40003",
        add_months(base, -2).isoformat(),
        6,
        amount=20000.0,
        maturity=24000.0,
    )
    return ongoing_id, completed_id, danger_id


def test_tc40_pnl_summary_structure_and_proposed_formula(db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_pnl_portfolio(conn, today)
        result = pnl_summary(conn, today)
    assert set(result) >= {"till_return", "investment", "pnl", "ongoing_tl", "l2_status", "l2_note"}
    assert result["till_return"] == pytest.approx(2300.0)
    assert result["investment"] == pytest.approx(170000.0)
    assert result["pnl"] == pytest.approx(result["till_return"] - result["investment"])
    assert result["pnl"] == pytest.approx(2300.0 - 170000.0)


def test_tc40_ongoing_tl_sums_only_ongoing_principal(db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_pnl_portfolio(conn, today)
        result = pnl_summary(conn, today)
    assert result["ongoing_tl"] == pytest.approx(100000.0)


def test_tc40_all_completed_yields_zero_ongoing_tl(db_path):
    today = date.today()
    base = today.replace(day=1)
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "Solo", "INETC40004", add_months(base, -2).isoformat(), 1, amount=10000.0
        )
        pay_range(conn, bond_id, f"{add_months(base, -2).year:04d}-{add_months(base, -2).month:02d}", 1)
        result = pnl_summary(conn, today)
    assert result["ongoing_tl"] == 0.0
    assert result["investment"] == pytest.approx(10000.0)


def test_tc40_empty_portfolio_genuine_zeros(db_path):
    with get_conn(db_path) as conn:
        result = pnl_summary(conn, date.today())
    assert result["till_return"] == 0.0
    assert result["investment"] == 0.0
    assert result["pnl"] == 0.0
    assert result["ongoing_tl"] == 0.0


def test_tc40_l2_status_pending_confirmation_names_both_formulas(db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_pnl_portfolio(conn, today)
        result = pnl_summary(conn, today)
    assert result["l2_status"] == "PENDING_CONFIRMATION"
    note = result["l2_note"]
    assert "Till Return - Investment" in note
    assert "maturity - investment" in note
    assert "PROPOSED" in note


def test_tc40_dashboard_card_shows_proposed_value_and_l2_badge(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_pnl_portfolio(conn, today)
        result = pnl_summary(conn, today)
    html = client.get("/").get_data(as_text=True)
    assert 'id="card-pnl"' in html
    assert 'id="pnl-l2-badge"' in html
    assert "L2 pending owner confirmation" in html
    assert 'data-l2-status="PENDING_CONFIRMATION"' in html
    assert "{:.2f}".format(result["pnl"]) in html
    assert "{:.2f}".format(result["ongoing_tl"]) in html
    assert "proposed formula" in html
    assert "not yet owner-confirmed" in html


def test_tc40_dashboard_never_claims_pnl_approved(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_pnl_portfolio(conn, today)
    html = client.get("/").get_data(as_text=True)
    assert "P&L confirmed" not in html
    assert "owner approved" not in html
    assert "L2 pending owner confirmation" in html


def test_tc40_pnl_reflects_ledger_edit_on_next_request(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    with get_conn(db_path) as conn:
        ongoing_id = add_bond(
            conn, "LiveCo", "INETC40005", base.isoformat(), 6, amount=10000.0
        )
    before = client.get("/").get_data(as_text=True)
    assert "&#8377;-10000.00" in before
    with get_conn(db_path) as conn:
        add_payment(conn, ongoing_id, f"{base.year:04d}-{base.month:02d}", 500.0)
    after = client.get("/").get_data(as_text=True)
    assert "&#8377;-9500.00" in after
