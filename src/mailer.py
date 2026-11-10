import os
import smtplib

from email.message import EmailMessage

from .prefs import set_pref
from .validators import AppError

DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465


def _pref(conn, key):
    if conn is None:
        return None
    from .prefs import get_pref

    value = get_pref(conn, key, None)
    return str(value).strip() if value not in (None, "") else None


def _config(conn=None):
    host = os.environ.get("SMTP_HOST") or _pref(conn, "smtp_host") or DEFAULT_SMTP_HOST
    port_raw = os.environ.get("SMTP_PORT") or _pref(conn, "smtp_port")
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise AppError("ERR-smtp-unconfigured", f"SMTP_PORT must be an integer: {port_raw!r}") from exc
    else:
        port = DEFAULT_SMTP_PORT
    user = os.environ.get("SMTP_USER") or _pref(conn, "smtp_from")
    if not user:
        raise AppError("ERR-smtp-unconfigured", "SMTP_USER is not set")
    app_password = os.environ.get("SMTP_APP_PASSWORD") or _pref(conn, "smtp_app_password")
    if not app_password:
        raise AppError("ERR-smtp-unconfigured", "SMTP_APP_PASSWORD is not set")
    recipient = os.environ.get("ALERT_TO") or _pref(conn, "smtp_recipient") or user
    return host, port, user, app_password, recipient


def _use_starttls(port, conn=None):
    if port == 465:
        return False
    if os.environ.get("SMTP_STARTTLS") == "1":
        return True
    if _pref(conn, "smtp_security") == "STARTTLS":
        return True
    return port == 587


def _gmail_ready(conn):
    return bool(conn is not None and _pref(conn, "gmail_refresh_token"))


def _gmail_send(msg, conn):
    from . import gmail_oauth

    client_id = _pref(conn, "gmail_client_id") or ""
    client_secret = _pref(conn, "gmail_client_secret") or ""
    refresh_token = _pref(conn, "gmail_refresh_token") or ""
    access = _pref(conn, "gmail_access_token") or ""
    expiry = _pref(conn, "gmail_token_expiry") or ""
    if gmail_oauth.token_expired(expiry):
        tokens = gmail_oauth.refresh_access_token(client_id, client_secret, refresh_token)
        access = tokens["access_token"]
        set_pref(conn, "gmail_access_token", access)
        set_pref(conn, "gmail_token_expiry", tokens["expiry"])
        if tokens.get("email"):
            set_pref(conn, "gmail_user", tokens["email"])
    gmail_oauth.send_raw(access, msg.as_bytes())
    return {"status": "sent", "via": "gmail-api", "to": msg["To"], "subject": msg["Subject"]}


def send_alert_email(event, conn=None):
    if not isinstance(event, dict):
        raise AppError("ERR-email-send", f"alert event must be a dict: {event!r}")
    host, port, user, app_password, recipient = _config(conn)
    company = str(event.get("company") or "")
    month = str(event.get("month") or "")
    severity = str(event.get("severity") or "alert")
    credit_day = event.get("credit_day")
    subject = f"{severity}: {company} payment {month}"
    body = (
        f"Company: {company}\n"
        f"Month: {month}\n"
        f"Credit day: {credit_day}\n"
        f"Alert: {severity}\n"
        f"Source: DK Bond Tracker local alert sweep\n"
    )
    if _gmail_ready(conn):
        msg = EmailMessage()
        msg["From"] = user or (_pref(conn, "smtp_from") or "me")
        msg["To"] = recipient or (_pref(conn, "smtp_recipient") or msg["From"])
        msg["Subject"] = subject
        msg.set_content(body)
        return _gmail_send(msg, conn)
    message = f"From: {user}\r\nTo: {recipient}\r\nSubject: {subject}\r\n\r\n{body}"
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as client:
                client.login(user, app_password)
                client.sendmail(user, [recipient], message)
        else:
            with smtplib.SMTP(host, port) as client:
                if _use_starttls(port, conn):
                    client.starttls()
                client.login(user, app_password)
                client.sendmail(user, [recipient], message)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-email-send", f"email send failed for {company} {month}: {exc}") from exc
    return {"status": "sent", "to": recipient, "subject": subject}


def send_message(subject, body, attachment=None, conn=None):
    host, port, user, app_password, recipient = _config(conn) if not _gmail_ready(conn) else (None, None, None, None, None)
    message = EmailMessage()
    message["From"] = user or (_pref(conn, "smtp_from") or "me")
    message["To"] = recipient or (_pref(conn, "smtp_recipient") or message["From"])
    message["Subject"] = str(subject or "DK Bond Tracker message")
    message.set_content(str(body or ""))
    if attachment:
        filename, content_type, payload = attachment
        maintype, _, subtype = str(content_type or "application/octet-stream").partition("/")
        message.add_attachment(
            payload,
            maintype=maintype or "application",
            subtype=subtype or "octet-stream",
            filename=str(filename or "attachment"),
        )
    if _gmail_ready(conn):
        return _gmail_send(message, conn)
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as client:
                client.login(user, app_password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port) as client:
                if _use_starttls(port, conn):
                    client.starttls()
                client.login(user, app_password)
                client.send_message(message)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-email-send", f"message send failed: {exc}") from exc
    return {"status": "sent", "to": recipient, "subject": str(message["Subject"])}
