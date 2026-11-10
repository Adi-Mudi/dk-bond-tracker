import io
import json
import urllib.error
from datetime import datetime, timedelta, timezone

import pytest

from src import gmail_oauth
from src.app import create_app
from src.db import get_conn, init_db
from src.mailer import send_message, _gmail_ready
from src.prefs import get_pref, set_pref
from src.validators import AppError


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return super().read()


def _fake_urlopen_factory(payload, capture):
    def fake(request, timeout=None):
        capture.append(request)
        if isinstance(payload, Exception):
            raise payload
        return FakeResponse(json.dumps(payload).encode("utf-8"))

    return fake


def test_authorize_url_contains_required_params():
    url = gmail_oauth.authorize_url("cid.apps.googleusercontent.com", "st4te", "chal1enge")
    assert "client_id=cid.apps.googleusercontent.com" in url
    assert "state=st4te" in url
    assert "code_challenge=chal1enge" in url
    assert "code_challenge_method=S256" in url
    assert "access_type=offline" in url
    assert "prompt=consent" in url
    assert "response_type=code" in url
    assert "gmail.send" in url


def test_pkce_and_state_unique():
    v1, c1 = gmail_oauth.pkce_pair()
    v2, c2 = gmail_oauth.pkce_pair()
    assert v1 != v2 and c1 != c2
    assert gmail_oauth.new_state() != gmail_oauth.new_state()


def test_exchange_code_parses_tokens(monkeypatch):
    capture = []
    payload = {
        "access_token": "at-1",
        "refresh_token": "rt-1",
        "expires_in": 3600,
        "id_token": "h." + __import__("base64").urlsafe_b64encode(
            json.dumps({"email": "divakaran060@gmail.com"}).encode()
        ).decode().rstrip("=") + ".sig",
    }
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_factory(payload, capture))
    tokens = gmail_oauth.exchange_code("cid", "sec", "code123", "verifier")
    assert tokens["access_token"] == "at-1"
    assert tokens["refresh_token"] == "rt-1"
    assert tokens["email"] == "divakaran060@gmail.com"
    body = capture[0].data.decode()
    assert "grant_type=authorization_code" in body
    assert "code_verifier=verifier" in body


def test_refresh_keeps_refresh_token(monkeypatch):
    capture = []
    payload = {"access_token": "at-2", "expires_in": 1800}
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_factory(payload, capture))
    tokens = gmail_oauth.refresh_access_token("cid", "sec", "rt-keep")
    assert tokens["access_token"] == "at-2"
    assert tokens["refresh_token"] == "rt-keep"


def test_http_error_raises_app_error(monkeypatch):
    def boom(request, timeout=None):
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, io.BytesIO(b'{"error":"invalid_grant"}'))

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(AppError) as exc:
        gmail_oauth.exchange_code("cid", "sec", "bad", "v")
    assert exc.value.code == "ERR-gmail-oauth"


def test_token_expired_math():
    past = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    assert gmail_oauth.token_expired(past) is True
    assert gmail_oauth.token_expired(future) is False
    assert gmail_oauth.token_expired("") is True


def test_send_raw_posts_json_with_bearer(monkeypatch):
    capture = []
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen_factory({"id": "msg1"}, capture))
    gmail_oauth.send_raw("access-token", b"From: a\r\n\r\nhello")
    req = capture[0]
    assert req.full_url.endswith("users/me/messages/send")
    assert req.get_header("Authorization") == "Bearer access-token"
    body = json.loads(req.data.decode())
    assert "raw" in body


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "bonds.db"
    init_db(path)
    return path


def test_gmail_ready_and_send_routes_to_api(db_path, monkeypatch):
    with get_conn(db_path) as conn:
        set_pref(conn, "gmail_refresh_token", "rt")
        set_pref(conn, "gmail_client_id", "cid")
        set_pref(conn, "gmail_client_secret", "sec")
        set_pref(conn, "gmail_access_token", "at")
        set_pref(conn, "gmail_token_expiry", (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())

    with get_conn(db_path) as conn2:
        assert _gmail_ready(conn2) is True
        calls = {}

        def fake_send_raw(access, mime_bytes):
            calls["access"] = access
            calls["mime"] = mime_bytes
            return {"id": "x"}

        monkeypatch.setattr(gmail_oauth, "send_raw", fake_send_raw)
        result = send_message("Hello", "body text", None, conn=conn2)

    assert calls.get("access") == "at"
    assert b"body text" in calls["mime"]
    assert result["via"] == "gmail-api"


def test_not_connected_falls_back_to_smtp_error(db_path, monkeypatch):
    for key in ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_TO"):
        monkeypatch.delenv(key, raising=False)
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc:
            send_message("Hello", "body", None, conn=conn)
    assert exc.value.code == "ERR-smtp-unconfigured"


def test_settings_saves_client_and_blank_secret_keeps(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    payload = {"gmail_client_id": "cid.apps.googleusercontent.com"}
    payload["gmail_client_secret"] = "GOCSPX-fake-secret-123"
    client.post("/settings", data=payload, follow_redirects=True)
    with get_conn(db_path) as conn:
        assert get_pref(conn, "gmail_client_id") == "cid.apps.googleusercontent.com"
        assert get_pref(conn, "gmail_client_secret") == "GOCSPX-fake-secret-123"
    payload2 = {"gmail_client_id": "cid.apps.googleusercontent.com", "gmail_client_secret": ""}
    client.post("/settings", data=payload2, follow_redirects=True)
    with get_conn(db_path) as conn:
        assert get_pref(conn, "gmail_client_secret") == "GOCSPX-fake-secret-123", "blank must keep secret"


def test_settings_page_never_renders_secret(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    payload = {"gmail_client_id": "cid", "gmail_client_secret": "GOCSPX-fake-secret-123"}
    client.post("/settings", data=payload, follow_redirects=True)
    html = client.get("/settings").get_data(as_text=True)
    assert "GOCSPX-fake-secret-123" not in html
    assert 'name="gmail_client_secret"' in html
    assert "Connect Gmail" in html


def test_callback_rejects_state_mismatch(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.get("/auth/google/callback?code=abc&state=WRONG", follow_redirects=True)
    assert resp.status_code == 200
    with get_conn(db_path) as conn:
        assert (get_pref(conn, "gmail_refresh_token", "") or "") == ""


def test_disconnect_clears_tokens(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    with get_conn(db_path) as conn:
        set_pref(conn, "gmail_refresh_token", "rt")
        set_pref(conn, "gmail_access_token", "at")
        set_pref(conn, "gmail_token_expiry", "2099-01-01T00:00:00+00:00")
        set_pref(conn, "gmail_user", "divakaran060@gmail.com")
    resp = client.post("/gmail/disconnect", follow_redirects=True)
    assert resp.status_code == 200
    with get_conn(db_path) as conn:
        assert (get_pref(conn, "gmail_refresh_token", "") or "") == ""
        assert (get_pref(conn, "gmail_access_token", "") or "") == ""


def test_connect_requires_client_id(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    resp = client.get("/gmail/connect", follow_redirects=True)
    assert resp.status_code == 200
    with get_conn(db_path) as conn:
        assert (get_pref(conn, "gmail_refresh_token", "") or "") == ""


def test_alert_send_works_with_only_gmail_prefs(db_path, monkeypatch):
    for key in ("SMTP_USER", "SMTP_APP_PASSWORD", "ALERT_TO", "SMTP_HOST", "SMTP_PORT"):
        monkeypatch.delenv(key, raising=False)
    with get_conn(db_path) as conn:
        set_pref(conn, "gmail_refresh_token", "rt")
        set_pref(conn, "gmail_client_id", "cid")
        set_pref(conn, "gmail_client_secret", "sec")
        set_pref(conn, "gmail_access_token", "at-live")
        set_pref(conn, "gmail_token_expiry", (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat())
        set_pref(conn, "gmail_user", "divakaran060@gmail.com")
    with get_conn(db_path) as conn2:
        calls = {}

        def fake_send_raw(access, mime_bytes):
            calls["access"] = access
            calls["mime"] = mime_bytes
            return {"id": "alert1"}

        monkeypatch.setattr(gmail_oauth, "send_raw", fake_send_raw)
        from src.mailer import send_alert_email

        result = send_alert_email({"company": "Acme", "month": "2026-11", "severity": "due", "credit_day": 5}, conn=conn2)

    assert result["via"] == "gmail-api"
    assert calls["access"] == "at-live"
    assert b"Acme" in calls["mime"]
