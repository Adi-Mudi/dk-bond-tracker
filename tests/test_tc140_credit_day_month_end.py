import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import add_bond
from src.alerts import daily_sweep
from src.db import get_conn
from src.notifications import due_reminders
from src.validators import validate_credit_day


def test_tc140_validate_credit_day_accepts_month_end_days():
    for day in (29, 30, 31):
        assert validate_credit_day(day) == day


def test_tc140_due_reminders_fire_for_credit_day_31(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "MONTHEND CO", "INE9000A14001", "2026-03-01", 12, credit_day=31)
        events = due_reminders(conn, date(2026, 3, 31))
    assert any(
        e["bond_id"] and e["severity"] == "due_today" and e["credit_day"] == 31
        for e in events
    )


def test_tc140_due_reminders_fire_lead_time_for_credit_day_30(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "LEADTIME CO", "INE9000A14002", "2026-03-01", 12, credit_day=30)
        events = due_reminders(conn, date(2026, 3, 28))
    assert any(
        e["severity"] == "reminder" and e["credit_day"] == 30 for e in events
    )


def test_tc140_daily_sweep_accepts_credit_day_29(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "SWEEP CO", "INE9000A14003", "2026-02-01", 2, credit_day=29)
        events = daily_sweep(conn, date(2026, 3, 30))
    assert any(e["credit_day"] == 29 for e in events)


def test_tc141_due_reminders_clamp_credit_day_31_to_april_30(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "APRIL CO", "INE9000A14101", "2026-03-01", 12, credit_day=31)
        events = due_reminders(conn, date(2026, 4, 30))
    assert any(
        e["severity"] == "due_today" and e["credit_day"] == 31 for e in events
    )


def test_tc141_lead_time_clamps_to_month_end(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "APRIL LEAD CO", "INE9000A14103", "2026-03-01", 12, credit_day=31)
        events = due_reminders(conn, date(2026, 4, 28))
    assert any(
        e["severity"] == "reminder" and e["credit_day"] == 31 for e in events
    )


def test_tc141_due_reminders_clamp_credit_day_30_to_february_28(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "FEB CO", "INE9000A14102", "2026-01-01", 12, credit_day=30)
        events = due_reminders(conn, date(2026, 2, 28))
    assert any(
        e["severity"] == "due_today" and e["credit_day"] == 30 for e in events
    )
