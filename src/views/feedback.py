import json
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.mailer import send_message
from src.prefs import get_pref, set_pref
from src.validators import AppError
from src.views.common import APP_VERSION, app_db

bp = Blueprint("feedback", __name__)

TYPES = ("bug", "feature", "question")
SEVERITIES = ("blocking", "major", "minor")
OUTBOX_KEY = "feedback_outbox"

REQUIRED_FIELDS = {
    "bug": (
        ("title", "Title"),
        ("what_happened", "What happened?"),
        ("steps", "Steps to reproduce"),
        ("expected_actual", "Expected vs actual"),
    ),
    "feature": (
        ("title", "Title"),
        ("problem", "Problem it solves"),
        ("solution", "Proposed solution"),
    ),
    "question": (
        ("title", "Title"),
        ("question", "Your question"),
    ),
}


def feedback_type(raw):
    key = str(raw or "").strip().lower()
    return key if key in TYPES else "bug"


def outbox(db_file):
    with get_conn(db_file) as conn:
        raw = get_pref(conn, OUTBOX_KEY)
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return parsed if isinstance(parsed, list) else []


def save_outbox(db_file, items):
    with get_conn(db_file) as conn:
        set_pref(conn, OUTBOX_KEY, json.dumps(items))
    return len(items)


def queue_feedback(db_file, item):
    items = outbox(db_file)
    items.append(item)
    return save_outbox(db_file, items)


def collect_fields(form, kind):
    values = {}
    for name, label in REQUIRED_FIELDS[kind]:
        text = str(form.get(name, "")).strip()
        if not text:
            raise AppError("ERR-feedback", f"{label} is required")
        values[name] = text
    if kind == "bug":
        severity = str(form.get("severity", "")).strip()
        if severity not in SEVERITIES:
            raise AppError(
                "ERR-feedback",
                f"severity must be one of {', '.join(SEVERITIES)}",
            )
        values["severity"] = severity
    return values


def context_from_request(req):
    page = str(req.form.get("context_page") or req.args.get("from") or "").strip()
    if not page and req.referrer:
        tail = req.referrer.split("//", 1)[-1]
        page = "/" + tail.split("/", 1)[-1] if "/" in tail else "/"
    device = str(getattr(req.user_agent, "string", "") or "unknown")[:120]
    return {"version": APP_VERSION, "page": page or "direct", "device": device}


def message_body(kind, values, context):
    lines = [f"Type: {kind}"]
    for name, label in REQUIRED_FIELDS[kind]:
        lines.append(f"{label}: {values.get(name, '')}")
    if kind == "bug":
        lines.append(f"Severity / blocking: {values.get('severity', '')}")
    lines.append(f"App version: {context['version']}")
    lines.append(f"Page: {context['page']}")
    lines.append(f"Device: {context['device']}")
    return "\n".join(lines)


def render_form(db_file, kind, **extra):
    context = {
        "kind": kind,
        "types": TYPES,
        "required_fields": REQUIRED_FIELDS[kind],
        "severities": SEVERITIES,
        "app_version": APP_VERSION,
        "pending": len(outbox(db_file)),
        "sent": False,
        "error": None,
        "error_code": None,
        "route_taken": None,
        "outbox_saved": False,
        "github_title": None,
        "github_body": None,
        "github_label": None,
    }
    context.update(extra)
    return render_template("feedback.html", **context)


@bp.route("/feedback", methods=["GET", "POST"])
def feedback_page():
    db_file = app_db()
    kind = feedback_type(request.values.get("type"))
    context = context_from_request(request)
    if request.method == "GET":
        return render_form(db_file, kind, context=context)
    try:
        values = collect_fields(request.form, kind)
    except AppError as exc:
        return (
            render_form(
                db_file,
                kind,
                context=context,
                error=exc.message,
                error_code=exc.code,
            ),
            400,
        )
    title = values.get("title", f"{kind} report")
    body = message_body(kind, values, context)
    route = str(request.form.get("route") or "email").strip().lower()
    if route == "github":
        return render_form(
            db_file,
            kind,
            context=context,
            sent=True,
            route_taken="github",
            github_title=title,
            github_body=body,
            github_label=kind,
        )
    item = {
        "type": kind,
        "title": title,
        "subject": f"[{kind}] DK Bond Tracker feedback: {title}",
        "body": body,
        "created_at": date.today().isoformat(),
        "context": context,
    }
    try:
        attachment = None
        upload = request.files.get("screenshot")
        if upload is not None and upload.filename:
            payload = upload.read()
            if payload:
                attachment = (
                    upload.filename,
                    upload.mimetype or "application/octet-stream",
                    payload,
                )
        send_message(item["subject"], body, attachment)
    except AppError as exc:
        pending = queue_feedback(db_file, item)
        return render_form(
            db_file,
            kind,
            context=context,
            sent=True,
            route_taken="outbox",
            outbox_saved=True,
            pending=pending,
            error=exc.message,
            error_code=exc.code,
        )
    flash("Thanks — your report is in.", "success")
    return render_form(db_file, kind, context=context, sent=True, route_taken="email")


@bp.route("/feedback/retry", methods=["POST"])
def feedback_retry():
    db_file = app_db()
    items = outbox(db_file)
    remaining = []
    sent = 0
    for item in items:
        try:
            send_message(item.get("subject"), item.get("body"))
        except AppError:
            remaining.append(item)
        else:
            sent += 1
    save_outbox(db_file, remaining)
    flash(
        f"Outbox retry: {sent} sent, {len(remaining)} still waiting",
        "success" if sent else "warn",
    )
    return redirect(url_for("feedback.feedback_page"))
