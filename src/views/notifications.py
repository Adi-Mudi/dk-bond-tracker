from datetime import date, datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.notifications import list_notifications, mark_all_read
from src.prefs import get_pref, set_pref
from src.views.common import app_db

bp = Blueprint("notifications", __name__)

SEVERITY_RANK = {
    "danger": 0,
    "due_today": 1,
    "reminder": 2,
    "maturity_soon": 3,
    "warn": 4,
    "info": 5,
}
FILTERS = ("all", "due", "overdue", "maturity")
FILTER_SEVERITIES = {
    "due": ("due_today", "reminder"),
    "overdue": ("danger",),
    "maturity": ("maturity_soon",),
}
BATCHABLE = ("danger", "due_today", "reminder", "maturity_soon")
BATCH_LABELS = {
    "danger": "positions overdue",
    "due_today": "payouts due today",
    "reminder": "payouts due",
    "maturity_soon": "maturities ahead",
}
GROUP_ORDER = ("Today", "This week", "Older")
CLEARED_KEY = "alerts_cleared_through"
HELD_LINK = "/portfolio?tab=holdings"
FILTER_LABELS = (("all", "All"), ("due", "Due"), ("overdue", "Overdue"), ("maturity", "Maturity"))


def held_links(conn):
    rows = conn.execute(
        "SELECT id, company FROM bonds WHERE watch_state = 'holding' ORDER BY id"
    ).fetchall()
    links = {}
    for row in rows:
        key = (row["company"] or "").strip().lower()
        if key and key not in links:
            links[key] = row["id"]
    return sorted(links.items(), key=lambda entry: len(entry[0]), reverse=True)


def item_link(message, links):
    text = (message or "").strip().lower()
    for company, bond_id in links:
        if text.startswith(company):
            return f"/portfolio/{bond_id}"
    return HELD_LINK


def feed_group(created_at, today):
    raw = (created_at or "").strip()
    try:
        stamp = datetime.fromisoformat(raw).replace(tzinfo=timezone.utc)
        created = stamp.astimezone().date()
    except ValueError:
        return "Older"
    days = (today - created).days
    if days <= 0:
        return "Today"
    if days < 7:
        return "This week"
    return "Older"


def cleared_through(db_file):
    with get_conn(db_file) as conn:
        raw = get_pref(conn, CLEARED_KEY, "0")
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 0


def feed_items(conn, today, links, watermark):
    items = []
    for row in list_notifications(conn, limit=200):
        if int(row.get("read") or 0) == 1 and int(row.get("id") or 0) <= watermark:
            continue
        items.append(
            {
                "id": row.get("id"),
                "severity": row.get("severity") or "info",
                "message": row.get("message") or "",
                "read": int(row.get("read") or 0),
                "timestamp": (row.get("created_at") or "")[:19],
                "group": feed_group(row.get("created_at"), today),
                "link": item_link(row.get("message"), links),
            }
        )
    items.sort(key=lambda item: (item["timestamp"], item["id"] or 0), reverse=True)
    items.sort(key=lambda item: SEVERITY_RANK.get(item["severity"], 99))
    return items


def batch_groups(items):
    groups = []
    for name in GROUP_ORDER:
        members = [item for item in items if item["group"] == name]
        if not members:
            continue
        rows = []
        index = 0
        while index < len(members):
            head = members[index]
            run = [head]
            while (
                index + len(run) < len(members)
                and members[index + len(run)]["severity"] == head["severity"]
            ):
                run.append(members[index + len(run)])
            if len(run) >= 2 and head["severity"] in BATCHABLE:
                rows.append(
                    {
                        "batch": True,
                        "severity": head["severity"],
                        "count": len(run),
                        "label": BATCH_LABELS.get(head["severity"], "alerts"),
                        "messages": [entry["message"] for entry in run],
                        "read": 0 if any(entry["read"] == 0 for entry in run) else 1,
                        "link": head["link"],
                        "timestamp": head["timestamp"],
                    }
                )
            else:
                for entry in run:
                    entry["batch"] = False
                    rows.append(entry)
            index += len(run)
        groups.append({"name": name, "rows": rows})
    return groups


@bp.route("/notifications", methods=["GET"])
def notifications_page():
    db_file = app_db()
    today = date.today()
    active = str(request.args.get("filter") or "all")
    if active not in FILTERS:
        active = "all"
    with get_conn(db_file) as conn:
        links = held_links(conn)
        items = feed_items(conn, today, links, cleared_through(db_file))
    counts = {"all": len(items)}
    for key, severities in FILTER_SEVERITIES.items():
        counts[key] = sum(1 for item in items if item["severity"] in severities)
    if active != "all":
        wanted = FILTER_SEVERITIES[active]
        items = [item for item in items if item["severity"] in wanted]
    return render_template(
        "notifications.html",
        groups=batch_groups(items),
        counts=counts,
        active_filter=active,
        filter_labels=FILTER_LABELS,
        total=len(items),
    )


@bp.route("/notifications/read_all", methods=["POST"])
def notifications_read_all():
    db_file = app_db()
    with get_conn(db_file) as conn:
        mark_all_read(conn)
    flash("All alerts marked read", "success")
    return redirect(url_for("notifications.notifications_page"))


@bp.route("/notifications/clear", methods=["POST"])
def notifications_clear():
    db_file = app_db()
    with get_conn(db_file) as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(id), 0) AS n FROM notifications WHERE read = 1"
        ).fetchone()
        set_pref(conn, CLEARED_KEY, str(int(row["n"])))
    flash("Read alerts cleared", "success")
    return redirect(url_for("notifications.notifications_page"))
