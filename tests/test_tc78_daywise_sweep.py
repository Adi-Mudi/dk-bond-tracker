from datetime import date

import pytest

from conftest import add_bond, bond_status
from src.alerts import daily_sweep
from src.app import create_app
from src.db import get_conn
from src.ledger import save_payment
from src.queries import grid_model, status_overview, summary_counts
from src.status import compute_row_status_daywise, recompute_all
from src.validators import AppError


def make_sim_date(frozen):
    class SimDate(date):
        @classmethod
        def today(cls):
            return frozen

    return SimDate


def test_tc78_day6_unpaid_flips_danger_same_day(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000078", "2026-09-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        conn.execute(
            "UPDATE bonds SET status = 'On-going' WHERE id = ?",
            (bond_id,),
        )
        events = daily_sweep(conn, date(2026, 10, 6))
        assert events == [
            {
                "bond_id": bond_id,
                "company": "Alpha",
                "month": "2026-10",
                "credit_day": 5,
                "severity": "danger",
            }
        ]
        assert bond_status(conn, bond_id) == "Danger"


def test_tc78_day4_unpaid_is_not_danger_from_current_month(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000784", "2026-09-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        events = daily_sweep(conn, date(2026, 10, 4))
        assert events == []
        assert bond_status(conn, bond_id) == "On-going"


def test_tc78_paid_month_stays_ongoing_across_days(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Beta", "INE0000000078", "2026-09-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        save_payment(conn, bond_id, "2026-10", 1000.0, 1)
        for day in (6, 15, 28, 30):
            events = daily_sweep(conn, date(2026, 10, day))
            assert events == []
        assert bond_status(conn, bond_id) == "On-going"


def test_tc78_completed_position_untouched_even_with_unpaid_future_rows(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Gamma", "INE0000000785", "2026-08-01", 2, credit_day=5)
        save_payment(conn, bond_id, "2026-08", 1000.0, 1)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            (bond_id, "2026-10", 0.0, 0),
        )
        recompute_all(conn, date(2026, 10, 6))
        assert bond_status(conn, bond_id) == "Completed"
        events = daily_sweep(conn, date(2026, 10, 6))
        assert events == []
        assert bond_status(conn, bond_id) == "Completed"


def test_tc78_ledger_completed_guard_even_if_stored_status_stale(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Delta", "INE0000000786", "2026-08-01", 2, credit_day=5, status="On-going")
        save_payment(conn, bond_id, "2026-08", 1000.0, 1)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        events = daily_sweep(conn, date(2026, 10, 6))
        assert events == []
        assert bond_status(conn, bond_id) == "On-going"


def test_tc78_not_started_position_not_flipped(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Epsilon", "INE0000000787", "2026-11-01", 12, credit_day=5)
        events = daily_sweep(conn, date(2026, 10, 6))
        assert events == []
        assert bond_status(conn, bond_id) == "On-going"


def test_tc78_helper_daywise_semantics():
    months = {"2026-09": True, "2026-10": False}
    assert compute_row_status_daywise(months, 12, 5, date(2026, 10, 6)) == "Danger"
    months_paid = {"2026-09": True, "2026-10": True}
    assert compute_row_status_daywise(months_paid, 12, 5, date(2026, 10, 6)) == "On-going"
    assert compute_row_status_daywise(months, 12, 5, date(2026, 10, 4)) == "On-going"
    completed = {"2026-08": True, "2026-09": True, "2026-10": False}
    assert compute_row_status_daywise(completed, 2, 5, date(2026, 10, 6)) == "Completed"


def test_tc78_sweep_rejects_bad_today(db_path):
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            daily_sweep(conn, "2026-10-06")
        assert exc_info.value.code == "ERR-credit-sweep"


def test_tc78_sweep_rejects_missing_credit_day(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Zeta", "INE0000000788", "2026-09-01", 12, credit_day=5)
        conn.execute("UPDATE bonds SET credit_day = NULL WHERE id = ?", (bond_id,))
        with pytest.raises(AppError) as exc_info:
            daily_sweep(conn, date(2026, 10, 6))
        assert exc_info.value.code == "ERR-credit-sweep"
        assert str(bond_id) in exc_info.value.message


def test_tc78_old_unpaid_month_keeps_danger_without_new_event(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Eta", "INE0000000789", "2026-08-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-08", 1000.0, 1)
        conn.execute("UPDATE bonds SET status = 'Danger' WHERE id = ?", (bond_id,))
        events = daily_sweep(conn, date(2026, 10, 6))
        assert len(events) == 1
        assert events[0]["month"] == "2026-10"
        assert events[0]["severity"] == "danger"
        assert bond_status(conn, bond_id) == "Danger"


def test_tc78_summary_counts_overview_and_grid_agree_in_active_daywise_danger(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "SyncCo", "INE000000078A", "2026-09-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        conn.execute("UPDATE bonds SET status = 'On-going' WHERE id = ?", (bond_id,))
        today = date(2026, 10, 6)
        events = daily_sweep(conn, today)
        assert events == [
            {
                "bond_id": bond_id,
                "company": "SyncCo",
                "month": "2026-10",
                "credit_day": 5,
                "severity": "danger",
            }
        ]
        assert bond_status(conn, bond_id) == "Danger"
        counts = summary_counts(conn, today)
        assert counts["danger"] >= 1
        overview = status_overview(conn, today)
        overview_entry = next(row for row in overview if row["id"] == bond_id)
        assert overview_entry["status"] == "Danger"
        model = grid_model(conn, today)
        grid_row = next(row for row in model["rows"] if row["id"] == bond_id)
        assert grid_row["status"] == "Danger"
        assert counts["danger"] == sum(1 for row in overview if row["status"] == "Danger")


def test_tc78_watch_candidate_does_not_abort_sweep(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, watch_state) "
            "VALUES (?, ?, ?, 'watching')",
            ("Candidate Co", "INE0000000115", "Candidate Co"),
        )
        bond_id = add_bond(conn, "Alpha", "INE0000000078", "2026-09-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        conn.execute("UPDATE bonds SET status = 'On-going' WHERE id = ?", (bond_id,))
        events = daily_sweep(conn, date(2026, 10, 6))
        assert events == [
            {
                "bond_id": bond_id,
                "company": "Alpha",
                "month": "2026-10",
                "credit_day": 5,
                "severity": "danger",
            }
        ]
        assert bond_status(conn, bond_id) == "Danger"
        candidate = conn.execute(
            "SELECT watch_state, credit_day, status FROM bonds WHERE isin = ?",
            ("INE0000000115",),
        ).fetchone()
        assert candidate["watch_state"] == "watching"
        assert candidate["credit_day"] is None
        assert candidate["status"] == "On-going"


def test_tc78_watch_candidate_does_not_abort_startup_alerts(db_path, monkeypatch):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 6)))
    for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_TO"):
        monkeypatch.delenv(name, raising=False)
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, end_date, watch_state) "
            "VALUES (?, ?, ?, ?, 'watching')",
            ("Candidate Co", "INE0000000116", "Candidate Co", "2026-11-05"),
        )
        bond_id = add_bond(conn, "Alpha", "INE0000000078", "2026-09-01", 12, credit_day=5)
        save_payment(conn, bond_id, "2026-09", 1000.0, 1)
        conn.execute("UPDATE bonds SET status = 'On-going' WHERE id = ?", (bond_id,))
    create_app(str(db_path))
    with get_conn(db_path) as conn:
        messages = [
            dict(row)
            for row in conn.execute("SELECT severity, message FROM notifications").fetchall()
        ]
        assert bond_status(conn, bond_id) == "Danger"
    assert not any("daily sweep failed" in row["message"] for row in messages)
    assert not any("due reminder failed" in row["message"] for row in messages)
    assert not any("Candidate Co" in row["message"] for row in messages)
    assert any(row["severity"] == "danger" and "Alpha" in row["message"] for row in messages)
