from pathlib import Path

from flask import current_app, render_template

from src.db import init_db

from src.version import APP_VERSION

__all__ = [
    "APP_VERSION",
    "app_db",
    "error_page",
]
BUILD_NOTES = "DK Bond Tracker standalone build — watchlist upgrade v6 (D43 ordering, day-wise alerts, themes)"

ENTRY_GUARD_MESSAGE = "Add position is only allowed from the Watch List form"

EMAIL_TEST_SUCCESS_MESSAGE = "Test email sent. Check the inbox (and the spam folder)."

EMAIL_TEST_FAILURE_MESSAGE = (
    "Sending failed. Authentication failed = usually needs an App Password. "
    "Also check SMTP host, port and security setting."
)


def app_db():
    path = Path(current_app.config["DB_PATH"])
    init_db(path)
    return path


def error_page(code, message, title, status):
    return (
        render_template(
            "error.html",
            code=code,
            message=message,
            title=title,
        ),
        status,
    )


def entry_guard():
    return error_page("ERR-entry-guard", ENTRY_GUARD_MESSAGE, "Add position rejected", 403)
