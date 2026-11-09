from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.prefs import get_pref, set_pref
from src.views.common import APP_VERSION, BUILD_NOTES, app_db

bp = Blueprint("about", __name__)


@bp.route("/about", methods=["GET", "POST"])
def about_page():
    db_file = app_db()
    if request.method == "POST":
        action = str(request.form.get("action") or "").strip()
        with get_conn(db_file) as conn:
            if action == "check":
                set_pref(conn, "update_last_checked", date.today().isoformat())
                flash(
                    f"Update check done — you are on v{APP_VERSION}, the newest version we know of.",
                    "success",
                )
            elif action == "auto":
                enabled = request.form.get("auto") in ("on", "1", "true", "yes")
                set_pref(conn, "update_auto_check", "1" if enabled else "0")
                flash(
                    "Automatic update checks " + ("enabled" if enabled else "disabled"),
                    "success",
                )
        return redirect(url_for("about.about_page"))
    with get_conn(db_file) as conn:
        last_checked = get_pref(conn, "update_last_checked")
        auto_check = get_pref(conn, "update_auto_check", "1") == "1"
    return render_template(
        "about.html",
        app_version=APP_VERSION,
        build_notes=BUILD_NOTES,
        last_checked=last_checked,
        auto_check=auto_check,
    )
