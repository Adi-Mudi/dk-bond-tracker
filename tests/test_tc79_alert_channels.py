import re
import smtplib
from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn


def make_sim_date(frozen):
    class SimDate(date):
        @classmethod
        def today(cls):
            return frozen

    return SimDate


@pytest.fixture
def mail_log():
    return []


@pytest.fixture
def fake_smtp(monkeypatch, mail_log):
    class FakeSMTP:
        def __init__(self, host, port):
            mail_log.append(("connect", host, port))

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def login(self, user, password):
            mail_log.append(("login", user, password))

        def sendmail(self, sender, recipients, body):
            mail_log.append(("sendmail", sender, recipients, body))

    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
    return FakeSMTP


def notifications_rows(db_path):
    with get_conn(db_path) as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id, created_at, severity, message, read FROM notifications "
                "ORDER BY id"
            ).fetchall()
        ]


def test_tc79_sweep_flip_creates_notification_and_sends_email(
    db_path, monkeypatch, fake_smtp, mail_log
):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 30)))
    monkeypatch.setenv("SMTP_HOST", "smtp.example.test")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "owner@example.test")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-password-abc-123")
    monkeypatch.delenv("ALERT_TO", raising=False)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "FlipCo", "INE0000000791", "2026-09-01", 12, credit_day=1)
        add_payment(conn, bond_id, "2026-09", 1000.0)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    rows = notifications_rows(db_path)
    danger_rows = [row for row in rows if row["severity"] == "danger"]
    assert len(danger_rows) == 1
    assert "FlipCo" in danger_rows[0]["message"]
    assert "Danger set" in danger_rows[0]["message"]
    assert danger_rows[0]["created_at"]
    assert danger_rows[0]["read"] == 0
    assert ("connect", "smtp.example.test", 465) in mail_log
    assert ("login", "owner@example.test", "app-password-abc-123") in mail_log
    send_entries = [entry for entry in mail_log if entry[0] == "sendmail"]
    assert len(send_entries) == 1
    sender, recipients, body = send_entries[0][1], send_entries[0][2], send_entries[0][3]
    assert sender == "owner@example.test"
    assert recipients == ["owner@example.test"]
    assert "FlipCo" in body
    assert "2026-10" in body
    page = app.test_client().get("/notifications").get_data(as_text=True)
    assert "FlipCo" in page
    assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", page)


def test_tc79_unconfigured_smtp_keeps_app_alive_with_warn_notification(
    db_path, monkeypatch
):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 30)))
    for name in ("SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_TO"):
        monkeypatch.delenv(name, raising=False)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "QuietCo", "INE0000000792", "2026-09-01", 12, credit_day=1)
        add_payment(conn, bond_id, "2026-09", 1000.0)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    rows = notifications_rows(db_path)
    assert any(row["severity"] == "danger" and "QuietCo" in row["message"] for row in rows)
    warn_rows = [row for row in rows if row["severity"] == "warn"]
    assert len(warn_rows) == 1
    assert warn_rows[0]["message"].startswith("email failed:")
    assert "ERR-smtp-unconfigured" in warn_rows[0]["message"]
    response = app.test_client().get("/")
    assert response.status_code == 200


def test_tc79_due_reminder_fires_both_channels_once(
    db_path, monkeypatch, fake_smtp, mail_log
):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 3)))
    monkeypatch.setenv("SMTP_USER", "owner@example.test")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-password-abc-123")
    with get_conn(db_path) as conn:
        add_bond(conn, "DueCo", "INE0000000793", "2026-09-01", 12, credit_day=5)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    rows = notifications_rows(db_path)
    reminders = [row for row in rows if row["severity"] == "reminder"]
    assert len(reminders) == 1
    assert "DueCo payment due in 2 days" in reminders[0]["message"]
    assert reminders[0]["created_at"]
    assert any(entry[0] == "sendmail" for entry in mail_log)
    mail_log.clear()
    create_app(str(db_path))
    rows_after = notifications_rows(db_path)
    reminders_after = [row for row in rows_after if row["severity"] == "reminder"]
    assert len(reminders_after) == 1
    assert not any(entry[0] == "sendmail" for entry in mail_log)


def test_tc79_alert_lands_in_bell_and_history(db_path, monkeypatch, fake_smtp, mail_log):
    monkeypatch.setattr("src.app.date", make_sim_date(date(2026, 10, 30)))
    monkeypatch.setenv("SMTP_USER", "owner@example.test")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "app-password-abc-123")
    with get_conn(db_path) as conn:
        add_bond(conn, "BellCo", "INE0000000794", "2026-09-01", 12, credit_day=1)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    dashboard = app.test_client().get("/").get_data(as_text=True)
    assert 'id="unreadCount">1<' in dashboard
    assert "BellCo" in dashboard
    assert "sev-danger" in dashboard
    history = app.test_client().get("/notifications").get_data(as_text=True)
    assert "BellCo" in history
    assert "danger" in history
