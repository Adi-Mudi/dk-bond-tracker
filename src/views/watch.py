import json
import re

from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.engine import tenure_window
from src.lock import check_add_allowed
from src.prefs import get_pref, set_pref
from src.queries import delete_candidate, portfolio_snapshot
from src.status import month_key
from src.validators import (
    AppError,
    date_range_tenure,
    parse_date_value,
    percent_value,
    validate_positive_int,
)
from src.views.common import app_db, error_page

bp = Blueprint("watch", __name__)

ISIN_PATTERN = re.compile(r"^[A-Z]{2}[A-Z0-9]{9}[0-9]$")

WATCH_ISSUER_TYPES = ("corporate_bond", "ncd", "sdi", "government", "fd")
WATCH_PAYOUT_CYCLES = ("monthly", "quarterly", "annual")
WATCH_RATINGS = ("AAA", "AA+", "AA", "AA-", "A+", "A", "A-", "BBB+", "BBB", "BBB-")
WATCH_AGENCIES = ("CRISIL", "ICRA", "CARE", "India Ratings", "Brickwork", "Infomerics")
WATCH_BROKERS = (
    "ICICI Direct",
    "HDFC Sec",
    "Zerodha",
    "Groww",
    "5paisa",
    "Upstox",
    "Angel One",
    "Kotak",
    "Axis Direct",
    "SBI Sec",
)
CUSTOM_AGENCIES_KEY = "watch_custom_agencies"
CUSTOM_BROKERS_KEY = "watch_custom_brokers"


def _custom_values(conn, key):
    raw = get_pref(conn, key)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _remember_custom(conn, key, value, presets):
    if not value or value in presets:
        return
    values = _custom_values(conn, key)
    if value in values:
        return
    values.append(value)
    set_pref(conn, key, json.dumps(values))


def watch_options(db_file):
    with get_conn(db_file) as conn:
        agencies = _custom_values(conn, CUSTOM_AGENCIES_KEY)
        brokers = _custom_values(conn, CUSTOM_BROKERS_KEY)
    return {
        "ratings": list(WATCH_RATINGS),
        "agencies": list(WATCH_AGENCIES)
        + [item for item in agencies if item not in WATCH_AGENCIES],
        "brokers": list(WATCH_BROKERS)
        + [item for item in brokers if item not in WATCH_BROKERS],
    }


def watch_register(db_file):
    with get_conn(db_file) as conn:
        rows = conn.execute(
            "SELECT company, isin, watch_state FROM bonds "
            "WHERE company IS NOT NULL AND trim(company) <> '' "
            "ORDER BY company COLLATE NOCASE, id"
        ).fetchall()
    grouped = {}
    order = []
    for row in rows:
        name = row["company"]
        key = name.strip().lower()
        if key not in grouped:
            grouped[key] = {"company": name, "isins": []}
            order.append(key)
        grouped[key]["isins"].append(
            {"isin": row["isin"] or "", "state": row["watch_state"] or ""}
        )
    return [grouped[key] for key in order]


def watch_goals(db_file):
    with get_conn(db_file) as conn:
        rows = conn.execute(
            "SELECT id, name, target_amount FROM financial_goals ORDER BY id"
        ).fetchall()
    return [dict(row) for row in rows]


def error_field(code, message):
    text = str(message or "").lower()
    if code == "ERR-watch-dup":
        return "isin"
    if "isin" in text:
        return "isin"
    if "company" in text:
        return "company"
    if "rating" in text:
        return "rating"
    return None


def watch_context(db_file, form=None, error=None, error_code=None, form_open=False, duplicate=None):
    field = error_field(error_code, error)
    if duplicate and duplicate.get("field"):
        field = duplicate["field"]
    return {
        "candidates": watch_candidates(db_file),
        "snapshot": watch_snapshot(db_file),
        "error": error,
        "error_code": error_code,
        "error_field": field,
        "duplicate": duplicate,
        "form": form or {},
        "form_open": form_open,
        "options": watch_options(db_file),
        "register": watch_register(db_file),
        "goals": watch_goals(db_file),
    }


def watch_candidates(db_file):
    with get_conn(db_file) as conn:
        rows = conn.execute(
            "SELECT id, company, isin, rating, coupon_pct, expected_yield_pct, name, "
            "broker, rating_agency, issuer_type, secured, face_value, payout_cycle, "
            "qty, watch_investment "
            "FROM bonds WHERE watch_state = 'watching' ORDER BY company COLLATE NOCASE, id"
        ).fetchall()
    candidates = []
    for row in rows:
        item = dict(row)
        item["source_note"] = item.pop("name", None)
        item["invested"] = item.pop("watch_investment", None)
        candidates.append(item)
    return candidates


def watch_snapshot(db_file):
    with get_conn(db_file) as conn:
        return portfolio_snapshot(conn)


def watch_percent(raw, field):
    return percent_value(raw, field, "ERR-watch-add")


def watch_form_values(form):
    company = str(form.get("company", "")).strip()
    isin = str(form.get("isin", "")).strip().upper()
    rating = str(form.get("rating", "")).strip()
    source_note = str(form.get("source_note", "")).strip()
    broker = str(form.get("broker", "")).strip() or None
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
    if rating not in WATCH_RATINGS:
        raise AppError(
            "ERR-watch-add",
            f"rating must be investment grade AAA to BBB-: {rating!r}",
        )
    rating_agency = str(form.get("rating_agency", "")).strip() or None
    issuer_type = str(form.get("issuer_type", "")).strip() or None
    if issuer_type is not None and issuer_type not in WATCH_ISSUER_TYPES:
        raise AppError(
            "ERR-watch-add",
            f"issuer_type must be one of corporate_bond, ncd, sdi, "
            f"government, fd: {issuer_type!r}",
        )
    payout_cycle = str(form.get("payout_cycle", "")).strip() or None
    if payout_cycle is not None and payout_cycle not in WATCH_PAYOUT_CYCLES:
        raise AppError(
            "ERR-watch-add",
            f"payout_cycle must be monthly, quarterly or annual: {payout_cycle!r}",
        )
    secured = 1 if str(form.get("secured", "1")) == "1" else 0
    face_value = percent_value(
        form.get("face_value", ""), "face_value", "ERR-watch-add", required=False
    )
    watch_investment = percent_value(
        form.get("watch_investment", ""),
        "watch_investment",
        "ERR-watch-add",
        required=False,
    )
    qty_raw = str(form.get("qty", "")).strip()
    qty = validate_positive_int(qty_raw, "qty", "ERR-watch-add") if qty_raw else None
    return {
        "company": company,
        "isin": isin,
        "rating": rating,
        "source_note": source_note,
        "broker": broker,
        "coupon": coupon,
        "est_yield": est_yield,
        "rating_agency": rating_agency,
        "issuer_type": issuer_type,
        "payout_cycle": payout_cycle,
        "secured": secured,
        "face_value": face_value,
        "watch_investment": watch_investment,
        "qty": qty,
    }


def watch_insert_candidate(conn, values):
    duplicate = conn.execute(
        "SELECT id, company, isin, watch_state, "
        "(upper(trim(isin)) = upper(?)) AS isin_match "
        "FROM bonds "
        "WHERE lower(trim(company)) = lower(?) OR upper(trim(isin)) = upper(?) "
        "ORDER BY id",
        (values["isin"], values["company"], values["isin"]),
    ).fetchone()
    if duplicate is not None:
        error = AppError(
            "ERR-watch-dup",
            f"duplicate candidate rejected: {duplicate['company']} "
            f"({duplicate['isin']}) already exists as {duplicate['watch_state']}",
        )
        error.duplicate = {
            "id": duplicate["id"],
            "company": duplicate["company"],
            "isin": duplicate["isin"],
            "watch_state": duplicate["watch_state"],
            "field": "isin" if duplicate["isin_match"] else "company",
        }
        raise error
    cursor = conn.execute(
        "INSERT INTO bonds (company, isin, name, rating, coupon_pct, "
        "expected_yield_pct, watch_state, broker, rating_agency, issuer_type, "
        "secured, face_value, payout_cycle, qty, watch_investment) "
        "VALUES (?, ?, ?, ?, ?, ?, 'watching', ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            values["company"],
            values["isin"],
            values["source_note"],
            values["rating"],
            values["coupon"],
            values["est_yield"],
            values["broker"],
            values["rating_agency"],
            values["issuer_type"],
            values["secured"],
            values["face_value"],
            values["payout_cycle"],
            values["qty"],
            values["watch_investment"],
        ),
    )
    if cursor.rowcount != 1:
        raise AppError("ERR-watch-add", "candidate insert affected 0 rows")


@bp.route("/watch", methods=["GET", "POST"])
def watch_list():
    db_file = app_db()
    if request.method == "POST":
        form = request.form
        try:
            values = watch_form_values(form)
            with get_conn(db_file) as conn:
                watch_insert_candidate(conn, values)
                _remember_custom(conn, CUSTOM_AGENCIES_KEY, values["rating_agency"], WATCH_AGENCIES)
                _remember_custom(conn, CUSTOM_BROKERS_KEY, values["broker"], WATCH_BROKERS)
        except AppError as exc:
            return (
                render_template(
                    "watch.html",
                    **watch_context(
                        db_file,
                        form=form,
                        error=exc.message,
                        error_code=exc.code,
                        form_open=True,
                        duplicate=getattr(exc, "duplicate", None),
                    ),
                ),
                409 if exc.code == "ERR-watch-dup" else 400,
            )
        flash(f"Candidate added: {values['company']}", "success")
        return redirect(url_for("watch.watch_list"))
    try:
        context = watch_context(db_file)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Watchlist failed", 500)
    return render_template("watch.html", **context)


@bp.route("/watch/<int:candidate_id>/move", methods=["POST"])
def watch_move(candidate_id):
    db_file = app_db()
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
        purchase_date = parse_date_value(form.get("purchase_date", ""), "purchase_date")
        if tenure_months < 1:
            raise AppError(
                "ERR-date-range",
                f"tenure must span at least one whole month: {tenure_months}",
            )
        quantity = validate_positive_int(form.get("qty", ""), "qty", "ERR-move-watching")
        invested = percent_value(form.get("amount", ""), "amount", "ERR-move-watching")
        broker = str(form.get("broker", "")).strip()
        if not broker:
            raise AppError("ERR-move-watching", "broker is required")
        goal_raw = str(form.get("goal_id", "") or "").strip()
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
            goal_id = None
            if goal_raw:
                try:
                    goal_id = int(goal_raw)
                except ValueError as exc:
                    raise AppError(
                        "ERR-move-watching",
                        f"financial goal must be an integer id: {goal_raw!r}",
                    ) from exc
                if conn.execute(
                    "SELECT id FROM financial_goals WHERE id = ?", (goal_id,)
                ).fetchone() is None:
                    raise AppError(
                        "ERR-move-watching", f"financial goal not found: {goal_id!r}"
                    )
            check_add_allowed(row["company"], row["isin"], conn)
            cursor = conn.execute(
                "UPDATE bonds SET start_date = ?, end_date = ?, tenure_months = ?, "
                "credit_day = ?, amount = ?, qty = ?, broker = ?, purchase_date = ?, "
                "goal_id = ?, watch_state = 'holding' "
                "WHERE id = ? AND watch_state = 'watching'",
                (
                    start_date.isoformat(),
                    end_date.isoformat(),
                    int(tenure_months),
                    int(credit_day),
                    invested,
                    int(quantity),
                    broker,
                    purchase_date.isoformat(),
                    goal_id,
                    candidate_id,
                ),
            )
            if cursor.rowcount != 1:
                raise AppError(
                    "ERR-move-watching",
                    f"move affected {cursor.rowcount} rows for candidate {candidate_id}",
                )
            current_key = month_key(date.today())
            for key in tenure_window(start_date, tenure_months):
                if key > current_key:
                    break
                conn.execute(
                    "INSERT OR IGNORE INTO payment_ledger (bond_id, month, amount, paid) "
                    "VALUES (?, ?, 0, 0)",
                    (candidate_id, key),
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
                **watch_context(db_file, form=form, error=message, error_code=exc.code),
            ),
            409 if exc.code == "ERR-active-position" else 400,
        )
    flash(f"Moved to Portfolio: {moved_company}", "success")
    return redirect(url_for("watch.watch_list"))


@bp.route("/watch/<int:candidate_id>/delete", methods=["POST"])
def watch_delete(candidate_id):
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            row = conn.execute(
                "SELECT id, company, watch_state FROM bonds WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                return error_page(
                    "ERR-watch-delete",
                    f"candidate not found: {candidate_id}",
                    "Delete failed",
                    404,
                )
            if row["watch_state"] != "watching":
                raise AppError(
                    "ERR-watch-delete",
                    f"cannot delete {row['company']}: "
                    f"{row['watch_state']} rows are never deleted",
                )
            delete_candidate(conn, candidate_id)
            company = row["company"]
    except AppError as exc:
        return error_page(exc.code, exc.message, "Delete failed", 409)
    flash(f"Candidate deleted: {company}", "success")
    return redirect(url_for("watch.watch_list"))
