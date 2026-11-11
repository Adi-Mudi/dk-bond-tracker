from pathlib import Path

import pytest

from src.app import _attempt_email, create_app
from src.db import get_conn
from src.notifications import notify
from src.validators import AppError

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "src" / "templates" / "notifications.html"


def test_every_severity_has_a_human_label():
    from src.views.notifications import SEVERITY_LABELS, SEVERITY_RANK

    assert set(SEVERITY_LABELS) == set(SEVERITY_RANK)
    for severity, label in SEVERITY_LABELS.items():
        assert "_" not in label, severity
        assert label == label.strip() and label, severity


def test_feed_renders_friendly_labels_not_machine_tokens(db_path):
    with get_conn(db_path) as conn:
        notify(conn, "due_today", "HDFC Bank — payout due today (credit day 12)")
        notify(conn, "maturity_soon", "Muthoot Finance — matures in 20 days")
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/notifications").get_data(as_text=True)
    assert "Due today" in html
    assert "Maturity soon" in html
    assert "DUE_TODAY" not in html
    assert "MATURITY_SOON" not in html


def test_template_never_prints_the_raw_severity_token():
    text = TEMPLATE.read_text(encoding="utf-8")
    assert "{{ row.severity_label }}" in text
    assert '<span class="alert-severity">{{ row.severity }}</span>' not in text


def test_email_failure_warning_is_user_friendly(db_path, monkeypatch):
    def boom(*args, **kwargs):
        raise AppError("ERR-smtp-unconfigured", "SMTP_APP_PASSWORD is not set")

    monkeypatch.setattr("src.app.send_alert_email", boom)
    with get_conn(db_path) as conn:
        _attempt_email(conn, {"company": "HDFC Bank", "credit_day": 12, "month": "2026-11"})
        row = conn.execute("SELECT message FROM notifications ORDER BY id DESC LIMIT 1").fetchone()
    message = row["message"]
    assert "Settings" in message
    assert "ERR-" not in message
    assert "SMTP_" not in message
