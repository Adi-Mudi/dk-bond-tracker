from datetime import datetime, timezone

from flask import Blueprint, redirect, request, session, url_for, flash

from .. import gmail_oauth
from ..db import get_conn
from ..prefs import get_pref, set_pref
from ..validators import AppError
from .common import app_db

bp = Blueprint("gmail_auth", __name__)

TOKEN_KEYS = (
    "gmail_access_token",
    "gmail_refresh_token",
    "gmail_token_expiry",
    "gmail_user",
)


@bp.route("/gmail/connect")
def gmail_connect():
    db_file = app_db()
    with get_conn(db_file) as conn:
        client_id = get_pref(conn, "gmail_client_id", "") or ""
        client_secret = get_pref(conn, "gmail_client_secret", "") or ""
    client_id = str(client_id).strip()
    client_secret = str(client_secret).strip()
    if not client_id or not client_secret:
        flash("Enter your OAuth Client ID and Secret first (Settings > General > Email).", "error")
        return redirect(url_for("settings.settings_page", section="general") + "#email-card")
    state = gmail_oauth.new_state()
    verifier, challenge = gmail_oauth.pkce_pair()
    session["gmail_state"] = state
    session["gmail_verifier"] = verifier
    return redirect(gmail_oauth.authorize_url(client_id, state, challenge))


@bp.route("/auth/google/callback")
def gmail_callback():
    db_file = app_db()
    error = request.args.get("error")
    if error:
        flash("Gmail connection cancelled: " + str(error)[:120], "error")
        return redirect(url_for("settings.settings_page", section="general") + "#email-card")
    code = request.args.get("code", "")
    state = request.args.get("state", "")
    expected = session.pop("gmail_state", "")
    verifier = session.pop("gmail_verifier", "")
    if not code or not state or state != expected or not verifier:
        flash("Gmail connection failed: state mismatch — please try again.", "error")
        return redirect(url_for("settings.settings_page", section="general") + "#email-card")
    with get_conn(db_file) as conn:
        client_id = str(get_pref(conn, "gmail_client_id", "") or "").strip()
        client_secret = str(get_pref(conn, "gmail_client_secret", "") or "").strip()
    try:
        tokens = gmail_oauth.exchange_code(client_id, client_secret, code, verifier)
    except AppError as exc:
        flash("Gmail connection failed: " + str(exc.message)[:160], "error")
        return redirect(url_for("settings.settings_page", section="general") + "#email-card")
    with get_conn(db_file) as conn:
        set_pref(conn, "gmail_access_token", tokens["access_token"])
        set_pref(conn, "gmail_refresh_token", tokens["refresh_token"])
        set_pref(conn, "gmail_token_expiry", tokens["expiry"])
        set_pref(conn, "gmail_user", tokens["email"])
    flash("Connected to Gmail" + (" as " + tokens["email"] if tokens["email"] else "") + ".", "success")
    return redirect(url_for("settings.settings_page", section="general") + "#email-card")


@bp.route("/gmail/disconnect", methods=["POST"])
def gmail_disconnect():
    db_file = app_db()
    with get_conn(db_file) as conn:
        for key in TOKEN_KEYS:
            set_pref(conn, key, "")
    flash("Gmail disconnected — tokens cleared from this device.", "success")
    return redirect(url_for("settings.settings_page", section="general") + "#email-card")
