import sys

from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from src.db import get_conn
from src.mailer import send_alert_email
from src.prefs import set_pref
from src.validators import AppError
from src.views.common import (
    APP_VERSION,
    BUILD_NOTES,
    EMAIL_TEST_FAILURE_MESSAGE,
    EMAIL_TEST_SUCCESS_MESSAGE,
    app_db,
)
from src.views.notifications import alert_prefs_map

bp = Blueprint("settings", __name__)


def settings_from_form(form):
    host = str(form.get("smtp_host", "")).strip()
    port_raw = str(form.get("smtp_port", "")).strip()
    security = str(form.get("smtp_security", "")).strip()
    sender = str(form.get("smtp_from", "")).strip()
    recipient = str(form.get("smtp_to", "")).strip()
    if security not in ("", "TLS", "STARTTLS", "SSL", "None"):
        raise AppError(
            "ERR-settings-save",
            f"unknown SMTP security: {security!r} (expected TLS, STARTTLS, SSL or None)",
        )
    port_value = ""
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise AppError(
                "ERR-settings-save", f"SMTP port must be an integer: {port_raw!r}"
            ) from exc
        if not 1 <= port <= 65535:
            raise AppError("ERR-settings-save", f"SMTP port out of range 1-65535: {port}")
        port_value = str(port)
    checked = ("on", "1", "true", "yes")
    return {
        "smtp_host": host,
        "smtp_port": port_value,
        "smtp_security": security,
        "smtp_from": sender,
        "smtp_recipient": recipient,
        "privacy_on_startup": "1" if form.get("privacy_on_startup") in checked else "0",
        "share_section_holdings": "1" if form.get("share_holdings") in checked else "0",
        "share_section_payouts": "1" if form.get("share_payouts") in checked else "0",
        "share_section_goals": "1" if form.get("share_goals") in checked else "0",
    }


@bp.route("/settings", methods=["GET", "POST"])
def settings_page():
    db_file = app_db()
    if request.method == "POST":
        try:
            values = settings_from_form(request.form)
        except AppError as exc:
            return (
                render_template(
                    "settings.html",
                    prefs=alert_prefs_map(db_file),
                    error=exc.message,
                    error_code=exc.code,
                    app_version=APP_VERSION,
                    build_notes=BUILD_NOTES,
                    data_dir=str(db_file.parent),
                ),
                400,
            )
        with get_conn(db_file) as conn:
            for key, value in values.items():
                set_pref(conn, key, value)
        flash("Settings saved", "success")
        return redirect(url_for("settings.settings_page"))
    return render_template(
        "settings.html",
        prefs=alert_prefs_map(db_file),
        error=None,
        error_code=None,
        app_version=APP_VERSION,
        build_notes=BUILD_NOTES,
        data_dir=str(db_file.parent),
    )


@bp.route("/settings/email/test", methods=["POST"])
def settings_email_test():
    host = str(request.form.get("smtp_host", "")).strip()
    ok = bool(host)
    detail = ""
    if ok:
        try:
            send_alert_email(
                {
                    "company": "settings test",
                    "month": "manual test",
                    "severity": "test",
                    "credit_day": None,
                }
            )
        except AppError as exc:
            ok = False
            detail = exc.code
        except Exception as exc:
            ok = False
            detail = "ERR-email-send"
            print(f"email test send failed: {exc}", file=sys.stderr)
    status = "success" if ok else "failure"
    message = EMAIL_TEST_SUCCESS_MESSAGE if ok else EMAIL_TEST_FAILURE_MESSAGE
    try:
        db_file = app_db()
        with get_conn(db_file) as conn:
            set_pref(conn, "email_test_last_status", status)
            set_pref(conn, "email_test_last_at", date.today().isoformat())
    except Exception as exc:
        print(f"email test status persist failed: {exc}", file=sys.stderr)
    return jsonify({"status": status, "message": message, "detail": detail})
