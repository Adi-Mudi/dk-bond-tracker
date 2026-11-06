from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.notifications import list_notifications, mark_all_read
from src.prefs import set_pref
from src.views.common import app_db

bp = Blueprint("notifications", __name__)


def alert_prefs_map(db_file):
    with get_conn(db_file) as conn:
        rows = conn.execute("SELECT key, value FROM alert_prefs").fetchall()
    return {row["key"]: row["value"] for row in rows}


@bp.route("/notifications", methods=["GET", "POST"])
def notifications_page():
    db_file = app_db()
    if request.method == "POST":
        inapp_on = request.form.get("inapp") in ("on", "1", "true", "yes")
        email_on = request.form.get("email") in ("on", "1", "true", "yes")
        with get_conn(db_file) as conn:
            set_pref(conn, "alert_channel_inapp", "1" if inapp_on else "0")
            set_pref(conn, "alert_channel_email", "1" if email_on else "0")
        flash("Alert channels saved", "success")
        return redirect(url_for("notifications.notifications_page"))
    with get_conn(db_file) as conn:
        feed = list_notifications(conn, limit=50)
    severity_rank = {
        "danger": 0,
        "due_today": 1,
        "reminder": 2,
        "maturity_soon": 3,
        "warn": 4,
        "info": 5,
    }
    feed.sort(
        key=lambda item: (item.get("created_at") or "", item.get("id") or 0),
        reverse=True,
    )
    feed.sort(
        key=lambda item: severity_rank.get(item.get("severity"), 99)
    )
    return render_template(
        "notifications.html", prefs=alert_prefs_map(db_file), feed=feed
    )


@bp.route("/notifications/read_all", methods=["POST"])
def notifications_read_all():
    db_file = app_db()
    with get_conn(db_file) as conn:
        mark_all_read(conn)
    return redirect(url_for("notifications.notifications_page"))
