import argparse
import os
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template, request
from werkzeug.exceptions import HTTPException

from src.alerts import daily_sweep
from src.db import get_conn, init_db
from src.mailer import send_alert_email
from src.notifications import (
    due_reminders,
    list_notifications,
    maturity_reminders,
    notify,
    notify_once,
    unread_count,
)
from src.prefs import set_pref
from src.status import recompute_all
from src.validators import AppError
from src.views import common
from src.views.dashboard import bp as dashboard_bp
from src.views.exports import bp as exports_bp
from src.views.goals import bp as goals_bp
from src.views.notifications import bp as notifications_bp
from src.views.portfolio import bp as portfolio_bp
from src.views.search import bp as search_bp
from src.views.settings import bp as settings_bp
from src.views.watch import bp as watch_bp

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "bonds.db"

THEMES = (
    ("system", "System (follow OS)"),
    ("light", "Light (default)"),
    ("dark", "Dark"),
)

ERROR_STATUS = {
    "ERR-active-position": 409,
    "ERR-add-insert": 409,
    "ERR-watch-dup": 409,
    "ERR-entry-guard": 403,
}


def _ensure_db(db_file):
    init_db(db_file)


def _attempt_email(conn, event):
    try:
        send_alert_email(event)
    except Exception as exc:
        notify(conn, "warn", f"email failed: {exc}")
        print(f"email failed: {exc}", file=sys.stderr)


def _startup_alerts(db_file, today):
    with get_conn(db_file) as conn:
        try:
            events = daily_sweep(conn, today)
        except AppError as exc:
            notify(conn, "warn", f"daily sweep failed: {exc}")
            events = []
        else:
            set_pref(conn, "last_sweep", today.isoformat())
        for event in events:
            message = (
                f"{event['company']} credit day {event['credit_day']} "
                f"missed — Danger set ({event['month']})"
            )
            key = f"danger:{event['bond_id']}:{today.isoformat()}"
            if notify_once(conn, key, event["severity"], message) is None:
                continue
            _attempt_email(conn, event)
        try:
            reminders = due_reminders(conn, today)
        except AppError as exc:
            notify(conn, "warn", f"due reminder failed: {exc}")
            reminders = []
        for reminder in reminders:
            _attempt_email(conn, reminder)
        try:
            maturities = maturity_reminders(conn, today)
        except AppError as exc:
            notify(conn, "warn", f"maturity reminder failed: {exc}")
            maturities = []
        for maturity_event in maturities:
            _attempt_email(conn, maturity_event)


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path) if db_path else str(DEFAULT_DB_PATH)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)

    db_file = Path(app.config["DB_PATH"])
    _ensure_db(db_file)
    _startup_alerts(db_file, date.today())

    app.register_blueprint(dashboard_bp)
    app.register_blueprint(portfolio_bp)
    app.register_blueprint(watch_bp)
    app.register_blueprint(goals_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(exports_bp)

    def render_unexpected(error_text):
        endpoint = request.endpoint or "unknown"
        message = error_text or "unexpected failure"
        print(f"ERR-unexpected {endpoint}: {message}", file=sys.stderr)
        return (
            render_template(
                "error.html",
                code="ERR-unexpected",
                message=message,
                title=f"Unexpected error ({endpoint})",
            ),
            500,
        )

    @app.errorhandler(500)
    def handle_internal_error(_error):
        return render_unexpected("internal server error")

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            return error
        return render_unexpected(str(error))

    @app.errorhandler(AppError)
    def handle_app_error(exc):
        return common.error_page(
            exc.code, exc.message, "Request failed", ERROR_STATUS.get(exc.code, 500)
        )

    @app.context_processor
    def inject_header_alerts():
        current_db = Path(app.config["DB_PATH"])
        if not current_db.exists():
            return {"unread_count": 0, "recent_notifications": [], "themes": THEMES}
        with get_conn(current_db) as conn:
            count = unread_count(conn)
            recent = list_notifications(conn, limit=5)
        for item in recent:
            item["timestamp"] = (item.get("created_at") or "")[:19]
        return {"unread_count": count, "recent_notifications": recent, "themes": THEMES}

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dk-bond-tracker")
    parser.add_argument("--db", dest="db_path", default=str(DEFAULT_DB_PATH), metavar="SQLITE")
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="recompute stored bond statuses for today and exit",
    )
    args = parser.parse_args(argv)
    if args.recompute:
        db_file = Path(args.db_path)
        _ensure_db(db_file)
        with get_conn(db_file) as conn:
            changed = recompute_all(conn, date.today())
        print(f"recomputed: changed={len(changed)}")
        return 0
    create_app(args.db_path).run(
        host="127.0.0.1", port=int(os.environ.get("PORT", "5000"))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
