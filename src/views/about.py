from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for

from src.bond_master import snapshot
from src.db import get_conn
from src.prefs import get_pref, set_pref
from src.updater import check_for_updates, store_update_result
from src.views.common import APP_VERSION, BUILD_NOTES, app_db

bp = Blueprint("about", __name__)

DATA_SOURCES = (
    {
        "key": "nsdl",
        "name": "NSDL",
        "detail": "Corporate bond master and the detailed ISIN search (primary source).",
        "license": "Published download files - terms of use apply, no automated scraping.",
        "url": "",
    },
    {
        "key": "india-isin-data",
        "name": snapshot.SNAPSHOT_NAME,
        "detail": "Bundled offline ISIN snapshot that seeds a fresh install.",
        "license": "CC0 1.0 (public domain).",
        "url": snapshot.url(),
    },
)


def _banner_from_prefs(conn, checked):
    if checked not in ("newer", "current", "offline", "error"):
        return None
    if checked == "newer":
        return {
            "status": "newer",
            "version": get_pref(conn, "update_version", ""),
            "url": get_pref(conn, "update_url", "") or None,
        }
    if checked == "current":
        return {
            "status": "current",
            "version": APP_VERSION,
            "url": None,
            "local_ahead": get_pref(conn, "update_local_ahead", "0") == "1",
        }
    return {"status": checked, "version": None, "url": None}


@bp.route("/update/dismiss", methods=["POST"])
def dismiss_update_popup():
    current_app.config["UPDATE_POPUP_DISMISSED"] = True
    return ("", 204)


@bp.route("/about", methods=["GET", "POST"])
def about_page():
    db_file = app_db()
    banner = None
    checked = request.args.get("checked")
    if request.method == "POST":
        action = str(request.form.get("action") or "").strip()
        if action == "check":
            result = check_for_updates()
            with get_conn(db_file) as conn:
                store_update_result(conn, result)
            banner = {
                "status": result["status"],
                "version": result.get("version"),
                "url": result.get("url"),
                "local_ahead": bool(result.get("local_ahead")),
            }
            if result["status"] == "newer":
                current_app.config["UPDATE_POPUP_DISMISSED"] = False
            return redirect(url_for("about.about_page", checked=result["status"]))
        elif action == "auto":
            enabled = request.form.get("auto") in ("on", "1", "true", "yes")
            with get_conn(db_file) as conn:
                set_pref(conn, "update_auto_check", "1" if enabled else "0")
            flash(
                "Automatic update checks " + ("enabled" if enabled else "disabled"),
                "success",
            )
            return redirect(url_for("about.about_page"))
        else:
            return redirect(url_for("about.about_page"))
    with get_conn(db_file) as conn:
        last_checked = get_pref(conn, "update_last_checked")
        auto_check = get_pref(conn, "update_auto_check", "1") == "1"
        if checked:
            banner = _banner_from_prefs(conn, checked)
    return render_template(
        "about.html",
        app_version=APP_VERSION,
        build_notes=BUILD_NOTES,
        last_checked=last_checked,
        auto_check=auto_check,
        update_banner=banner,
        data_dir=str(db_file.parent),
        data_sources=DATA_SOURCES,
        snapshot_version=snapshot.version(),
        snapshot_rows=len(snapshot.rows()),
    )
