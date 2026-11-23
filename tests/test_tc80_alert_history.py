import re
from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn
from src.notifications import list_notifications, mark_all_read, notify, unread_count

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN_TOKENS = ("requests", "httpx", "push", "sms", "whatsapp")


def source_files():
    files = sorted(SRC.rglob("*.py")) + sorted(SRC.rglob("*.html"))
    return [p for p in files if (SRC / "design") not in p.parents]


def seed_history(db_path):
    with get_conn(db_path) as conn:
        notify(conn, "danger", "Beta Finance Ltd credit day 5 missed — Danger set (2026-10-06)")
        notify(conn, "reminder", "Alpha Securities Ltd payment due in 2 days")
        notify(conn, "warn", "email failed: boom")


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc80_history_rows_persist_with_timestamps(client, db_path):
    seed_history(db_path)
    html = client.get("/notifications").get_data(as_text=True)
    assert "Beta Finance Ltd credit day 5 missed" in html
    assert "Alpha Securities Ltd payment due in 2 days" in html
    assert "email failed: boom" in html
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", html)
    assert "danger" in html
    assert "reminder" in html
    assert "warn" in html
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"] == 3


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc80_history_survives_repeated_reads(client, db_path):
    seed_history(db_path)
    first = client.get("/notifications").get_data(as_text=True)
    second = client.get("/notifications").get_data(as_text=True)
    assert first == second
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"] == 3


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc80_mark_all_read_keeps_rows_and_clears_badge(client, db_path):
    seed_history(db_path)
    assert re.search(r'id="unreadCount"[^>]*>3<', client.get("/").get_data(as_text=True))
    response = client.post("/notifications/read_all")
    assert response.status_code == 302
    assert response.headers["Location"] == "/notifications"
    assert re.search(r'id="unreadCount"[^>]*>0<', client.get("/").get_data(as_text=True))
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"] == 3
        assert unread_count(conn) == 0
        rows = list_notifications(conn)
    assert len(rows) == 3
    assert all(int(row["read"]) == 1 for row in rows)
    html = client.get("/notifications").get_data(as_text=True)
    assert "Beta Finance Ltd credit day 5 missed" in html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc80_severity_colors_render_in_bell_dropdown(client, db_path):
    seed_history(db_path)
    html = client.get("/").get_data(as_text=True)
    assert "sev-danger" in html
    assert "sev-reminder" in html
    assert "sev-warn" in html
    assert "See all alerts" in html


def test_tc80_no_network_or_push_channels_in_source():
    offenders = []
    for path in source_files():
        text = path.read_text(encoding="utf-8").lower()
        text = text.replace("history.pushstate", "")
        for token in FORBIDDEN_TOKENS:
            if token in text:
                offenders.append(f"{path.relative_to(SRC)}: {token}")
    assert offenders == []


def test_tc80_notifications_are_never_cleared_by_app_code():
    app_sources = [path.read_text(encoding="utf-8").lower() for path in source_files()]
    for text in app_sources:
        assert "delete from notifications" not in text
        assert "drop table notifications" not in text


def test_tc80_mark_all_read_helper_reports_row_count(db_path):
    with get_conn(db_path) as conn:
        notify(conn, "info", "first alert")
        notify(conn, "info", "second alert")
        assert unread_count(conn) == 2
        changed = mark_all_read(conn)
        assert changed == 2
        assert unread_count(conn) == 0
        assert len(list_notifications(conn)) == 2
