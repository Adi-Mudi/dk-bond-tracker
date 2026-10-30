import re
from datetime import date

import pytest

from conftest import add_bond, add_payment, month_sequence
from src.alerts import daily_sweep
from src.app import create_app
from src.db import get_conn


def make_sim_date(frozen):
    class SimDate(date):
        @classmethod
        def today(cls):
            return frozen

    return SimDate


def company_order(html):
    return re.findall(r'grid-company">([^<]+)</td>', html)


def status_order(html):
    return re.findall(r'data-status="([^"]+)"', html)


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_alpha_beta_gamma(db_path):
    with get_conn(db_path) as conn:
        alpha_id = add_bond(conn, "Alpha", "INE0000000751", "2026-10-01", 6, credit_day=15)
        beta_id = add_bond(conn, "Beta", "INE0000000752", "2026-08-01", 6, credit_day=5)
        gamma_id = add_bond(conn, "Gamma", "INE0000000753", "2026-08-01", 2, credit_day=5)
        add_payment(conn, gamma_id, "2026-08", 1000.0)
        add_payment(conn, gamma_id, "2026-09", 1000.0)
    return alpha_id, beta_id, gamma_id


def test_tc75_initial_order_is_danger_ongoing_completed(client, db_path, monkeypatch):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 10)))
    seed_alpha_beta_gamma(db_path)
    html = client.get("/grid").get_data(as_text=True)
    assert company_order(html) == ["Beta", "Alpha", "Gamma"]
    assert status_order(html) == ["Danger", "On-going", "Completed"]


def test_tc75_order_changes_on_next_get_after_status_flips(client, db_path, monkeypatch):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 10)))
    alpha_id, beta_id, gamma_id = seed_alpha_beta_gamma(db_path)
    before = client.get("/grid").get_data(as_text=True)
    assert company_order(before) == ["Beta", "Alpha", "Gamma"]
    with get_conn(db_path) as conn:
        for month in month_sequence("2026-10", 6):
            add_payment(conn, alpha_id, month, 1000.0)
        conn.execute(
            "UPDATE payment_ledger SET amount = 0, paid = 0 "
            "WHERE bond_id = ? AND month = '2026-08'",
            (gamma_id,),
        )
    after = client.get("/grid").get_data(as_text=True)
    assert company_order(after) == ["Beta", "Gamma", "Alpha"]
    assert status_order(after) == ["Danger", "Danger", "Completed"]
    assert company_order(after) != company_order(before)


def test_tc75_sweep_flip_moves_new_danger_row_to_top(client, db_path, monkeypatch):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 10)))
    with get_conn(db_path) as conn:
        alpha_id = add_bond(conn, "Alpha", "INE0000000754", "2026-10-01", 6, credit_day=15)
        beta_id = add_bond(conn, "Beta", "INE0000000755", "2026-10-01", 6, credit_day=15)
        gamma_id = add_bond(conn, "Gamma", "INE0000000756", "2026-10-01", 6, credit_day=15)
        add_payment(conn, alpha_id, "2026-10", 1000.0)
        add_payment(conn, gamma_id, "2026-10", 1000.0)
    first = client.get("/grid").get_data(as_text=True)
    assert company_order(first) == ["Alpha", "Beta", "Gamma"]
    assert status_order(first) == ["On-going", "On-going", "On-going"]
    with get_conn(db_path) as conn:
        events = daily_sweep(conn, date(2026, 10, 20))
    assert [event["company"] for event in events] == ["Beta"]
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 20)))
    second = client.get("/grid").get_data(as_text=True)
    assert company_order(second) == ["Beta", "Alpha", "Gamma"]
    assert status_order(second)[0] == "Danger"
    assert second != first


def test_tc75_sort_is_stable_within_status_band(client, db_path, monkeypatch):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 10)))
    with get_conn(db_path) as conn:
        add_bond(conn, "Zulu", "INE0000000757", "2026-10-01", 6, credit_day=15)
        add_bond(conn, "Mike", "INE0000000758", "2026-10-01", 6, credit_day=15)
        add_bond(conn, "Alfa", "INE0000000759", "2026-10-01", 6, credit_day=15)
    html = client.get("/grid").get_data(as_text=True)
    assert company_order(html) == ["Alfa", "Mike", "Zulu"]
