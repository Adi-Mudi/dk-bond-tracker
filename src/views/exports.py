from datetime import date

from flask import Blueprint, Response, render_template, request

from src.db import get_conn
from src.export_csv import (
    LEDGER_HEADERS,
    current_view_csv,
    current_view_rows,
    full_ledger_csv,
)
from src.print import monthly_print_model
from src.queries import MONTH_PATTERN
from src.share import SECTION_KEYS, build_share_snapshot, share_csv
from src.status import month_key
from src.validators import AppError
from src.views.common import app_db, error_page

bp = Blueprint("exports", __name__)


def generate_share():
    db_file = app_db()
    selected = request.form.getlist("sections")
    sections = {key: key in selected for key in SECTION_KEYS}
    include_amounts = request.form.get("include_amounts") in ("on", "1", "true", "yes")
    privacy_on = request.form.get("privacy") in ("on", "1", "true", "yes")
    fmt = request.form.get("format", "html")
    if fmt not in ("html", "csv"):
        return error_page(
            "ERR-share-export",
            f"unsupported share format: {fmt!r} (expected 'html' or 'csv')",
            "Share snapshot failed",
            400,
        )
    try:
        with get_conn(db_file) as conn:
            if fmt == "csv":
                text = share_csv(conn, sections, include_amounts, privacy_on)
                filename = "share_snapshot.csv"
            else:
                text = build_share_snapshot(
                    conn, sections, include_amounts, privacy_on
                )
                filename = "share_snapshot.html"
    except AppError as exc:
        return error_page(exc.code, exc.message, "Share snapshot failed", 400)
    mimetype = "text/csv" if fmt == "csv" else "text/html"
    response = Response(text, mimetype=mimetype)
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@bp.route("/export.csv")
def export_csv_route():
    scope = request.args.get("scope", "")
    db_file = app_db()
    if scope == "full":
        try:
            with get_conn(db_file) as conn:
                text = full_ledger_csv(conn)
        except AppError as exc:
            return error_page(exc.code, exc.message, "CSV export failed", 500)
        filename = "full_ledger.csv"
    elif scope == "current":
        month = str(request.args.get("month", "")).strip()
        if month and not MONTH_PATTERN.match(month):
            return error_page(
                "ERR-export-view",
                f"unparseable month (expected YYYY-MM): {month!r}",
                "CSV export failed",
                400,
            )
        try:
            with get_conn(db_file) as conn:
                if not month:
                    row = conn.execute(
                        "SELECT MAX(month) AS latest FROM payment_ledger"
                    ).fetchone()
                    month = row["latest"] if row and row["latest"] else month_key(date.today())
                rows = current_view_rows(conn, month, date.today())
                text = current_view_csv(rows, headers=list(LEDGER_HEADERS))
        except AppError as exc:
            status = 400 if exc.code == "ERR-export-view" else 500
            return error_page(exc.code, exc.message, "CSV export failed", status)
        filename = f"view_{month}.csv"
    else:
        return error_page(
            "ERR-export-view",
            f"unknown export scope: {scope!r} (expected 'current' or 'full')",
            "CSV export failed",
            400,
        )
    response = Response(text, mimetype="text/csv")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@bp.route("/share", methods=["GET", "POST"])
def share_page():
    if request.method == "GET":
        return render_template("share.html")
    return generate_share()


@bp.route("/share/generate", methods=["POST"])
def share_generate():
    return generate_share()


@bp.route("/print")
def print_statement():
    db_file = app_db()
    privacy = str(request.args.get("privacy", "")).lower() in ("1", "on", "true", "yes")
    try:
        with get_conn(db_file) as conn:
            model = monthly_print_model(conn, date.today())
    except AppError as exc:
        return error_page(exc.code, exc.message, "Monthly print failed", 500)
    return render_template("monthly_print.html", privacy=privacy, **model)
