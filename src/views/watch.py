import json
import math
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
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    INSTRUMENT_FIELDS,
    POSITION_FIELDS,
    SOURCE_PRIORITY,
    FetchResult,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.normalize import is_investment_grade
from src.bond_master.snapshot import SNAPSHOT_SOURCE
from src.bond_master.service import build_default_service, primary_source, unmark_isin_deleted
from src.db import get_conn
from src.engine import tenure_window
from src.forms import FACT_BY_FIELD, fetched_form_values
from src.lock import check_add_allowed
from src.maturity import months_remaining
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
APPLIED_ISIN_SESSION_KEY = "watch_applied_isin"
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
    "maturity_date",
    "listing_status",
)

WATCH_LISTING_STATUSES = ("listed", "unlisted", "unknown")

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
ONLINE_FACT_FIELDS = (
    "company",
    "coupon",
    "maturity",
    "rating",
    "rating_agency",
    "issuer_type",
    "payout_cycle",
    "secured",
)
SNAPSHOT_FACT_FIELDS = ("company", "coupon", "maturity")
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
        "popup_facts": {},
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


def rating_gate(payload, manual_rating=""):
    if not payload:
        return None
    facts = payload.get("facts") or {}
    if not facts:
        return None
    fetched = str(facts.get("rating") or "").strip()
    manual = str(manual_rating or "").strip()
    effective = manual or fetched
    if not effective:
        return RATING_GATE_MESSAGE
    if fetched and not is_investment_grade(fetched):
        return RATING_GATE_MESSAGE
    return None


def autofetch_refusal(isin, manual_rating=""):
    stored = session.get(AUTOFETCH_SESSION_KEY) or {}
    if stored.get("isin") != isin:
        return None
    return rating_gate(stored.get("payload"), manual_rating)


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
    if state in (FETCH_FOUND, FETCH_DOWNGRADE, FETCH_OFFLINE) and cached_row:
        cached = {
            field: cached_row[field]
            for field in INSTRUMENT_FIELDS
            if cached_row.get(field) is not None
        }
    if state == FETCH_OFFLINE and cached_row:
        asof = str(cached_row.get("fetched_at") or "")
        facts = {field: cached[field] for field in SNAPSHOT_FACT_FIELDS if field in cached}
        sources = {field: cached_row.get("source") or SNAPSHOT_SOURCE for field in facts}
    failure_code = result.failure_code if result is not None else None
    official = any(source != SNAPSHOT_SOURCE for source in sources.values())
    popup_fields = ONLINE_FACT_FIELDS if official else SNAPSHOT_FACT_FIELDS
    tier = ("official" if official else "snapshot") if sources else ""
    return {
        "state": state,
        "states": FETCH_STATES,
        "labels": FETCH_STATE_LABELS,
        "isin": result.isin if result is not None else "",
        "facts": facts,
        "popup_facts": {field: value for field, value in facts.items() if field in popup_fields},
        "tier": tier,
        "sources": sources,
        "source_names": _source_names(sources),
        "cached": cached,
        "asof": asof,
        "message": fetch_message(state, failure_code),
        "failure_code": failure_code,
        "values": {},
        "sources_by_field": {},
    }


def refresh_failure_code(summary):
    codes = {entry.get("failure_code") for entry in (summary or {}).values()}
    codes.discard(None)
    if not codes or FAILURE_OK in codes:
        return None
    if codes <= set(OFFLINE_REACH_FAILURE_CODES):
        return FAILURE_OFFLINE
    if codes & set(OFFLINE_BLOCKED_FAILURE_CODES):
        return FAILURE_BLOCKED
    return None


def _single_known_isin(db_file):
    with get_conn(db_file) as conn:
        rows = conn.execute(
            "SELECT isin FROM bond_master WHERE isin IS NOT NULL "
            "UNION SELECT isin FROM bonds WHERE isin IS NOT NULL"
        ).fetchall()
    isins = sorted(
        {
            str(row["isin"]).strip().upper()
            for row in rows
            if str(row["isin"] or "").strip()
        }
    )
    return isins[0] if len(isins) == 1 else ""


def refresh_target_isin(db_file, requested):
    candidate = str(requested or "").strip().upper()
    if candidate and ISIN_PATTERN.match(candidate):
        return candidate
    stored = session.get(AUTOFETCH_SESSION_KEY) or {}
    viewed = str(stored.get("isin") or "").strip().upper()
    if viewed and ISIN_PATTERN.match(viewed):
        return viewed
    return _single_known_isin(db_file)


def refresh_fetch_payload(isin, failure_code):
    row = _bond_cache().lookup(isin)
    payload = fetch_payload(
        FetchResult(isin=isin, failure_code=failure_code), cached_row=row
    )
    if row is None:
        return payload
    facts = {
        field: row.get(field)
        for field in INSTRUMENT_FIELDS
        if row.get(field) is not None
    }
    source = row.get("source") or SNAPSHOT_SOURCE
    official = source != SNAPSHOT_SOURCE
    popup_fields = ONLINE_FACT_FIELDS if official else SNAPSHOT_FACT_FIELDS
    payload["facts"] = facts
    payload["popup_facts"] = {
        field: facts[field] for field in popup_fields if field in facts
    }
    payload["sources"] = {field: source for field in facts}
    payload["source_names"] = _source_names(payload["sources"])
    payload["tier"] = "official" if official else "snapshot"
    return payload


def dirty_fields(raw):
    return {part.strip() for part in str(raw or "").split(",") if part.strip()}


def apply_fetch(current, payload, dirty):
    values = {}
    sources_by_field = {}
    fetched = fetched_form_values(payload.get("facts") or {})
    sources = payload.get("sources") or {}
    cached = payload.get("cached") or {}
    if cached:
        if cached.get("maturity") is not None:
            fetched["maturity_date"] = str(cached["maturity"])
        if cached.get("listing_status"):
            fetched["listing_status"] = cached["listing_status"]
    facts = payload.get("facts") or {}
    if facts.get("maturity") is not None:
        fetched.setdefault("maturity_date", str(facts["maturity"]))
    if facts.get("listing_status"):
        fetched.setdefault("listing_status", facts["listing_status"])
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
        before = _bond_cache().lookup(isin)
        result = service.lookup(isin)
        events = [event for event in service.events() if event.isin == isin]
        cached_row = _bond_cache().lookup(isin)
        local_stamp = None
        if before is not None and result.has_facts() and all(
            getattr(result, field) == before.get(field) for field in INSTRUMENT_FIELDS
        ):
            local_stamp = before.get("fetched_at")
        payload = fetch_payload(result, events, cached_row=cached_row, fetched_at=local_stamp)
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
    remaining = _bond_cache().cooldown_remaining()
    payload["countdown_seconds"] = math.ceil(remaining) if remaining > 0 else 60
    payload["countdown_active"] = bool(
        payload.get("failure_code") == FAILURE_RATE_LIMITED and remaining > 0
    )
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


INLINE_ERROR_FIELDS = (
    "isin",
    "company",
    "rating",
    "coupon",
    "yield",
    "issuer_type",
    "face_value",
    "maturity_date",
    "listing_status",
    "payout_cycle",
)


def error_field(code, message):
    text = str(message or "").lower()
    if code == "ERR-watch-rating-gate":
        return "rating"
    if code == "ERR-watch-dup":
        return "isin"
    for field in (
        "isin",
        "company",
        "rating",
        "coupon",
        "yield",
        "amount",
        "purchase_date",
        "maturity_date",
        "qty",
        "face_value",
        "issuer_type",
        "listing_status",
        "payout_cycle",
        "watch_investment",
    ):
        if field in text:
            return field
    return None


def watch_context(
    db_file,
    form=None,
    error=None,
    error_code=None,
    form_open=False,
    duplicate=None,
    fetch=None,
    field_errors=None,
):
    field = error_field(error_code, error)
    if duplicate and duplicate.get("field"):
        field = duplicate["field"]
    errors = field_errors or {}
    other = {key: value for key, value in errors.items() if key not in INLINE_ERROR_FIELDS}
    return {
        "candidates": watch_candidates(db_file),
        "snapshot": watch_snapshot(db_file),
        "error": error,
        "error_code": error_code,
        "error_field": field,
        "field_errors": errors,
        "other_field_errors": other,
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
            "qty, watch_investment, maturity_date, listing_status "
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
    errors = {}

    def capture(field, action, default=None):
        try:
            return action()
        except AppError as exc:
            errors.setdefault(field, exc.message)
            return default

    company = str(form.get("company", "")).strip()
    if not company:
        errors.setdefault("company", "company is required")
    isin = str(form.get("isin", "")).strip()
    if not isin:
        errors.setdefault("isin", "ISIN is required")
    elif not ISIN_PATTERN.match(isin):
        errors.setdefault(
            "isin",
            f"ISIN format invalid: {isin!r} (expected 12 characters, e.g. INE9000A0101)",
        )
    rating = str(form.get("rating", "")).strip()
    if not rating:
        errors.setdefault("rating", "rating is required")
    elif rating not in WATCH_RATINGS:
        errors.setdefault(
            "rating",
            f"rating must be investment grade AAA to BBB-: {rating!r}",
        )
    coupon = capture("coupon", lambda: watch_percent(form.get("coupon_pct", ""), "coupon"))
    est_yield = capture(
        "yield",
        lambda: percent_value(
            form.get("expected_yield_pct", ""), "est yield", "ERR-watch-add", required=False
        ),
    )
    amount_raw = str(form.get("amount", "") or "").strip()
    amount = None
    if amount_raw:
        amount = capture(
            "amount",
            lambda: percent_value(amount_raw, "amount", "ERR-watch-add", required=False),
        )
        if amount is not None and amount <= 0:
            errors.setdefault("amount", f"amount must be greater than 0: {amount_raw!r}")
    purchase_raw = str(form.get("purchase_date", "") or "").strip()
    purchase_date = None
    if purchase_raw:
        purchase_date = capture(
            "purchase_date",
            lambda: parse_date_value(purchase_raw, "purchase_date"),
        )
    source_note = str(form.get("source_note", "")).strip()
    broker = str(form.get("broker", "")).strip() or None
    rating_agency = str(form.get("rating_agency", "")).strip() or None
    issuer_type = str(form.get("issuer_type", "")).strip() or None
    if issuer_type is not None and issuer_type not in WATCH_ISSUER_TYPES:
        errors.setdefault(
            "issuer_type",
            f"issuer_type must be one of corporate_bond, ncd, sdi, "
            f"government, fd: {issuer_type!r}",
        )
    maturity_raw = str(form.get("maturity_date", "")).strip()
    maturity_date = None
    if maturity_raw:
        maturity_date = capture(
            "maturity_date",
            lambda: parse_date_value(maturity_raw, "maturity_date").isoformat(),
        )
    listing_status = str(form.get("listing_status", "")).strip() or "unknown"
    if listing_status not in WATCH_LISTING_STATUSES:
        errors.setdefault(
            "listing_status",
            f"listing_status must be listed, unlisted or unknown: {listing_status!r}",
        )
    payout_cycle = str(form.get("payout_cycle", "")).strip() or None
    if payout_cycle is not None and payout_cycle not in WATCH_PAYOUT_CYCLES:
        errors.setdefault(
            "payout_cycle",
            f"payout_cycle must be monthly, quarterly or annual: {payout_cycle!r}",
        )
    secured = 1 if str(form.get("secured", "1")) == "1" else 0
    face_value = capture(
        "face_value",
        lambda: percent_value(form.get("face_value", ""), "face_value", "ERR-watch-add", required=False),
    )
    watch_investment = capture(
        "watch_investment",
        lambda: percent_value(form.get("watch_investment", ""), "watch_investment", "ERR-watch-add", required=False),
    )
    qty_raw = str(form.get("qty", "")).strip()
    qty = (
        capture("qty", lambda: validate_positive_int(qty_raw, "qty", "ERR-watch-add"))
        if qty_raw
        else None
    )
    if errors:
        error = AppError("ERR-watch-add", next(iter(errors.values())))
        error.field_errors = errors
        raise error
    return {
        "company": company,
        "isin": isin,
        "rating": rating,
        "source_note": source_note,
        "broker": broker,
        "coupon": coupon,
        "est_yield": est_yield,
        "amount": amount,
        "purchase_date": purchase_date.isoformat() if purchase_date else None,
        "rating_agency": rating_agency,
        "issuer_type": issuer_type,
        "payout_cycle": payout_cycle,
        "secured": secured,
        "face_value": face_value,
        "watch_investment": watch_investment,
        "qty": qty,
        "maturity_date": maturity_date,
        "listing_status": listing_status,
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
        "secured, face_value, payout_cycle, qty, watch_investment, "
        "maturity_date, listing_status, amount, purchase_date) "
        "VALUES (?, ?, ?, ?, ?, ?, 'watching', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
            values["maturity_date"],
            values["listing_status"],
            values["amount"],
            values["purchase_date"],
        ),
    )
    unmark_isin_deleted(conn, values["isin"])
    if cursor.rowcount != 1:
        raise AppError("ERR-watch-add", "candidate insert affected 0 rows")


@bp.route("/watch", methods=["GET", "POST"])
def watch_list():
    db_file = app_db()
    if request.method == "POST":
        form = request.form
        try:
            refusal = autofetch_refusal(
                str(form.get("isin", "")).strip().upper(),
                str(form.get("rating", "")).strip(),
            )
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
                        field_errors=getattr(exc, "field_errors", None),
                    ),
                ),
                409 if exc.code == "ERR-watch-dup" else 400,
            )
        flash(f"Candidate added: {values['company']}", "success")
        return redirect(url_for("watch.watch_list"))
    try:
        if request.args.get("isin"):
            form, fetch = autofetch_form(request.args)
            if fetch and fetch.get("isin") in (session.get(APPLIED_ISIN_SESSION_KEY) or []):
                fetch = dict(
                    fetch,
                    facts={},
                    popup_facts={},
                    sources={},
                    source_names=[],
                    values={},
                    sources_by_field={},
                )
            context = watch_context(
                db_file, form=form, form_open=True, fetch=fetch
            )
        else:
            context = watch_context(db_file)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Watchlist failed", 500)
    return render_template("watch.html", **context)


@bp.route("/watch/lookup", methods=["GET"])
def watch_lookup():
    current = request.args
    isin = str(current.get("isin", "") or "").strip().upper()
    if not isin or not ISIN_PATTERN.match(isin):
        return jsonify({"error": "ERR-watch-lookup", "message": "enter a valid ISIN"}), 400
    try:
        _, payload = autofetch_form({"isin": isin, "dirty": current.get("dirty", "")})
    except AppError as exc:
        return jsonify({"error": exc.code, "message": exc.message}), 500
    return jsonify(payload)


@bp.route("/watch/months", methods=["GET"])
def watch_months():
    purchase = str(request.args.get("purchase", "") or "").strip()
    maturity = str(request.args.get("maturity", "") or "").strip()
    cycle = str(request.args.get("cycle", "") or "").strip()
    if not purchase:
        purchase = date.today().isoformat()
    return jsonify({"months_remaining": months_remaining(purchase, maturity or None, cycle)})


@bp.route("/watch/lookup/applied", methods=["POST"])
def watch_lookup_applied():
    isin = str(request.form.get("isin", "") or "").strip().upper()
    if not isin or not ISIN_PATTERN.match(isin):
        return jsonify({"error": "ERR-watch-lookup", "message": "enter a valid ISIN"}), 400
    applied = list(session.get(APPLIED_ISIN_SESSION_KEY) or [])
    if isin not in applied:
        applied.append(isin)
    session[APPLIED_ISIN_SESSION_KEY] = applied
    return jsonify({"status": "ok", "isin": isin})


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
    payload = {
        "trigger": "manual",
        "status": "refreshed",
        "summary": summary,
        "message": "Bond master refresh finished",
    }
    isin = refresh_target_isin(db_file, request.values.get("isin"))
    failure_code = refresh_failure_code(summary)
    if isin and failure_code is not None:
        payload["fetch"] = refresh_fetch_payload(isin, failure_code)
        payload["message"] = payload["fetch"]["message"]
    return jsonify(payload)


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
        purchase_date = parse_date_value(form.get("purchase_date", ""), "purchase_date")
        start_raw = str(form.get("start_date", "") or "").strip() or purchase_date.isoformat()
        quantity = validate_positive_int(form.get("qty", ""), "qty", "ERR-move-watching")
        invested = percent_value(form.get("amount", ""), "amount", "ERR-move-watching")
        if invested <= 0:
            raise AppError(
                "ERR-move-watching",
                f"amount must be greater than 0: {form.get('amount', '')!r}",
            )
        broker = str(form.get("broker", "")).strip() or None
        goal_raw = str(form.get("goal_id", "") or "").strip()
        with get_conn(db_file) as conn:
            row = conn.execute(
                "SELECT id, company, isin, watch_state, maturity_date, listing_status "
                "FROM bonds WHERE id = ?",
                (candidate_id,),
            ).fetchone()
            if row is None:
                raise AppError("ERR-move-watching", f"candidate not found: {candidate_id}")
            if row["watch_state"] != "watching":
                raise AppError(
                    "ERR-move-watching",
                    f"already in Portfolio: {row['company']} is {row['watch_state']}",
                )
            end_raw = str(form.get("end_date", "") or "").strip() or str(row["maturity_date"] or "").strip()
            start_date, end_date, tenure_months, credit_day = date_range_tenure(
                start_raw, end_raw, credit_value
            )
            if tenure_months < 1:
                raise AppError(
                    "ERR-date-range",
                    f"tenure must span at least one whole month: {tenure_months}",
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
            maturity_date = row["maturity_date"]
            listing_status = row["listing_status"] or "unknown"
            cursor = conn.execute(
                "UPDATE bonds SET start_date = ?, end_date = ?, tenure_months = ?, "
                "credit_day = ?, amount = ?, qty = ?, broker = ?, purchase_date = ?, "
                "goal_id = ?, watch_state = 'holding', maturity_date = ?, listing_status = ? "
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
                    maturity_date,
                    listing_status,
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
