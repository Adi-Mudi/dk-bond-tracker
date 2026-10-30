import argparse
import json
import os
import sqlite3
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, flash, redirect, render_template, request, url_for

from src.alerts import daily_sweep
from src.db import get_conn, init_db
from src.import_xlsm import import_workbook
from src.mailer import send_alert_email
from src.notifications import (
    due_reminders,
    list_notifications,
    mark_all_read,
    notify,
    notify_once,
    unread_count,
)
from src.queries import (
    active_bonds_in_month,
    chart_data,
    grid_model,
    insert_position,
    month_label,
    monthly_history,
    save_payment,
    status_overview,
    summary_amounts,
    summary_counts,
    this_month_returns,
)
from src.status import compute_row_status_daywise, month_key, tenure_month_map
from src.validators import AppError, active_position_lock, date_range_tenure

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "bonds.db"

ENTRY_GUARD_MESSAGE = "Add position is only allowed from the Watch List form"


def _ensure_db(db_file):
    if not db_file.exists():
        init_db(db_file)


def _attempt_email(conn, event):
    try:
        send_alert_email(event)
    except AppError as exc:
        notify(conn, "warn", f"email failed: {exc}")
        print(f"email failed: {exc}", file=sys.stderr)
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


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path) if db_path else str(DEFAULT_DB_PATH)
    app.secret_key = os.environ.get("FLASK_SECRET_KEY") or os.urandom(32)
    db_file = Path(app.config["DB_PATH"])
    _ensure_db(db_file)
    _startup_alerts(db_file, date.today())

    def entry_guard():
        return (
            render_template(
                "error.html",
                code="ERR-entry-guard",
                message=ENTRY_GUARD_MESSAGE,
                title="Add position rejected",
            ),
            403,
        )

    @app.context_processor
    def inject_header_alerts():
        current_db = Path(app.config["DB_PATH"])
        if not current_db.exists():
            return {"unread_count": 0, "recent_notifications": []}
        with get_conn(current_db) as conn:
            count = unread_count(conn)
            recent = list_notifications(conn, limit=5)
        for item in recent:
            item["timestamp"] = (item.get("created_at") or "")[:16]
        return {"unread_count": count, "recent_notifications": recent}

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            return entry_guard()
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                today = date.today()
                context = {
                    "counts": summary_counts(conn, today),
                    "amounts": summary_amounts(conn, today),
                    "this_month": this_month_returns(conn, today),
                    "active_bonds": active_bonds_in_month(conn, today),
                    "history": monthly_history(conn, today),
                    "overview": status_overview(conn, today),
                    "charts": chart_data(conn, today),
                    "current_month": month_key(today),
                }
        except AppError as exc:
            return (
                render_template(
                    "error.html",
                    code=exc.code,
                    message=exc.message,
                    title="Dashboard query failed",
                ),
                500,
            )
        return render_template("dashboard.html", **context)

    @app.route("/grid", methods=["GET", "POST"])
    def grid():
        if request.method == "POST":
            return entry_guard()
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                model = grid_model(conn, date.today())
        except AppError as exc:
            return (
                render_template(
                    "error.html",
                    code="ERR-render-grid",
                    message=str(exc),
                    title="Month grid render failed",
                ),
                500,
            )
        return render_template("grid.html", **model)

    @app.route("/payment/<int:bond_id>/<month>", methods=["GET", "POST"])
    def payment_edit(bond_id, month):
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if request.method == "GET":
            try:
                with get_conn(db_file) as conn:
                    bond = conn.execute(
                        "SELECT id, company, isin, start_date, tenure_months, credit_day "
                        "FROM bonds WHERE id = ?",
                        (bond_id,),
                    ).fetchone()
                    if bond is None:
                        raise AppError(
                            "ERR-ledger-edit", f"bond not found: {bond_id!r}"
                        )
                    ledger = conn.execute(
                        "SELECT amount, paid FROM payment_ledger "
                        "WHERE bond_id = ? AND month = ?",
                        (bond_id, month),
                    ).fetchone()
                    today = date.today()
                    window = tenure_month_map(
                        conn, bond_id, bond["start_date"], bond["tenure_months"]
                    )
                current_key = month_key(today)
                if month not in window:
                    state = "outside the payment window"
                elif ledger is not None and ledger["paid"] and ledger["amount"] and float(ledger["amount"]) > 0:
                    state = "paid"
                elif month < current_key:
                    state = "currently due (unpaid past month)"
                elif month == current_key:
                    state = "due this month"
                else:
                    state = "future month (not yet due)"
                amount_value = 0.0
                paid_flag = False
                if ledger is not None:
                    amount_value = float(ledger["amount"] or 0.0)
                    paid_flag = bool(ledger["paid"]) and amount_value > 0
            except AppError as exc:
                return (
                    render_template(
                        "error.html",
                        code=exc.code,
                        message=exc.message,
                        title="Payment edit failed",
                    ),
                    400,
                )
            return render_template(
                "payment_edit.html",
                bond=dict(bond),
                month=month,
                month_label=month_label(month),
                state=state,
                amount=amount_value,
                paid=paid_flag,
            )
        try:
            amount_raw = request.form.get("amount", "")
            try:
                amount = float(str(amount_raw).strip())
            except (TypeError, ValueError) as exc:
                raise AppError(
                    "ERR-ledger-insert",
                    f"amount must be a number: {amount_raw!r}",
                ) from exc
            paid = request.form.get("paid") in ("on", "1", "true", "yes")
            with get_conn(db_file) as conn:
                save_payment(conn, bond_id, month, amount, paid)
                bond = conn.execute(
                    "SELECT start_date, tenure_months, credit_day FROM bonds WHERE id = ?",
                    (bond_id,),
                ).fetchone()
                if bond is None:
                    raise AppError("ERR-ledger-edit", f"bond not found: {bond_id!r}")
                today = date.today()
                window = tenure_month_map(
                    conn, bond_id, bond["start_date"], bond["tenure_months"]
                )
                status = compute_row_status_daywise(
                    window, bond["tenure_months"], bond["credit_day"], today
                )
                conn.execute(
                    "UPDATE bonds SET status = ? WHERE id = ?", (status, bond_id)
                )
        except AppError as exc:
            return (
                render_template(
                    "error.html",
                    code=exc.code,
                    message=exc.message,
                    title="Payment save failed",
                ),
                400,
            )
        return redirect(url_for("grid"))

    @app.route("/add", methods=["GET", "POST"])
    def add_position():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if request.method == "GET":
            return render_template("add_position.html", form={}, error=None, code=None)
        form = request.form
        company = str(form.get("company", "")).strip()
        isin = str(form.get("isin", "")).strip()
        try:
            with get_conn(db_file) as conn:
                try:
                    active_position_lock(conn, company, isin)
                except AppError as exc:
                    return (
                        render_template(
                            "add_position.html",
                            form=form,
                            error=f"{exc.message} — no override",
                            code=exc.code,
                        ),
                        409,
                    )
                if not company:
                    raise AppError("ERR-add-fields", "company is required")
                if not isin:
                    raise AppError("ERR-add-fields", "ISIN is required")
                amount_raw = str(form.get("amount", "")).strip()
                try:
                    amount = float(amount_raw)
                except ValueError as exc:
                    raise AppError(
                        "ERR-add-fields", f"amount must be a number: {amount_raw!r}"
                    ) from exc
                if amount < 0:
                    raise AppError(
                        "ERR-add-fields", f"amount must not be negative: {amount_raw!r}"
                    )
                credit_raw = str(form.get("credit_day", "")).strip()
                try:
                    credit_value = int(credit_raw)
                except ValueError as exc:
                    raise AppError(
                        "ERR-add-fields", f"credit day must be an integer in 1-28: {credit_raw!r}"
                    ) from exc
                start_date, end_date, tenure_months, credit_day = date_range_tenure(
                    form.get("start_date", ""), form.get("end_date", ""), credit_value
                )
                try:
                    insert_position(
                        conn,
                        company,
                        isin,
                        amount,
                        start_date,
                        end_date,
                        tenure_months,
                        credit_day,
                    )
                except sqlite3.IntegrityError as exc:
                    raise AppError(
                        "ERR-add-insert",
                        f"position insert rejected (duplicate ISIN {isin}): {exc}",
                    ) from exc
        except AppError as exc:
            status_code = 409 if exc.code in ("ERR-active-position", "ERR-add-insert") else 400
            return (
                render_template(
                    "add_position.html",
                    form=form,
                    error=exc.message,
                    code=exc.code,
                ),
                status_code,
            )
        flash(f"Position added: {company}", "success")
        return redirect(url_for("watch_list"))

    @app.route("/watch")
    def watch_list():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                entries = status_overview(conn, date.today())
        except AppError as exc:
            return (
                render_template(
                    "error.html",
                    code=exc.code,
                    message=exc.message,
                    title="Watch list failed",
                ),
                500,
            )
        return render_template("watch.html", entries=entries)

    @app.route("/notifications")
    def notifications_page():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        with get_conn(db_file) as conn:
            rows = list_notifications(conn)
        return render_template("notifications.html", notifications=rows)

    @app.route("/notifications/read_all", methods=["POST"])
    def notifications_read_all():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        with get_conn(db_file) as conn:
            mark_all_read(conn)
        return redirect(url_for("notifications_page"))

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dk-bond-tracker")
    parser.add_argument("--import", dest="import_path", metavar="XLSM")
    parser.add_argument("--db", dest="db_path", default=str(DEFAULT_DB_PATH), metavar="SQLITE")
    args = parser.parse_args(argv)
    if args.import_path:
        try:
            summary = import_workbook(args.import_path, args.db_path)
        except AppError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(summary, indent=2))
        return 0
    create_app(args.db_path).run(host="127.0.0.1", port=5000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
