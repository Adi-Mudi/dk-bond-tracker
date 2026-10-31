import argparse
import calendar
import os
import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, Response, flash, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from src.alerts import daily_sweep
from src.db import get_conn, init_db
from src.export_csv import (
    LEDGER_HEADERS,
    current_view_csv,
    current_view_rows,
    full_ledger_csv,
)
from src.goals import add_goal, delete_goal, list_goals, update_goal
from src.mailer import send_alert_email
from src.notifications import (
    due_reminders,
    list_notifications,
    mark_all_read,
    notify,
    notify_once,
    unread_count,
)
from src.phase4 import payment_cycle_of, payout_schedule
from src.print import monthly_print_model
from src.queries import (
    MONTH_PATTERN,
    grid_model,
    insert_position,
    month_label,
    save_payment,
)
from src.share import SECTION_KEYS, build_share_snapshot, share_csv
from src.status import compute_row_status_daywise, month_key, tenure_month_map
from src.validators import AppError, active_position_lock, add_months, date_range_tenure, parse_date_value

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
        else:
            conn.execute(
                "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
                ("last_sweep", today.isoformat()),
            )
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

    def next_payout_for(row, months_map, current):
        tenure = row["tenure_months"]
        if not tenure or int(tenure) < 1 or not row["start_date"]:
            return None
        try:
            start = parse_date_value(row["start_date"], "start_date")
        except AppError:
            return None
        window = [month_key(add_months(start, offset)) for offset in range(int(tenure))]
        unpaid = [key for key in window if not months_map.get(key, {}).get("paid")]
        if not unpaid:
            return None
        upcoming = [key for key in unpaid if key >= current]
        month = upcoming[0] if upcoming else unpaid[0]
        entry = months_map.get(month, {})
        amount = float(entry.get("amount") or 0.0)
        if amount <= 0 and row["interest_payout"] is not None:
            amount = float(row["interest_payout"]) / int(tenure)
        credit = int(row["credit_day"] or 1)
        year, mon = int(month[:4]), int(month[5:7])
        day = min(max(credit, 1), calendar.monthrange(year, mon)[1])
        return {
            "amount": amount,
            "date_label": date(year, mon, day).strftime("%d %b %Y"),
            "sort_key": month,
        }

    def dashboard_model(conn):
        current = month_key(date.today())
        holdings = conn.execute(
            "SELECT id, company, amount, interest_payout, tenure_months, credit_day, start_date "
            "FROM bonds WHERE watch_state = 'holding' ORDER BY company COLLATE NOCASE, id"
        ).fetchall()
        ledger = conn.execute(
            "SELECT bond_id, month, amount, paid FROM payment_ledger"
        ).fetchall()
        months_by_bond = {}
        for row in ledger:
            entry = months_by_bond.setdefault(row["bond_id"], {})
            entry[row["month"]] = {
                "paid": bool(row["paid"]) and row["amount"] is not None and float(row["amount"]) > 0,
                "amount": float(row["amount"] or 0.0),
            }
        bars = []
        total_invested = 0.0
        received_total = 0.0
        next_payout = None
        for row in holdings:
            invested = float(row["amount"] or 0.0)
            months_map = months_by_bond.get(row["id"], {})
            received = sum(entry["amount"] for entry in months_map.values() if entry["paid"])
            total_invested += invested
            received_total += received
            bars.append(
                {
                    "company": row["company"] or f"Bond {row['id']}",
                    "invested": invested,
                    "received": received,
                }
            )
            payout = next_payout_for(row, months_map, current)
            if payout is not None and (next_payout is None or payout["sort_key"] < next_payout["sort_key"]):
                next_payout = payout
        max_invested = max((bar["invested"] for bar in bars), default=0.0)
        for bar in bars:
            bar["bar_width"] = round(bar["invested"] / max_invested * 100.0, 1) if max_invested > 0 else 0.0
            bar["recv_width"] = (
                min(100.0, round(bar["received"] / bar["invested"] * 100.0, 1)) if bar["invested"] > 0 else 0.0
            )
        return {
            "total_invested": total_invested,
            "received_total": received_total,
            "outstanding": received_total - total_invested,
            "next_payout_amount": next_payout["amount"] if next_payout else 0.0,
            "next_payout_date": next_payout["date_label"] if next_payout else None,
            "bars": bars,
        }

    @app.route("/", methods=["GET", "POST"])
    def index():
        if request.method == "POST":
            return entry_guard()
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                context = dashboard_model(conn)
        except AppError as exc:
            return error_page(exc.code, exc.message, "Dashboard query failed", 500)
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

    @app.route("/goals", methods=["GET", "POST"])
    def goals_page():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if request.method == "POST":
            try:
                with get_conn(db_file) as conn:
                    add_goal(
                        conn,
                        request.form.get("name", ""),
                        request.form.get("target_amount", ""),
                        request.form.get("target_end_date", ""),
                        request.form.get("note", ""),
                        request.form.get("saved_amount", ""),
                    )
            except AppError as exc:
                return _goals_error_page(db_file, exc, request.form)
            flash("Goal added", "success")
            return redirect(url_for("goals_page"))
        try:
            with get_conn(db_file) as conn:
                goals = list_goals(conn, date.today())
        except AppError as exc:
            return error_page(exc.code, exc.message, "Financial Goals failed", 500)
        return render_template(
            "goals.html", goals=goals, error=None, error_code=None, form={}
        )

    @app.route("/goals/<int:goal_id>/edit", methods=["POST"])
    def goals_edit(goal_id):
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                update_goal(
                    conn,
                    goal_id,
                    request.form.get("name", ""),
                    request.form.get("target_amount", ""),
                    request.form.get("target_end_date", ""),
                    request.form.get("saved_amount", ""),
                )
        except AppError as exc:
            return _goals_error_page(db_file, exc, request.form)
        flash(f"Goal updated: {goal_id}", "success")
        return redirect(url_for("goals_page"))

    @app.route("/goals/<int:goal_id>/delete", methods=["POST"])
    def goals_delete(goal_id):
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                delete_goal(conn, goal_id)
        except AppError as exc:
            return _goals_error_page(db_file, exc, request.form)
        flash(f"Goal deleted: {goal_id}", "success")
        return redirect(url_for("goals_page"))

    def _goals_error_page(db_file, exc, form):
        try:
            with get_conn(db_file) as conn:
                goals = list_goals(conn, date.today())
        except AppError:
            goals = []
        return (
            render_template(
                "goals.html",
                goals=goals,
                error=exc.message,
                error_code=exc.code,
                form=form,
            ),
            400,
        )

    def watch_candidates(db_file):
        with get_conn(db_file) as conn:
            rows = conn.execute(
                "SELECT id, company, isin, rating, coupon_pct, expected_yield_pct, name "
                "FROM bonds WHERE watch_state = 'watching' ORDER BY company COLLATE NOCASE, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def watch_percent(raw, field):
        text = str(raw or "").strip()
        if not text:
            raise AppError("ERR-watch-add", f"{field} is required")
        try:
            value = float(text)
        except ValueError as exc:
            raise AppError("ERR-watch-add", f"{field} must be a number: {raw!r}") from exc
        if value < 0:
            raise AppError("ERR-watch-add", f"{field} must not be negative: {raw!r}")
        return value

    ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

    @app.route("/watch", methods=["GET", "POST"])
    def watch_list():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if request.method == "POST":
            form = request.form
            company = str(form.get("company", "")).strip()
            isin = str(form.get("isin", "")).strip().upper()
            rating = str(form.get("rating", "")).strip()
            source_note = str(form.get("source_note", "")).strip()
            try:
                coupon = watch_percent(form.get("coupon_pct", ""), "coupon")
                est_yield = watch_percent(form.get("expected_yield_pct", ""), "est yield")
                if not company:
                    raise AppError("ERR-watch-add", "company is required")
                if not isin:
                    raise AppError("ERR-watch-add", "ISIN is required")
                if not ISIN_PATTERN.match(isin):
                    raise AppError(
                        "ERR-watch-add",
                        f"ISIN format invalid: {isin!r} (expected 12 characters, e.g. INE9000A01001)",
                    )
                if not rating:
                    raise AppError("ERR-watch-add", "rating is required")
                with get_conn(db_file) as conn:
                    duplicate = conn.execute(
                        "SELECT company, isin, watch_state FROM bonds "
                        "WHERE lower(trim(company)) = lower(?) OR upper(trim(isin)) = upper(?)",
                        (company, isin),
                    ).fetchone()
                    if duplicate is not None:
                        raise AppError(
                            "ERR-watch-dup",
                            f"duplicate candidate rejected: {duplicate['company']} "
                            f"({duplicate['isin']}) already exists as {duplicate['watch_state']}",
                        )
                    cursor = conn.execute(
                        "INSERT INTO bonds (company, isin, name, rating, coupon_pct, "
                        "expected_yield_pct, watch_state) VALUES (?, ?, ?, ?, ?, ?, 'watching')",
                        (company, isin, source_note, rating, coupon, est_yield),
                    )
                    if cursor.rowcount != 1:
                        raise AppError("ERR-watch-add", "candidate insert affected 0 rows")
            except AppError as exc:
                return (
                    render_template(
                        "watch.html",
                        candidates=watch_candidates(db_file),
                        error=exc.message,
                        error_code=exc.code,
                        form=form,
                    ),
                    409 if exc.code == "ERR-watch-dup" else 400,
                )
            flash(f"Candidate added: {company}", "success")
            return redirect(url_for("watch_list"))
        try:
            candidates = watch_candidates(db_file)
        except AppError as exc:
            return (
                render_template(
                    "error.html",
                    code=exc.code,
                    message=exc.message,
                    title="Watchlist failed",
                ),
                500,
            )
        return render_template(
            "watch.html", candidates=candidates, error=None, error_code=None, form={}
        )

    @app.route("/watch/<int:candidate_id>/move", methods=["POST"])
    def watch_move(candidate_id):
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        form = request.form
        try:
            credit_raw = str(form.get("credit_day", "")).strip()
            try:
                credit_value = int(credit_raw)
            except ValueError as exc:
                raise AppError(
                    "ERR-move-watching",
                    f"credit day must be an integer in 1-28: {credit_raw!r}",
                ) from exc
            start_date, end_date, tenure_months, credit_day = date_range_tenure(
                form.get("start_date", ""), form.get("end_date", ""), credit_value
            )
            with get_conn(db_file) as conn:
                row = conn.execute(
                    "SELECT id, company, isin, watch_state FROM bonds WHERE id = ?",
                    (candidate_id,),
                ).fetchone()
                if row is None:
                    raise AppError("ERR-move-watching", f"candidate not found: {candidate_id}")
                if row["watch_state"] != "watching":
                    raise AppError(
                        "ERR-move-watching",
                        f"already in Portfolio: {row['company']} is {row['watch_state']}",
                    )
                from src.lock import check_add_allowed

                check_add_allowed(conn, row["company"], row["isin"])
                cursor = conn.execute(
                    "UPDATE bonds SET start_date = ?, end_date = ?, tenure_months = ?, "
                    "credit_day = ?, watch_state = 'holding' "
                    "WHERE id = ? AND watch_state = 'watching'",
                    (
                        start_date.isoformat(),
                        end_date.isoformat(),
                        int(tenure_months),
                        int(credit_day),
                        candidate_id,
                    ),
                )
                if cursor.rowcount != 1:
                    raise AppError(
                        "ERR-move-watching",
                        f"move affected {cursor.rowcount} rows for candidate {candidate_id}",
                    )
                moved_company = row["company"]
        except AppError as exc:
            message = (
                f"{exc.message} — no override"
                if exc.code == "ERR-active-position"
                else exc.message
            )
            return (
                render_template(
                    "watch.html",
                    candidates=watch_candidates(db_file),
                    error=message,
                    error_code=exc.code,
                    form=form,
                ),
                409 if exc.code == "ERR-active-position" else 400,
            )
        flash(f"Moved to Portfolio: {moved_company}", "success")
        return redirect(url_for("watch_list"))

    def alert_prefs_map(db_file):
        with get_conn(db_file) as conn:
            rows = conn.execute("SELECT key, value FROM alert_prefs").fetchall()
        return {row["key"]: row["value"] for row in rows}

    @app.route("/notifications", methods=["GET", "POST"])
    def notifications_page():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if request.method == "POST":
            inapp_on = request.form.get("inapp") in ("on", "1", "true", "yes")
            email_on = request.form.get("email") in ("on", "1", "true", "yes")
            with get_conn(db_file) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
                    ("alert_channel_inapp", "1" if inapp_on else "0"),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
                    ("alert_channel_email", "1" if email_on else "0"),
                )
            flash("Alert channels saved", "success")
            return redirect(url_for("notifications_page"))
        return render_template("notifications.html", prefs=alert_prefs_map(db_file))

    @app.route("/notifications/read_all", methods=["POST"])
    def notifications_read_all():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        with get_conn(db_file) as conn:
            mark_all_read(conn)
        return redirect(url_for("notifications_page"))

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

    @app.route("/export.csv")
    def export_csv_route():
        scope = request.args.get("scope", "")
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if scope == "full":
            try:
                with get_conn(db_file) as conn:
                    text = full_ledger_csv(conn)
            except AppError as exc:
                return error_page(exc.code, exc.message, "CSV export failed", 500)
            filename = "full_ledger.csv"
        elif scope == "current":
            month = str(request.args.get("month", "")).strip()
            if month and not MONTH_PATTERN.match(month):
                return error_page(
                    "ERR-export-view",
                    f"unparseable month (expected YYYY-MM): {month!r}",
                    "CSV export failed",
                    400,
                )
            try:
                with get_conn(db_file) as conn:
                    if not month:
                        row = conn.execute(
                            "SELECT MAX(month) AS latest FROM payment_ledger"
                        ).fetchone()
                        month = row["latest"] if row and row["latest"] else month_key(date.today())
                    rows = current_view_rows(conn, month, date.today())
                    text = current_view_csv(rows, headers=list(LEDGER_HEADERS))
            except AppError as exc:
                status = 400 if exc.code == "ERR-export-view" else 500
                return error_page(exc.code, exc.message, "CSV export failed", status)
            filename = f"view_{month}.csv"
        else:
            return error_page(
                "ERR-export-view",
                f"unknown export scope: {scope!r} (expected 'current' or 'full')",
                "CSV export failed",
                400,
            )
        response = Response(text, mimetype="text/csv")
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    def generate_share():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        selected = request.form.getlist("sections")
        sections = {key: key in selected for key in SECTION_KEYS}
        include_amounts = request.form.get("include_amounts") in ("on", "1", "true", "yes")
        privacy_on = request.form.get("privacy") in ("on", "1", "true", "yes")
        fmt = request.form.get("format", "html")
        if fmt not in ("html", "csv"):
            return error_page(
                "ERR-share-export",
                f"unsupported share format: {fmt!r} (expected 'html' or 'csv')",
                "Share snapshot failed",
                400,
            )
        try:
            with get_conn(db_file) as conn:
                if fmt == "csv":
                    text = share_csv(conn, sections, include_amounts, privacy_on)
                    filename = "share_snapshot.csv"
                else:
                    text = build_share_snapshot(
                        conn, sections, include_amounts, privacy_on
                    )
                    filename = "share_snapshot.html"
        except AppError as exc:
            return error_page(exc.code, exc.message, "Share snapshot failed", 400)
        mimetype = "text/csv" if fmt == "csv" else "text/html"
        response = Response(text, mimetype=mimetype)
        response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    @app.route("/share", methods=["GET", "POST"])
    def share_page():
        if request.method == "GET":
            return render_template("share.html")
        return generate_share()

    @app.route("/share/generate", methods=["POST"])
    def share_generate():
        return generate_share()

    @app.route("/print")
    def print_statement():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        privacy = str(request.args.get("privacy", "")).lower() in ("1", "on", "true", "yes")
        try:
            with get_conn(db_file) as conn:
                model = monthly_print_model(conn, date.today())
        except AppError as exc:
            return error_page(exc.code, exc.message, "Monthly print failed", 500)
        return render_template("monthly_print.html", privacy=privacy, **model)

    @app.route("/payout")
    def payout_page():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        raw_bond = str(request.args.get("bond_id", "")).strip()
        try:
            bond_id = int(raw_bond)
        except ValueError:
            return error_page(
                "ERR-due-dates",
                f"bond_id must be an integer: {raw_bond!r}",
                "Payout schedule failed",
                400,
            )
        cycle = str(request.args.get("cycle", "")).strip().lower()
        try:
            with get_conn(db_file) as conn:
                if not cycle:
                    row = conn.execute(
                        "SELECT payment_type FROM bonds WHERE id = ?", (bond_id,)
                    ).fetchone()
                    if row is None:
                        raise AppError("ERR-due-dates", f"bond not found: {bond_id!r}")
                    cycle = payment_cycle_of(row["payment_type"])
                    if cycle is None:
                        raise AppError(
                            "ERR-due-dates",
                            f"payment type missing or unknown for bond {bond_id}: "
                            f"{row['payment_type']!r}; pass cycle=monthly|quarterly|yearly",
                        )
                schedule = payout_schedule(conn, bond_id, cycle)
        except AppError as exc:
            return error_page(exc.code, exc.message, "Payout schedule failed", 400)
        return render_template("payout.html", schedule=schedule)

    @app.route("/portfolio")
    def portfolio_page():
        return render_template("portfolio.html")

    def settings_from_form(form):
        host = str(form.get("smtp_host", "")).strip()
        port_raw = str(form.get("smtp_port", "")).strip()
        sender = str(form.get("smtp_from", "")).strip()
        recipient = str(form.get("smtp_to", "")).strip()
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
            "smtp_from": sender,
            "smtp_recipient": recipient,
            "privacy_on_startup": "1" if form.get("privacy_on_startup") in checked else "0",
            "share_section_holdings": "1" if form.get("share_holdings") in checked else "0",
            "share_section_payouts": "1" if form.get("share_payouts") in checked else "0",
            "share_section_goals": "1" if form.get("share_goals") in checked else "0",
        }

    @app.route("/settings", methods=["GET", "POST"])
    def settings_page():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
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
                    ),
                    400,
                )
            with get_conn(db_file) as conn:
                for key, value in values.items():
                    conn.execute(
                        "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
                        (key, value),
                    )
            flash("Settings saved", "success")
            return redirect(url_for("settings_page"))
        return render_template(
            "settings.html", prefs=alert_prefs_map(db_file), error=None, error_code=None
        )

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dk-bond-tracker")
    parser.add_argument("--db", dest="db_path", default=str(DEFAULT_DB_PATH), metavar="SQLITE")
    args = parser.parse_args(argv)
    create_app(args.db_path).run(
        host="127.0.0.1", port=int(os.environ.get("PORT", "5000"))
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
