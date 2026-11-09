import calendar

from datetime import date

from flask import Blueprint, redirect, render_template, request, url_for

from src.db import get_conn
from src.engine import display_label
from src.ledger import ledger_by_bond, save_payment
from src.phase4 import tds_breakdown
from src.queries import (
    MONTH_PATTERN,
    grid_model,
    month_label,
    received_by_bond,
    returns_history,
    status_overview,
    summary_amounts,
    summary_counts,
)
from src.status import compute_row_status_daywise, month_key, tenure_month_map
from src.validators import AppError, add_months, parse_date_value, safe_float
from src.views.common import app_db, entry_guard, error_page

bp = Blueprint("dashboard", __name__)

STATUS_CHIPS = {
    "Danger": ("danger", "chip-danger"),
    "On-going": ("ongoing", "chip-ongoing"),
    "Matured": ("matured", "chip-matured"),
    "Invalid": ("invalid", "chip-invalid"),
}


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
    amount = safe_float(entry.get("amount"))
    if amount <= 0 and row["interest_payout"] is not None:
        try:
            amount = safe_float(row["interest_payout"]) / int(tenure)
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


def dashboard_model(conn, today):
    counts = summary_counts(conn)
    amounts = summary_amounts(conn)
    received_map = received_by_bond(conn)
    current = month_key(today)
    holdings = status_overview(conn)
    months_by_bond = ledger_by_bond(conn)
    bars = []
    next_payout = None
    for row in holdings:
        invested = safe_float(row["amount"])
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
        "received_tds": amounts["received_tds"],
        "received_gross": amounts["received_gross"],
        "outstanding": received_total - total_invested,
        "next_payout_amount": next_payout["amount"] if next_payout else 0.0,
        "next_payout_date": next_payout["date_label"] if next_payout else None,
        "bars": bars,
        "returns": returns_history(conn, today),
    }


@bp.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        return entry_guard()
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            context = dashboard_model(conn, date.today())
    except AppError as exc:
        return error_page(exc.code, exc.message, "Dashboard query failed", 500)
    return render_template("dashboard.html", **context)


@bp.route("/grid", methods=["GET", "POST"])
def grid():
    if request.method == "POST":
        return entry_guard()
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            model = grid_model(conn, date.today())
    except AppError as exc:
        return error_page("ERR-render-grid", str(exc), "Month grid render failed", 500)
    return render_template("grid.html", **model)


@bp.route("/payment/<int:bond_id>/<month>", methods=["GET", "POST"])
def payment_edit(bond_id, month):
    db_file = app_db()
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
                    "SELECT amount, paid, tds_applied FROM payment_ledger "
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
            tds_applied = True
            if ledger is not None:
                amount_value = float(ledger["amount"] or 0.0)
                paid_flag = bool(ledger["paid"]) and amount_value > 0
                tds_applied = bool(ledger["tds_applied"])
            breakdown = tds_breakdown(amount_value, tds_applied)
        except AppError as exc:
            return error_page(exc.code, exc.message, "Payment edit failed", 400)
        return render_template(
            "payment_edit.html",
            bond=dict(bond),
            month=month,
            month_label=month_label(month),
            state=state,
            amount=amount_value,
            paid=paid_flag,
            tds_applied=tds_applied,
            tds=breakdown["tds"],
            gross=breakdown["gross"],
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
        tds_applied = request.form.get("tds") in ("on", "1", "true", "yes")
        with get_conn(db_file) as conn:
            bond = conn.execute(
                "SELECT start_date, tenure_months, credit_day FROM bonds WHERE id = ?",
                (bond_id,),
            ).fetchone()
            if bond is not None and MONTH_PATTERN.match(str(month).strip()):
                window = tenure_month_map(
                    conn, bond_id, bond["start_date"], bond["tenure_months"]
                )
                if month not in window:
                    raise AppError(
                        "ERR-ledger-edit",
                        f"month outside the payment window: {month!r}",
                    )
            save_payment(conn, bond_id, month, amount, paid, tds_applied)
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
        return error_page(exc.code, exc.message, "Payment save failed", 400)
    return redirect(url_for("dashboard.grid"))
