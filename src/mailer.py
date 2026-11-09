import os
import smtplib

from email.message import EmailMessage

from .validators import AppError

DEFAULT_SMTP_HOST = "smtp.gmail.com"
DEFAULT_SMTP_PORT = 465


def _config():
    host = os.environ.get("SMTP_HOST") or DEFAULT_SMTP_HOST
    port_raw = os.environ.get("SMTP_PORT")
    if port_raw:
        try:
            port = int(port_raw)
        except ValueError as exc:
            raise AppError("ERR-smtp-unconfigured", f"SMTP_PORT must be an integer: {port_raw!r}") from exc
    else:
        port = DEFAULT_SMTP_PORT
    user = os.environ.get("SMTP_USER")
    if not user:
        raise AppError("ERR-smtp-unconfigured", "SMTP_USER is not set")
    app_password = os.environ.get("SMTP_APP_PASSWORD")
    if not app_password:
        raise AppError("ERR-smtp-unconfigured", "SMTP_APP_PASSWORD is not set")
    recipient = os.environ.get("ALERT_TO") or user
    return host, port, user, app_password, recipient


def _use_starttls(port):
    if port == 465:
        return False
    if os.environ.get("SMTP_STARTTLS") == "1":
        return True
    return port == 587


def send_alert_email(event):
    if not isinstance(event, dict):
        raise AppError("ERR-email-send", f"alert event must be a dict: {event!r}")
    host, port, user, app_password, recipient = _config()
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
    message = f"From: {user}\r\nTo: {recipient}\r\nSubject: {subject}\r\n\r\n{body}"
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as client:
                client.login(user, app_password)
                client.sendmail(user, [recipient], message)
        else:
            with smtplib.SMTP(host, port) as client:
                if _use_starttls(port):
                    client.starttls()
                client.login(user, app_password)
                client.sendmail(user, [recipient], message)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-email-send", f"email send failed for {company} {month}: {exc}") from exc
    return {"status": "sent", "to": recipient, "subject": subject}


def send_message(subject, body, attachment=None):
    host, port, user, app_password, recipient = _config()
    message = EmailMessage()
    message["From"] = user
    message["To"] = recipient
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
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port) as client:
                client.login(user, app_password)
                client.send_message(message)
        else:
            with smtplib.SMTP(host, port) as client:
                if _use_starttls(port):
                    client.starttls()
                client.login(user, app_password)
                client.send_message(message)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-email-send", f"message send failed: {exc}") from exc
    return {"status": "sent", "to": recipient, "subject": str(message["Subject"])}
