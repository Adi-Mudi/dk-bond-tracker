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

from flask import Flask, Response, flash, jsonify, redirect, render_template, request, url_for
from werkzeug.exceptions import HTTPException

from src.alerts import daily_sweep
from src.db import get_conn, init_db
from src.engine import (
    derive_health,
    display_label,
    entry_paid,
    list_months_through_current,
    month_due_passed,
    payout_date_label,
    sort_rows,
    tenure_window,
)
from src.export_csv import (
    LEDGER_HEADERS,
    current_view_csv,
    current_view_rows,
    full_ledger_csv,
)
from src.goals import add_goal, delete_goal, list_goals, update_goal
from src.lock import check_add_allowed
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
    chart_data,
    grid_model,
    insert_position,
    month_label,
    portfolio_snapshot,
    portfolio_totals,
    position_detail,
    received_by_bond,
    returns_history,
    save_payment,
    status_overview,
    summary_amounts,
    summary_counts,
    this_month_returns,
)
from src.share import SECTION_KEYS, build_share_snapshot, share_csv
from src.status import compute_row_status_daywise, month_key, tenure_month_map
from src.validators import (
    AppError,
    active_position_lock,
    add_months,
    date_range_tenure,
    parse_date_value,
    percent_value,
)

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "bonds.db"

ENTRY_GUARD_MESSAGE = "Add position is only allowed from the Watch List form"

EMAIL_TEST_SUCCESS_MESSAGE = "Test email sent. Check the inbox (and the spam folder)."

EMAIL_TEST_FAILURE_MESSAGE = (
    "Sending failed. Authentication failed = usually needs an App Password. "
    "Also check SMTP host, port and security setting."
)


def _ensure_db(db_file):
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
            item["timestamp"] = (item.get("created_at") or "")[:19]
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
            try:
                amount = float(row["interest_payout"]) / int(tenure)
            except (TypeError, ValueError):
                amount = 0.0
        credit = int(row["credit_day"] or 1)
        year, mon = int(month[:4]), int(month[5:7])
        day = min(max(credit, 1), calendar.monthrange(year, mon)[1])
        return {
            "amount": amount,
            "date_label": date(year, mon, day).strftime("%d %b %Y"),
            "sort_key": month,
        }

    STATUS_CHIPS = {
        "Danger": ("danger", "chip-danger"),
        "On-going": ("ongoing", "chip-ongoing"),
        "Matured": ("matured", "chip-matured"),
        "Invalid": ("invalid", "chip-invalid"),
    }

    def dashboard_model(conn):
        counts = summary_counts(conn)
        amounts = summary_amounts(conn)
        received_map = received_by_bond(conn)
        current = month_key(date.today())
        holdings = status_overview(conn)
        ledger = conn.execute(
            "SELECT bond_id, month, amount, paid FROM payment_ledger"
        ).fetchall()
        months_by_bond = {}
        for row in ledger:
            entry = months_by_bond.setdefault(row["bond_id"], {})
            try:
                ledger_amount = float(row["amount"] or 0.0)
                ledger_paid = bool(row["paid"]) and row["amount"] is not None and ledger_amount > 0
            except (TypeError, ValueError):
                ledger_amount = 0.0
                ledger_paid = False
            entry[row["month"]] = {"paid": ledger_paid, "amount": ledger_amount}
        bars = []
        next_payout = None
        for row in holdings:
            try:
                invested = float(row["amount"] or 0.0)
            except (TypeError, ValueError):
                invested = 0.0
            months_map = months_by_bond.get(row["id"], {})
            received = received_map.get(row["id"], 0.0)
            status_label = display_label(row["status"])
            status_slug, chip_class = STATUS_CHIPS.get(status_label, ("invalid", "chip-invalid"))
            bars.append(
                {
                    "company": row["company"] or f"Bond {row['id']}",
                    "invested": invested,
                    "received": received,
                    "status": status_label,
                    "status_slug": status_slug,
                    "chip_class": chip_class,
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
        total_invested = amounts["total_investment"]
        received_total = amounts["till_return"]
        return {
            "counts": counts,
            "total_invested": total_invested,
            "received_total": received_total,
            "outstanding": received_total - total_invested,
            "next_payout_amount": next_payout["amount"] if next_payout else 0.0,
            "next_payout_date": next_payout["date_label"] if next_payout else None,
            "bars": bars,
            "returns": returns_history(conn, date.today()),
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
                        "ERR-add-fields", f"credit day must be an integer in 1-31: {credit_raw!r}"
                    ) from exc
                start_date, end_date, tenure_months, credit_day = date_range_tenure(
                    form.get("start_date", ""), form.get("end_date", ""), credit_value
                )
                if tenure_months < 1:
                    raise AppError(
                        "ERR-date-range",
                        f"tenure must span at least one whole month: {tenure_months}",
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
                month_returns = this_month_returns(conn)
                totals = portfolio_totals(conn)
        except AppError as exc:
            return error_page(exc.code, exc.message, "Financial Goals failed", 500)
        return render_template(
            "goals.html",
            goals=goals,
            error=None,
            error_code=None,
            form={},
            earned_this_month=month_returns["total"] or 0.0,
            total_received=totals["till_return"],
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
                earned_this_month=0.0,
                total_received=0.0,
            ),
            400,
        )

    def watch_candidates(db_file):
        with get_conn(db_file) as conn:
            rows = conn.execute(
                "SELECT id, company, isin, rating, coupon_pct, expected_yield_pct, name, broker "
                "FROM bonds WHERE watch_state = 'watching' ORDER BY company COLLATE NOCASE, id"
            ).fetchall()
        return [dict(row) for row in rows]

    def watch_snapshot(db_file):
        with get_conn(db_file) as conn:
            return portfolio_snapshot(conn)

    def watch_percent(raw, field):
        return percent_value(raw, field, "ERR-watch-add")

    def _row_valid(row):
        try:
            start = parse_date_value(row["start_date"], "start_date")
            end = parse_date_value(row["end_date"], "end_date")
        except AppError:
            return False
        if end <= start:
            return False
        tenure = row["tenure_months"]
        if isinstance(tenure, bool) or not isinstance(tenure, int) or tenure < 1:
            return False
        if "amount" in row.keys():
            try:
                float(row["amount"] or 0.0)
            except (TypeError, ValueError):
                return False
        return True

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
            broker = str(form.get("broker", "")).strip() or None
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
                        "expected_yield_pct, watch_state, broker) VALUES (?, ?, ?, ?, ?, ?, 'watching', ?)",
                        (company, isin, source_note, rating, coupon, est_yield, broker),
                    )
                    if cursor.rowcount != 1:
                        raise AppError("ERR-watch-add", "candidate insert affected 0 rows")
            except AppError as exc:
                return (
                    render_template(
                        "watch.html",
                        candidates=watch_candidates(db_file),
                        snapshot=watch_snapshot(db_file),
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
            "watch.html",
            candidates=candidates,
            snapshot=watch_snapshot(db_file),
            error=None,
            error_code=None,
            form={},
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
                    f"credit day must be an integer in 1-31: {credit_raw!r}",
                ) from exc
            start_date, end_date, tenure_months, credit_day = date_range_tenure(
                form.get("start_date", ""), form.get("end_date", ""), credit_value
            )
            if tenure_months < 1:
                raise AppError(
                    "ERR-date-range",
                    f"tenure must span at least one whole month: {tenure_months}",
                )
            broker = str(form.get("broker", "")).strip()
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

                check_add_allowed(row["company"], row["isin"], conn)
                cursor = conn.execute(
                    "UPDATE bonds SET start_date = ?, end_date = ?, tenure_months = ?, "
                    "credit_day = ?, broker = CASE WHEN ? != '' THEN ? ELSE broker END, "
                    "watch_state = 'holding' "
                    "WHERE id = ? AND watch_state = 'watching'",
                    (
                        start_date.isoformat(),
                        end_date.isoformat(),
                        int(tenure_months),
                        int(credit_day),
                        broker,
                        broker,
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
                    snapshot=watch_snapshot(db_file),
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

    def _portfolio_holdings(conn, bond_rows, ledger_by_bond, today):
        received_by_bond_map = received_by_bond(conn)
        holdings = []
        for row in bond_rows:
            entries = ledger_by_bond.get(row["id"], {})
            bad_amount = False
            try:
                invested = float(row["amount"] or 0.0)
            except (TypeError, ValueError):
                invested = 0.0
                bad_amount = True
            try:
                health = display_label(derive_health(row, entries, today))
                next_payout = "—"
                if health != "Matured":
                    for key in tenure_window(row["start_date"], row["tenure_months"]):
                        if not entry_paid(entries.get(key)):
                            next_payout = payout_date_label(key, row["credit_day"])
                            break
            except AppError:
                health = "Invalid"
                next_payout = "—"
            if bad_amount:
                health = "Invalid"
                next_payout = "—"
            holdings.append(
                {
                    "id": row["id"],
                    "company": row["company"],
                    "isin": row["isin"] or "",
                    "rating": row["rating"],
                    "coupon": row["coupon_pct"],
                    "yield_pct": row["expected_yield_pct"],
                    "frequency": row["payout_cycle"],
                    "invested": invested,
                    "received": received_by_bond_map.get(row["id"], 0.0),
                    "next_payout": next_payout,
                    "health": health,
                }
            )
        return sort_rows(holdings)

    def _portfolio_payouts(bond_rows, ledger_by_bond, today):
        prepared = []
        first_keys = []
        for row in bond_rows:
            entries = ledger_by_bond.get(row["id"], {})
            try:
                float(row["amount"] or 0.0)
            except (TypeError, ValueError):
                prepared.append((row, [], entries, "Invalid", True))
                continue
            try:
                window = tenure_window(row["start_date"], row["tenure_months"])
                first_keys.append(window[0])
                prepared.append(
                    (row, window, entries, display_label(derive_health(row, entries, today)), False)
                )
            except AppError:
                prepared.append((row, [], entries, "Invalid", True))
        months = list_months_through_current(today, min(first_keys) if first_keys else None)
        rows = []
        for row, window, entries, health, invalid in prepared:
            window_set = set(window)
            cells = []
            if invalid:
                for index, _key in enumerate(months):
                    if index == 0:
                        cells.append({"kind": "chip", "text": "Invalid", "chip": "chip-invalid"})
                    else:
                        cells.append({"kind": "text", "text": "—"})
            else:
                for key in months:
                    entry = entries.get(key)
                    if key in window_set:
                        if entry_paid(entry):
                            cells.append({"kind": "amount", "amount": float(entry["amount"])})
                        elif health == "Matured":
                            cells.append({"kind": "chip", "text": "Matured", "chip": "chip-matured"})
                        elif month_due_passed(key, row["credit_day"], today):
                            cells.append({"kind": "chip", "text": "Missed", "chip": "chip-danger"})
                        else:
                            cells.append({"kind": "chip", "text": "Due", "chip": "chip-ongoing"})
                    elif health == "Matured":
                        cells.append({"kind": "chip", "text": "Matured", "chip": "chip-matured"})
                    else:
                        cells.append({"kind": "text", "text": "—"})
            rows.append(
                {
                    "id": row["id"],
                    "company": row["company"],
                    "isin": row["isin"] or "",
                    "health": health,
                    "cells": cells,
                }
            )
        return (
            sort_rows(rows),
            [{"key": key, "label": month_label(key)} for key in months],
        )

    def _portfolio_context(conn, today, tab, form, error, code):
        bond_rows = conn.execute(
            "SELECT id, company, isin, rating, coupon_pct, expected_yield_pct, payout_cycle, "
            "amount, start_date, end_date, tenure_months, credit_day "
            "FROM bonds WHERE watch_state = 'holding' "
            "ORDER BY id"
        ).fetchall()
        ledger_rows = conn.execute(
            "SELECT bond_id, month, amount, paid FROM payment_ledger ORDER BY bond_id, month"
        ).fetchall()
        ledger_by_bond = {}
        for entry in ledger_rows:
            ledger_by_bond.setdefault(entry["bond_id"], {})[entry["month"]] = {
                "amount": entry["amount"],
                "paid": entry["paid"],
            }
        context = {
            "tab": tab,
            "holdings": [],
            "months": [],
            "payouts": [],
            "form": form,
            "error": error,
            "code": code,
        }
        if tab == "holdings":
            context["holdings"] = _portfolio_holdings(conn, bond_rows, ledger_by_bond, today)
        elif bond_rows:
            rows, months = _portfolio_payouts(bond_rows, ledger_by_bond, today)
            context["payouts"] = rows
            context["months"] = months
        return context

    def _portfolio_optional_text(form, field):
        raw = str(form.get(field, "")).strip()
        return raw or None

    def _portfolio_optional_float(form, field):
        raw = str(form.get(field, "")).strip()
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError as exc:
            raise AppError("ERR-add-fields", f"{field} must be a number: {raw!r}") from exc

    def _add_portfolio_position(db_file):
        form = request.form
        company = str(form.get("company", "")).strip()
        isin = str(form.get("isin", "")).strip()
        try:
            with get_conn(db_file) as conn:
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
                        "ERR-add-fields",
                        f"amount must not be negative: {amount_raw!r}",
                    )
                credit_raw = str(form.get("credit_day", "")).strip()
                try:
                    credit_value = int(credit_raw)
                except ValueError as exc:
                    raise AppError(
                        "ERR-add-fields",
                        f"credit day must be an integer in 1-31: {credit_raw!r}",
                    ) from exc
                start_date, end_date, tenure_months, credit_day = date_range_tenure(
                    form.get("start_date", ""), form.get("end_date", ""), credit_value
                )
                if tenure_months < 1:
                    raise AppError(
                        "ERR-date-range",
                        f"tenure must span at least one whole month: {tenure_months}",
                    )
                payout_cycle = _portfolio_optional_text(form, "payout_cycle")
                if payout_cycle is not None and payout_cycle not in (
                    "monthly",
                    "quarterly",
                    "annual",
                ):
                    raise AppError(
                        "ERR-add-fields",
                        f"payout_cycle must be monthly, quarterly or annual: {payout_cycle!r}",
                    )
                issuer_type = _portfolio_optional_text(form, "issuer_type")
                if issuer_type is not None and issuer_type not in (
                    "corporate_bond",
                    "ncd",
                    "sdi",
                    "government",
                    "fd",
                ):
                    raise AppError(
                        "ERR-add-fields",
                        "issuer_type must be one of corporate_bond, ncd, sdi, "
                        f"government, fd: {issuer_type!r}",
                    )
                rating = _portfolio_optional_text(form, "rating")
                rating_agency = _portfolio_optional_text(form, "rating_agency")
                coupon_pct = percent_value(form.get("coupon_pct", ""), "coupon_pct", "ERR-add-fields")
                expected_yield_pct = percent_value(
                    form.get("expected_yield_pct", ""), "expected_yield_pct", "ERR-add-fields"
                )
                face_value = _portfolio_optional_float(form, "face_value")
                broker = str(form.get("broker", "")).strip() or None
                secured = 1 if str(form.get("secured", "1")) == "1" else 0
                check_add_allowed(company, isin, conn)
                try:
                    cursor = conn.execute(
                        "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
                        "tenure_months, credit_day, status, watch_state, rating, rating_agency, "
                        "coupon_pct, expected_yield_pct, payout_cycle, issuer_type, secured, face_value, broker) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            company,
                            isin,
                            company,
                            float(amount),
                            start_date.isoformat(),
                            end_date.isoformat(),
                            int(tenure_months),
                            int(credit_day),
                            "On-going",
                            "holding",
                            rating,
                            rating_agency,
                            coupon_pct,
                            expected_yield_pct,
                            payout_cycle,
                            issuer_type,
                            secured,
                            face_value,
                            broker,
                        ),
                    )
                except sqlite3.IntegrityError as exc:
                    raise AppError(
                        "ERR-add-insert",
                        f"position insert rejected (duplicate ISIN {isin}): {exc}",
                    ) from exc
                if cursor.rowcount != 1:
                    raise AppError(
                        "ERR-add-insert",
                        f"position insert for {company} affected {cursor.rowcount} rows",
                    )
                bond_id = cursor.lastrowid
                current_key = month_key(date.today())
                for key in tenure_window(start_date, tenure_months):
                    if key > current_key:
                        break
                    conn.execute(
                        "INSERT OR IGNORE INTO payment_ledger (bond_id, month, amount, paid) "
                        "VALUES (?, ?, 0, 0)",
                        (bond_id, key),
                    )
        except AppError as exc:
            status_code = 409 if exc.code in ("ERR-active-position", "ERR-add-insert") else 400
            try:
                with get_conn(db_file) as conn:
                    context = _portfolio_context(
                        conn, date.today(), "holdings", form, exc.message, exc.code
                    )
            except AppError:
                context = {
                    "tab": "holdings",
                    "holdings": [],
                    "months": [],
                    "payouts": [],
                    "form": form,
                    "error": exc.message,
                    "code": exc.code,
                }
            return render_template("portfolio.html", **context), status_code
        flash(f"Position added: {company}", "success")
        return redirect(url_for("portfolio_page", tab="holdings"))

    @app.route("/portfolio", methods=["GET", "POST"])
    def portfolio_page():
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        if request.method == "POST":
            return _add_portfolio_position(db_file)
        tab = str(request.args.get("tab") or "holdings")
        if tab not in ("holdings", "payouts"):
            return error_page(
                "ERR-portfolio-tab",
                f"unknown tab: {tab!r} (expected 'holdings' or 'payouts')",
                "Portfolio tab failed",
                400,
            )
        try:
            with get_conn(db_file) as conn:
                context = _portfolio_context(conn, date.today(), tab, {}, None, None)
        except AppError as exc:
            return error_page(exc.code, exc.message, "Portfolio render failed", 500)
        return render_template("portfolio.html", **context)

    @app.route("/portfolio/<int:bond_id>/detail")
    def portfolio_position_detail(bond_id):
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                detail = position_detail(conn, bond_id)
        except AppError as exc:
            return jsonify({"error": exc.code, "message": exc.message}), 404
        return jsonify(detail)

    @app.route("/portfolio/invalid/<int:bond_id>/remove", methods=["POST"])
    def portfolio_invalid_remove(bond_id):
        db_file = Path(app.config["DB_PATH"])
        _ensure_db(db_file)
        try:
            with get_conn(db_file) as conn:
                row = conn.execute(
                    "SELECT id, start_date, end_date, tenure_months, watch_state, amount FROM bonds WHERE id = ?",
                    (bond_id,),
                ).fetchone()
                if row is None:
                    raise AppError("ERR-invalid-remove", f"position not found: {bond_id}")
                if row["watch_state"] != "holding":
                    raise AppError(
                        "ERR-invalid-remove",
                        f"position {bond_id} is {row['watch_state']}; remove only applies to holdings rows",
                    )
                if _row_valid(row):
                    raise AppError(
                        "ERR-invalid-remove",
                        f"position {bond_id} is valid; remove is only for rows with dates that need review",
                    )
                conn.execute("DELETE FROM payment_ledger WHERE bond_id = ?", (bond_id,))
                cursor = conn.execute("DELETE FROM bonds WHERE id = ?", (bond_id,))
                if cursor.rowcount != 1:
                    raise AppError(
                        "ERR-invalid-remove",
                        f"remove for position {bond_id} affected {cursor.rowcount} rows",
                    )
        except AppError as exc:
            return error_page(exc.code, exc.message, "Remove failed", 400)
        flash("Invalid row removed", "success")
        return redirect(url_for("portfolio_page", tab="holdings"))

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

    @app.route("/settings/email/test", methods=["POST"])
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
            except Exception:
                ok = False
                detail = "ERR-email-send"
        status = "success" if ok else "failure"
        message = EMAIL_TEST_SUCCESS_MESSAGE if ok else EMAIL_TEST_FAILURE_MESSAGE
        try:
            db_file = Path(app.config["DB_PATH"])
            _ensure_db(db_file)
            with get_conn(db_file) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
                    ("email_test_last_status", status),
                )
                conn.execute(
                    "INSERT OR REPLACE INTO alert_prefs (key, value) VALUES (?, ?)",
                    ("email_test_last_at", date.today().isoformat()),
                )
        except Exception as exc:
            print(f"email test status persist failed: {exc}", file=sys.stderr)
        return jsonify({"status": status, "message": message, "detail": detail})

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
