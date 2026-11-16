from flask import Blueprint, flash, redirect, render_template, request, url_for

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
        "key": "rbi",
        "name": "RBI",
        "detail": "Outstanding Government Securities, State Development Loans and T-Bills.",
        "license": "Published download files - RBI disclaimer applies.",
        "url": "",
    },
    {
        "key": "nse",
        "name": "NSE",
        "detail": "Debt security master.",
        "license": "Published download files only - the NSE Terms of Use ban automated site or API collection.",
        "url": "",
    },
    {
        "key": "bse",
        "name": "BSE",
        "detail": "Debt segment security master.",
        "license": "Published download files - BSE disclaimer applies.",
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


@bp.route("/update/dismiss", methods=["POST"])
def dismiss_update_popup():
    version = str(request.form.get("version") or "").strip()
    with get_conn(app_db()) as conn:
        set_pref(conn, "update_dismissed_session", version)
    return ("", 204)


@bp.route("/about", methods=["GET", "POST"])
def about_page():
    db_file = app_db()
    banner = None
    if request.method == "POST":
        action = str(request.form.get("action") or "").strip()
        if action == "check":
            result = check_for_updates(force=True)
            with get_conn(db_file) as conn:
                store_update_result(conn, result)
            banner = {
                "status": result["status"],
                "version": result.get("version"),
                "url": result.get("url"),
            }
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
