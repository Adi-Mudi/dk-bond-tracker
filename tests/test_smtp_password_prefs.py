import smtplib

import pytest

from src.app import create_app
from src.db import get_conn, init_db
from src.mailer import _config, send_alert_email
from src.prefs import set_pref
from src.validators import AppError


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "bonds.db"
    init_db(path)
    return path


def _clear_smtp_env(monkeypatch):
    for key in ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_TO", "SMTP_HOST", "SMTP_PORT", "SMTP_STARTTLS"):
        monkeypatch.delenv(key, raising=False)


def test_env_password_wins_over_pref(db_path, monkeypatch):
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_USER", "env@example.test")
    monkeypatch.setenv("SMTP_APP_PASSWORD", "env-pass-123")
    with get_conn(db_path) as conn:
        set_pref(conn, "smtp_app_password", "pref-pass-456")
        host, port, user, pw, recipient = _config(conn)
    assert pw == "env-pass-123"
    assert user == "env@example.test"


def test_pref_password_used_when_env_absent(db_path, monkeypatch):
    _clear_smtp_env(monkeypatch)
    with get_conn(db_path) as conn:
        set_pref(conn, "smtp_from", "pref@example.test")
        set_pref(conn, "smtp_app_password", "pref-pass-456")
        set_pref(conn, "smtp_recipient", "user@example.com")
        set_pref(conn, "smtp_host", "smtp.gmail.com")
        set_pref(conn, "smtp_port", "465")
        host, port, user, pw, recipient = _config(conn)
    assert user == "pref@example.test"
    assert pw == "pref-pass-456"
    assert recipient == "user@example.com"
    assert host == "smtp.gmail.com"
    assert port == 465


def test_both_missing_raises(db_path, monkeypatch):
    _clear_smtp_env(monkeypatch)
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc:
            _config(conn)
    assert "SMTP" in exc.value.message


def test_settings_post_stores_password_and_blank_keeps_it(db_path, monkeypatch):
    _clear_smtp_env(monkeypatch)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()

    payload = {"smtp_host": "smtp.gmail.com", "smtp_from": "a@b.test", "smtp_to": "c@d.test"}
    payload["smtp_app_password"] = "secret-abc-123"
    r = client.post("/settings", data=payload, follow_redirects=True)
    assert r.status_code == 200
    with get_conn(db_path) as conn:
        from src.prefs import get_pref

        assert get_pref(conn, "smtp_app_password") == "secret-abc-123"

    r2 = client.post(
        "/settings",
        data={"smtp_host": "smtp.gmail.com", "smtp_from": "a@b.test", "smtp_to": "c@d.test", "smtp_app_password": ""},
        follow_redirects=True,
    )
    assert r2.status_code == 200
    with get_conn(db_path) as conn:
        from src.prefs import get_pref

        assert get_pref(conn, "smtp_app_password") == "secret-abc-123", "blank input must not wipe stored password"


def test_password_never_in_html(db_path, monkeypatch):
    _clear_smtp_env(monkeypatch)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    payload2 = {"smtp_from": "a@b.test"}
    payload2["smtp_app_password"] = "secret-abc-123"
    client.post("/settings", data=payload2, follow_redirects=True)
    html = client.get("/settings").get_data(as_text=True)
    assert "secret-abc-123" not in html, "password must never be rendered"
    assert 'name="smtp_app_password"' in html
    assert 'type="password"' in html


def test_send_uses_pref_and_can_be_mocked(db_path, monkeypatch):
    _clear_smtp_env(monkeypatch)
    with get_conn(db_path) as conn:
        set_pref(conn, "smtp_from", "pref@example.test")
        set_pref(conn, "smtp_app_password", "pref-pass-456")
        set_pref(conn, "smtp_host", "smtp.example.test")
        set_pref(conn, "smtp_port", "465")

        sent = {}

        class FakeSMTP:
            def __init__(self, host, port):
                sent["host"] = host
                sent["port"] = port

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def login(self, user, password):
                sent["user"] = user
                sent["pass"] = password

            def sendmail(self, frm, to, message):
                sent["to"] = to
                sent["msg"] = message

        monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)
        result = send_alert_email({"company": "Acme", "month": "2026-11", "severity": "due", "credit_day": 5}, conn=conn)

    assert result["status"] == "sent"
    assert sent["pass"] == "pref-pass-456"
    assert sent["user"] == "pref@example.test"
    assert sent["host"] == "smtp.example.test"
