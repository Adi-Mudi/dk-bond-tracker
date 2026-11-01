import re
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.notifications import due_reminders, maturity_reminders, notify_once
from src.alerts import daily_sweep

FIXED_TODAY = date(2026, 3, 26)


def _seed_mixed_events(db_path):
    with get_conn(db_path) as conn:
        overdue_id = add_bond(
            conn, "OVERDUE CO", "INE9000A01001", "2026-03-01", 12, credit_day=24
        )
        due_today_id = add_bond(
            conn, "DUE TODAY CO", "INE9000A01002", "2026-03-01", 12, credit_day=26
        )
        reminder_id = add_bond(
            conn, "REMINDER CO", "INE9000A01003", "2026-03-01", 12, credit_day=28
        )
        maturity_id = add_bond(
            conn, "MATURE CO", "INE9000A01004", "2025-04-02", 12, credit_day=27
        )
        danger_events = daily_sweep(conn, FIXED_TODAY)
        reminder_events = due_reminders(conn, FIXED_TODAY)
        maturity_events = maturity_reminders(conn, FIXED_TODAY)
    return {
        "overdue": overdue_id,
        "due_today": due_today_id,
        "reminder": reminder_id,
        "maturity": maturity_id,
        "danger": danger_events,
        "reminders": reminder_events,
        "maturities": maturity_events,
    }


def _severities_in_order(html):
    return re.findall(r'data-severity="([a-z_]+)"', html)


def test_tc91_sweeps_emit_each_card_type(db_path):
    seeded = _seed_mixed_events(db_path)
    assert any(e["severity"] == "danger" for e in seeded["danger"])
    severities = {e["severity"] for e in seeded["reminders"]}
    assert "due_today" in severities
    assert "reminder" in severities
    assert any(e["severity"] == "maturity_soon" for e in seeded["maturities"])
    assert seeded["maturities"][0]["days_left"] == 7


def test_tc91_feed_renders_severity_ordered(db_path):
    _seed_mixed_events(db_path)
    app = create_app(str(db_path))
    html = app.test_client().get("/notifications").get_data(as_text=True)
    assert 'id="alert-feed"' in html
    severities = _severities_in_order(html)
    assert severities, "feed must render seeded cards"
    rank = {"danger": 0, "due_today": 1, "reminder": 2, "maturity_soon": 3}
    ranks = [rank[s] for s in severities if s in rank]
    assert ranks == sorted(ranks), f"severity order violated: {severities}"


def test_tc91_dedupe_keys_suppress_same_day_duplicates(db_path):
    with get_conn(db_path) as conn:
        key = f"danger:777:{FIXED_TODAY.isoformat()}"
        first = notify_once(conn, key, "danger", "first insert")
        second = notify_once(conn, key, "danger", "duplicate insert")
        assert first is not None
        assert second is None
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM notifications WHERE message = 'duplicate insert'"
        ).fetchone()
        assert int(row["n"]) == 0
        keys = conn.execute(
            "SELECT COUNT(*) AS n FROM alert_prefs WHERE key = ?", (key,)
        ).fetchone()
        assert int(keys["n"]) == 1


def test_tc91_startup_runs_maturity_scan_without_error(db_path):
    app = create_app(str(db_path))
    client = app.test_client()
    r = client.get("/notifications")
    assert r.status_code == 200
    assert 'id="alert-feed"' in r.get_data(as_text=True)


def test_tc91_completed_bonds_skipped_by_all_scans(db_path):
    with get_conn(db_path) as conn:
        add_bond(
            conn,
            "DONE CO",
            "INE9000A01009",
            "2025-04-03",
            12,
            credit_day=26,
            status="Completed",
        )
        assert daily_sweep(conn, FIXED_TODAY) == []
        assert due_reminders(conn, FIXED_TODAY) == []
        assert maturity_reminders(conn, FIXED_TODAY) == []
