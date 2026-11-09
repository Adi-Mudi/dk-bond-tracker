import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.notifications import notify
from src.prefs import get_pref

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "src" / "templates" / "notifications.html").read_text(encoding="utf-8")
BASE = (ROOT / "src" / "templates" / "base.html").read_text(encoding="utf-8")


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed(db_path, severity, message):
    with get_conn(db_path) as conn:
        notify(conn, severity, message)


def severities(html):
    return re.findall(r'data-severity="([a-z_]+)"', html)


def test_ui06_feed_has_no_config_forms(client, db_path):
    seed(db_path, "danger", "Alpha Ltd credit day 5 missed — Danger set (2026-10-06)")
    html = client.get("/notifications").get_data(as_text=True)
    for marker in (
        "alert-channels-form",
        'id="alert-channels"',
        'id="settings-alert-channels"',
        'name="alert_inapp"',
        'name="alert_email"',
        "day-wise-rule-text",
        "settings-day-wise-rule-text",
        "save-channels",
    ):
        assert marker not in html, marker
    assert 'id="alerts-config-pointer"' in html


def test_ui06_config_lives_under_settings(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    assert 'id="section-notifications"' in html
    assert 'id="settings-alert-channels"' in html
    assert 'name="alert_inapp"' in html
    assert 'name="alert_email"' in html
    assert 'id="settings-day-wise-rule-text"' in html
    assert "Day-wise rules" in html
    response = client.post(
        "/settings",
        data={"smtp_security": "", "smtp_port": "", "alert_inapp": "on"},
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        assert get_pref(conn, "alert_channel_inapp") == "1"
        assert get_pref(conn, "alert_channel_email") == "0"


def test_ui06_filter_chips_render_and_narrow(client, db_path):
    seed(db_path, "danger", "Alpha Ltd credit day 5 missed — Danger set (2026-10-06)")
    seed(db_path, "due_today", "Beta Ltd payment due today (day 5)")
    seed(db_path, "maturity_soon", "Gamma Ltd matures in 7 day(s) (16 Nov 2026)")
    html = client.get("/notifications").get_data(as_text=True)
    for key in ("all", "due", "overdue", "maturity"):
        assert f'id="feed-filter-{key}"' in html
    assert "All (3)" in html

    overdue = client.get("/notifications?filter=overdue").get_data(as_text=True)
    assert severities(overdue) == ["danger"]
    assert 'class="filter-chip-feed active" id="feed-filter-overdue"' in overdue

    due = client.get("/notifications?filter=due").get_data(as_text=True)
    assert severities(due) == ["due_today"]

    maturity = client.get("/notifications?filter=maturity").get_data(as_text=True)
    assert severities(maturity) == ["maturity_soon"]


def test_ui06_date_groups_render_today_week_older(client, db_path):
    seed(db_path, "danger", "FreshCo credit day 5 missed")
    html = client.get("/notifications").get_data(as_text=True)
    assert 'data-group="Today"' in html
    assert 'class="feed-group-title">Today<' in html

    week_stamp = (date.today() - timedelta(days=3)).isoformat() + " 09:00:00"
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO notifications (created_at, severity, message, read) "
            "VALUES (?, 'info', 'week alert', 0)",
            (week_stamp,),
        )
        conn.execute(
            "UPDATE notifications SET created_at = '2020-01-05 09:00:00' WHERE severity = 'danger'"
        )
    html = client.get("/notifications").get_data(as_text=True)
    assert 'data-group="This week"' in html
    assert 'data-group="Older"' in html


def test_ui06_same_type_bursts_batched_into_one_line(client, db_path):
    for index in range(3):
        seed(db_path, "reminder", f"Burst {index} Ltd payment due in 2 days (credit day 5)")
    seed(db_path, "danger", "Lone Ltd credit day 5 missed — Danger set (2026-10-06)")
    html = client.get("/notifications").get_data(as_text=True)
    assert "3 payouts due" in html
    assert html.count('data-severity="reminder"') == 1
    assert 'id="alert-batch-today-reminder"' in html
    assert "Burst 0 Ltd" in html
    assert html.count('data-severity="danger"') == 1
    assert 'id="alert-batch-today-danger"' not in html


def test_ui06_unread_is_bold_with_semantic_left_bar(client, db_path):
    seed(db_path, "danger", "Alpha Ltd credit day 5 missed — Danger set (2026-10-06)")
    html = client.get("/notifications").get_data(as_text=True)
    assert 'class="alert-card alert-danger unread"' in html
    assert ".alert-card.unread .alert-message { font-weight: 700; }" in TEMPLATE
    assert ".alert-card.alert-danger, .alert-card.alert-due_today { border-left-color: var(--c-red); }" in TEMPLATE
    assert ".alert-card.alert-reminder, .alert-card.alert-warn { border-left-color: var(--c-amber); }" in TEMPLATE
    assert ".alert-card.alert-maturity_soon { border-left-color: var(--c-blue); }" in TEMPLATE
    response = client.post("/notifications/read_all")
    assert response.status_code == 302
    html = client.get("/notifications").get_data(as_text=True)
    assert 'class="alert-card alert-danger unread"' not in html
    assert 'class="alert-card alert-danger"' in html


def test_ui06_mark_all_read_clears_the_badge(client, db_path):
    seed(db_path, "danger", "Alpha Ltd credit day 5 missed")
    seed(db_path, "warn", "email failed: boom")
    assert 'id="unreadCount">2<' in client.get("/").get_data(as_text=True)
    html = client.get("/notifications").get_data(as_text=True)
    assert 'id="mark-all-read"' in html
    response = client.post("/notifications/read_all")
    assert response.status_code == 302
    assert response.headers["Location"] == "/notifications"
    assert 'id="unreadCount">0<' in client.get("/").get_data(as_text=True)


def test_ui06_clear_hides_read_alerts_without_deleting(client, db_path):
    seed(db_path, "danger", "Alpha Ltd credit day 5 missed")
    seed(db_path, "warn", "email failed: boom")
    html = client.get("/notifications").get_data(as_text=True)
    assert 'id="clear-read"' in html
    client.post("/notifications/read_all")
    response = client.post("/notifications/clear")
    assert response.status_code == 302
    assert response.headers["Location"] == "/notifications"
    html = client.get("/notifications").get_data(as_text=True)
    assert 'id="alert-feed-empty"' in html
    assert "All caught up" in html
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM notifications").fetchone()["n"] == 2


def test_ui06_designed_empty_state_never_blank(client, db_path):
    html = client.get("/notifications").get_data(as_text=True)
    assert 'id="alert-feed"' in html
    assert 'id="alert-feed-empty"' in html
    assert "All caught up" in html
    assert 'class="feed-empty-icon"' in html
    assert "No alerts need your attention" in html


def test_ui06_rows_link_to_the_bond_and_to_the_fallback(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "LinkCo", "INE6000A1001", "2026-01-01", 12)
    seed(db_path, "danger", "LinkCo credit day 5 missed — Danger set (2026-10-06)")
    seed(db_path, "warn", "email failed: boom")
    html = client.get("/notifications").get_data(as_text=True)
    assert f'href="/portfolio/{bond_id}"' in html
    assert 'href="/portfolio?tab=holdings"' in html


def test_ui06_bell_previews_latest_five_and_open_all(client, db_path):
    for index in range(6):
        seed(db_path, "info", f"Bell item {index}")
    dashboard = client.get("/").get_data(as_text=True)
    assert dashboard.count('class="alert-item-v3 sev-') == 5
    assert 'id="open-all-alerts"' in dashboard
    assert 'id="unreadCount">6<' in dashboard
    assert "Alert history" in dashboard
    assert "open all" in BASE.lower()
    feed = client.get("/notifications").get_data(as_text=True)
    assert feed.count('class="alert-card alert-') == 6
