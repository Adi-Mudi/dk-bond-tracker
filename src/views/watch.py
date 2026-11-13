import json
import re

from datetime import date, datetime, timezone

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_PARSE_ERROR,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    INSTRUMENT_FIELDS,
    POSITION_FIELDS,
    SOURCE_PRIORITY,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.normalize import is_investment_grade
from src.bond_master.service import build_default_service, primary_source
from src.db import get_conn
from src.engine import tenure_window
from src.forms import FACT_BY_FIELD, fetched_form_values
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

AUTOFETCH_SESSION_KEY = "watch_autofetch"
BOND_MASTER_TRANSPORT_KEY = "BOND_MASTER_TRANSPORT"

WATCH_FORM_FIELDS = (
    "company",
    "isin",
    "rating",
    "rating_agency",
    "coupon_pct",
    "expected_yield_pct",
    "issuer_type",
    "secured",
    "face_value",
    "payout_cycle",
    "watch_investment",
    "qty",
    "source_note",
    "broker",
)

FETCH_IDLE = "idle"
FETCH_CHECKING = "checking"
FETCH_FOUND = "found"
FETCH_NOT_FOUND = "notfound"
FETCH_OFFLINE = "offline"
FETCH_DOWNGRADE = "downgrade"
FETCH_STATES = (
    FETCH_IDLE,
    FETCH_CHECKING,
    FETCH_FOUND,
    FETCH_NOT_FOUND,
    FETCH_OFFLINE,
    FETCH_DOWNGRADE,
)
FETCH_STATE_LABELS = {
    FETCH_IDLE: "Idle",
    FETCH_CHECKING: "Checking",
    FETCH_FOUND: "Found",
    FETCH_NOT_FOUND: "Not found",
    FETCH_OFFLINE: "Offline",
    FETCH_DOWNGRADE: "Downgraded",
}
OFFLINE_REACH_FAILURE_CODES = (
    FAILURE_OFFLINE,
    FAILURE_UNREACHABLE,
    FAILURE_TIMEOUT,
)
OFFLINE_BLOCKED_FAILURE_CODES = (
    FAILURE_BLOCKED,
    FAILURE_RATE_LIMITED,
)
OFFLINE_FAILURE_CODES = OFFLINE_REACH_FAILURE_CODES + OFFLINE_BLOCKED_FAILURE_CODES
DOWNGRADE_FAILURE_CODES = (
    FAILURE_OFFLINE,
    FAILURE_UNREACHABLE,
    FAILURE_TIMEOUT,
    FAILURE_BLOCKED,
)
RATING_GATE_MESSAGE = (
    "The application supports only AAA to BBB- investment-grade bonds "
    "- this fetched bond cannot be added."
)


def watch_fetch_idle():
    return {
        "state": FETCH_IDLE,
        "states": FETCH_STATES,
        "labels": FETCH_STATE_LABELS,
        "isin": "",
        "facts": {},
        "sources": {},
        "source_names": [],
        "cached": {},
        "asof": "",
        "message": "",
        "values": {},
        "sources_by_field": {},
    }


def _bond_cache():
    application = current_app._get_current_object()
    cache = application.extensions.get("bond_master_cache")
    if cache is None:
        cache = BondMasterCache(current_app.config["DB_PATH"])
        application.extensions["bond_master_cache"] = cache
    return cache


def _bond_service():
    application = current_app._get_current_object()
    service = application.extensions.get("bond_master_service")
    if service is None:
        service = build_default_service(
            _bond_cache(), current_app.config.get(BOND_MASTER_TRANSPORT_KEY)
        )
        application.extensions["bond_master_service"] = service
    return service


def fetch_state(result, events=()):
    if result is None:
        return FETCH_IDLE
    if result.has_facts():
        if any(
            (not event.ok) and event.failure_code in DOWNGRADE_FAILURE_CODES
            for event in events
        ):
            return FETCH_DOWNGRADE
        return FETCH_FOUND
    if result.failure_code in OFFLINE_FAILURE_CODES:
        return FETCH_OFFLINE
    return FETCH_NOT_FOUND


def fetch_message(state, failure_code=None):
    if state == FETCH_NOT_FOUND:
        return "metadata not found - enter manually"
    if state == FETCH_OFFLINE:
        if failure_code in OFFLINE_BLOCKED_FAILURE_CODES:
            return "The source blocked or rate-limited the request"
        return "Could not reach the source"
    if state == FETCH_DOWNGRADE:
        return "filled from a lesser-confidence source"
    return ""


def rating_gate(payload):
    if not payload:
        return None
    facts = payload.get("facts") or {}
    if not facts:
        return None
    rating = str(facts.get("rating") or "").strip()
    if is_investment_grade(rating):
        return None
    return RATING_GATE_MESSAGE


def autofetch_refusal(isin):
    stored = session.get(AUTOFETCH_SESSION_KEY) or {}
    if stored.get("isin") != isin:
        return None
    return rating_gate(stored.get("payload"))


def _source_names(sources):
    names = []
    for field in sources:
        name = sources[field]
        if name and name not in names:
            names.append(name)
    order = list(SOURCE_PRIORITY)
    names.sort(key=lambda item: order.index(item) if item in order else len(order))
    return names


def _asof_now():
    return datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M")


def fetch_payload(result, events=(), cached_row=None, fetched_at=None):
    state = fetch_state(result, events)
    facts = {}
    sources = {}
    if result is not None and result.has_facts():
        for field, value in result.facts().items():
            if value is None:
                continue
            facts[field] = value
            source = result.source_of(field)
            if source:
                sources[field] = source
    cached = {}
    asof = ""
    if state in (FETCH_FOUND, FETCH_DOWNGRADE):
        asof = fetched_at or _asof_now()
    elif state == FETCH_OFFLINE and cached_row:
        cached = {
            field: cached_row[field]
            for field in INSTRUMENT_FIELDS
            if cached_row.get(field) is not None
        }
        asof = str(cached_row.get("fetched_at") or "")
    failure_code = result.failure_code if result is not None else None
    return {
        "state": state,
        "states": FETCH_STATES,
        "labels": FETCH_STATE_LABELS,
        "isin": result.isin if result is not None else "",
        "facts": facts,
        "sources": sources,
        "source_names": _source_names(sources),
        "cached": cached,
        "asof": asof,
        "message": fetch_message(state, failure_code),
        "values": {},
        "sources_by_field": {},
    }


def dirty_fields(raw):
    return {part.strip() for part in str(raw or "").split(",") if part.strip()}


def apply_fetch(current, payload, dirty):
    values = {}
    sources_by_field = {}
    fetched = fetched_form_values(payload.get("facts") or {})
    sources = payload.get("sources") or {}
    for field, value in fetched.items():
        if field in POSITION_FIELDS:
            continue
        existing = str(current.get(field, "") or "").strip()
        if existing and field in dirty:
            continue
        values[field] = value
        source = sources.get(FACT_BY_FIELD.get(field))
        if source:
            sources_by_field[field] = source
    return values, sources_by_field


def reset_facts_on_isin_change(form, dirty):
    for field in FACT_BY_FIELD:
        if field in dirty:
            continue
        form.pop(field, None)
    return form


def run_autofetch(isin, current, dirty):
    stored = session.get(AUTOFETCH_SESSION_KEY)
    if stored and stored.get("isin") == isin:
        payload = dict(stored["payload"])
    else:
        service = _bond_service()
        result = service.lookup(isin)
        events = [event for event in service.events() if event.isin == isin]
        payload = fetch_payload(result, events, cached_row=_bond_cache().lookup(isin))
        session[AUTOFETCH_SESSION_KEY] = {"isin": isin, "payload": payload}
        if payload["state"] == FETCH_FOUND:
            record = {"isin": payload["isin"], "source": primary_source(payload["sources"])}
            record.update(payload["facts"])
            _bond_cache().save(record)
        elif payload["state"] in (FETCH_NOT_FOUND, FETCH_OFFLINE):
            current_app.logger.info("isin autofetch %s -> %s", isin, payload["state"])
    values, sources_by_field = apply_fetch(current, payload, dirty)
    payload = dict(payload)
    payload["values"] = values
    payload["sources_by_field"] = sources_by_field
    edited = {FACT_BY_FIELD[field] for field in dirty if field in FACT_BY_FIELD}
    if edited and payload.get("facts"):
        _bond_cache().mark_edited(payload["isin"], *sorted(edited))
    return payload


def autofetch_form(current):
    form = {}
    for field in WATCH_FORM_FIELDS:
        raw = current.get(field)
        if raw is not None:
            form[field] = raw
    isin = str(current.get("isin", "") or "").strip().upper()
    if not isin or not ISIN_PATTERN.match(isin):
        return (form or None), None
    dirty = dirty_fields(current.get("dirty", ""))
    stored = session.get(AUTOFETCH_SESSION_KEY) or {}
    if stored.get("isin") and stored.get("isin") != isin:
        form = reset_facts_on_isin_change(form, dirty)
    payload = run_autofetch(isin, current, dirty)
    form["isin"] = isin
    form.update(payload["values"])
    return form, payload


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
    if code == "ERR-watch-rating-gate":
        return "rating"
    if code == "ERR-watch-dup":
        return "isin"
    if "isin" in text:
        return "isin"
    if "company" in text:
        return "company"
    if "rating" in text:
        return "rating"
    return None


def watch_context(
    db_file,
    form=None,
    error=None,
    error_code=None,
    form_open=False,
    duplicate=None,
    fetch=None,
):
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
        "fetch": fetch or watch_fetch_idle(),
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
            refusal = autofetch_refusal(str(form.get("isin", "")).strip().upper())
            if refusal:
                raise AppError("ERR-watch-rating-gate", refusal)
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
        if request.args.get("isin"):
            form, fetch = autofetch_form(request.args)
            context = watch_context(
                db_file, form=form, form_open=True, fetch=fetch
            )
        else:
            context = watch_context(db_file)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Watchlist failed", 500)
    return render_template("watch.html", **context)


@bp.route("/watch/refresh", methods=["POST"])
def watch_refresh():
    db_file = app_db()
    cache = _bond_cache()
    remaining = cache.cooldown_remaining()
    if remaining > 0:
        return (
            jsonify(
                {
                    "trigger": "manual",
                    "status": "cooldown",
                    "remaining": round(remaining, 1),
                    "message": f"Refresh blocked - {remaining:.0f}s cooldown remaining",
                }
            ),
            429,
        )
    from src.bond_master import service as bond_service

    summary = bond_service.refresh_all(
        db_file,
        trigger="manual",
        transport=current_app.config.get(BOND_MASTER_TRANSPORT_KEY),
    )
    return jsonify(
        {
            "trigger": "manual",
            "status": "refreshed",
            "summary": summary,
            "message": "Bond master refresh finished",
        }
    )


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
