from datetime import date

from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for

from src.db import get_conn
from src.engine import (
    derive_health,
    display_label,
    entry_paid,
    list_months_through_current,
    month_due_passed,
    purchase_date_label,
    purchase_qty_value,
    row_health_state,
    sort_rows,
    tenure_window,
)
from src.ledger import ledger_by_bond
from src.phase4 import payment_cycle_of, payout_schedule
from src.queries import month_label, position_detail, received_by_bond
from src.queries.summary import bond_master_provenance_map
from src.status import month_key
from src.validators import AppError, parse_date_value, safe_float
from src.views.common import app_db, error_page

bp = Blueprint("portfolio", __name__)


def row_valid(row):
    try:
        start = parse_date_value(row["start_date"], "start_date")
        end = parse_date_value(row["end_date"], "end_date")
    except AppError:
        return False
    if end <= start:
        return False
    tenure = row["tenure_months"]
    if isinstance(tenure, bool) or not isinstance(tenure, int) or tenure < 1:
        return False
    if "amount" in row.keys():
        try:
            float(row["amount"] or 0.0)
        except (TypeError, ValueError):
            return False
    return True


def portfolio_holdings(conn, bond_rows, ledger_by_bond, today):
    received_by_bond_map = received_by_bond(conn)
    provenance = bond_master_provenance_map(conn, [row["isin"] for row in bond_rows])
    holdings = []
    for row in bond_rows:
        entries = ledger_by_bond.get(row["id"], {})
        invested, health, next_payout, bad_amount = row_health_state(row, entries, today, "—")
        holdings.append(
            {
                "id": row["id"],
                "company": row["company"],
                "isin": row["isin"] or "",
                "rating": row["rating"],
                "coupon": row["coupon_pct"],
                "coupon_pct": row["coupon_pct"],
                "yield_pct": row["expected_yield_pct"],
                "expected_yield_pct": row["expected_yield_pct"],
                "frequency": row["payout_cycle"],
                "payout_cycle": row["payout_cycle"],
                "rating_agency": row["rating_agency"],
                "issuer_type": row["issuer_type"],
                "secured": row["secured"],
                "face_value": row["face_value"],
                "broker": row["broker"],
                "source_note": row["name"],
                "invested": invested,
                "received": received_by_bond_map.get(row["id"], 0.0),
                "next_payout": next_payout,
                "health": health,
                "purchase_date": purchase_date_label(row["purchase_date"]),
                "qty": purchase_qty_value(row["qty"]),
                "provenance": provenance.get(row["isin"]),
            }
        )
    return sort_rows(holdings)


def payout_prepare(bond_rows, ledger_by_bond, today):
    prepared = []
    first_keys = []
    for row in bond_rows:
        entries = ledger_by_bond.get(row["id"], {})
        try:
            float(row["amount"] or 0.0)
        except (TypeError, ValueError):
            prepared.append((row, [], entries, "Invalid", True))
            continue
        try:
            window = tenure_window(row["start_date"], row["tenure_months"])
            first_keys.append(window[0])
            prepared.append(
                (row, window, entries, display_label(derive_health(row, entries, today)), False)
            )
        except AppError:
            prepared.append((row, [], entries, "Invalid", True))
    return prepared, first_keys


def payout_months(today, first_keys):
    current_key = month_key(today)
    months = [
        key
        for key in list_months_through_current(today, min(first_keys) if first_keys else None)
        if key <= current_key
    ]
    months.reverse()
    return months


def payout_invalid_cells(months):
    cells = []
    for index, key in enumerate(months):
        if index == 0:
            cells.append({"kind": "chip", "month": key, "text": "Invalid", "chip": "chip-invalid"})
        else:
            cells.append({"kind": "text", "month": key, "text": "—"})
    return cells


def payout_cell(key, window_set, entry, health, credit_day, today):
    if health == "Matured":
        return {"kind": "matured"}
    if key not in window_set:
        return {"kind": "text", "month": key, "text": "—"}
    tds_applied = bool(entry.get("tds_applied", True)) if entry is not None else True
    if entry_paid(entry):
        return {
            "kind": "received",
            "month": key,
            "amount": safe_float(entry["amount"]),
            "tds_applied": tds_applied,
        }
    amount_value = 0.0
    if entry is not None:
        amount_value = safe_float(entry["amount"])
    if amount_value > 0:
        return {
            "kind": "pending",
            "month": key,
            "amount": amount_value,
            "tds_applied": tds_applied,
        }
    if month_due_passed(key, credit_day, today):
        return {"kind": "missed", "month": key, "tds_applied": tds_applied}
    return {"kind": "pending", "month": key, "amount": None, "tds_applied": tds_applied}


def payout_row_cells(row, months, window, entries, health, invalid, today):
    if invalid:
        return payout_invalid_cells(months)
    window_set = set(window)
    return [
        payout_cell(key, window_set, entries.get(key), health, row["credit_day"], today)
        for key in months
    ]


def portfolio_payouts(bond_rows, ledger_by_bond, today):
    prepared, first_keys = payout_prepare(bond_rows, ledger_by_bond, today)
    months = payout_months(today, first_keys)
    rows = []
    for row, window, entries, health, invalid in prepared:
        cells = payout_row_cells(row, months, window, entries, health, invalid, today)
        rows.append(
            {
                "id": row["id"],
                "company": row["company"],
                "isin": row["isin"] or "",
                "health": health,
                "cells": cells,
            }
        )
    return (
        sort_rows(rows),
        [{"key": key, "label": month_label(key)} for key in months],
    )


def _goal_groups(conn, holdings):
    goals = conn.execute(
        "SELECT id, name, target_amount FROM financial_goals ORDER BY id"
    ).fetchall()
    groups = []
    for goal in goals:
        groups.append(
            {
                "key": "goal-%d" % goal["id"],
                "label": goal["name"] or "Goal",
                "locked_target": goal["target_amount"],
                "holdings": [],
            }
        )
    groups.append(
        {
            "key": "ungrouped",
            "label": "Ungrouped",
            "locked_target": None,
            "holdings": list(holdings),
        }
    )
    return [group for group in groups if group["holdings"]]


def _rows_flat(holdings, groups):
    flat = []
    for group in groups:
        flat.append(
            {
                "kind": "group",
                "label": group["label"],
                "locked_target": group["locked_target"],
                "count": len(group["holdings"]),
            }
        )
        for holding in group["holdings"]:
            flat.append({"kind": "row", "row": holding})
    return flat


def portfolio_context(conn, today, tab, form, error, code, group_by="none"):
    bond_rows = conn.execute(
        "SELECT id, company, isin, name, rating, rating_agency, coupon_pct, "
        "expected_yield_pct, payout_cycle, issuer_type, secured, face_value, broker, "
        "amount, start_date, end_date, tenure_months, credit_day, purchase_date, qty "
        "FROM bonds WHERE watch_state = 'holding' "
        "ORDER BY id"
    ).fetchall()
    months_by_bond = ledger_by_bond(conn)
    context = {
        "tab": tab,
        "holdings": [],
        "rows_flat": [],
        "months": [],
        "payouts": [],
        "form": form,
        "error": error,
        "code": code,
        "group_by": group_by,
    }
    if tab == "holdings":
        holdings = portfolio_holdings(conn, bond_rows, months_by_bond, today)
        context["holdings"] = holdings
        if group_by == "goal":
            context["rows_flat"] = _rows_flat(holdings, _goal_groups(conn, holdings))
        else:
            context["rows_flat"] = [
                {"kind": "row", "row": holding} for holding in holdings
            ]
    elif bond_rows:
        rows, months = portfolio_payouts(bond_rows, months_by_bond, today)
        context["payouts"] = rows
        context["months"] = months
    return context


@bp.route("/portfolio")
def portfolio_page():
    db_file = app_db()
    tab = str(request.args.get("tab") or "holdings")
    if tab not in ("holdings", "payouts"):
        return error_page(
            "ERR-portfolio-tab",
            f"unknown tab: {tab!r} (expected 'holdings' or 'payouts')",
            "Portfolio tab failed",
            400,
        )
    group_by = str(request.args.get("group") or "none")
    if group_by not in ("none", "goal"):
        group_by = "none"
    try:
        with get_conn(db_file) as conn:
            context = portfolio_context(
                conn, date.today(), tab, {}, None, None, group_by
            )
    except AppError as exc:
        return error_page(exc.code, exc.message, "Portfolio render failed", 500)
    return render_template("portfolio.html", **context)


@bp.route("/portfolio/<int:bond_id>")
def portfolio_detail_page(bond_id):
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            detail = position_detail(conn, bond_id)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Position detail failed", 404)
    return render_template("portfolio_detail.html", detail=detail)


@bp.route("/portfolio/<int:bond_id>/detail")
def portfolio_position_detail(bond_id):
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            detail = position_detail(conn, bond_id)
    except AppError as exc:
        return jsonify({"error": exc.code, "message": exc.message}), 404
    return jsonify(detail)


@bp.route("/portfolio/invalid/<int:bond_id>/remove", methods=["POST"])
def portfolio_invalid_remove(bond_id):
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            row = conn.execute(
                "SELECT id, start_date, end_date, tenure_months, watch_state, amount FROM bonds WHERE id = ?",
                (bond_id,),
            ).fetchone()
            if row is None:
                raise AppError("ERR-invalid-remove", f"position not found: {bond_id}")
            if row["watch_state"] != "holding":
                raise AppError(
                    "ERR-invalid-remove",
                    f"position {bond_id} is {row['watch_state']}; remove only applies to holdings rows",
                )
            if row_valid(row):
                raise AppError(
                    "ERR-invalid-remove",
                    f"position {bond_id} is valid; remove is only for rows with dates that need review",
                )
            conn.execute("DELETE FROM payment_ledger WHERE bond_id = ?", (bond_id,))
            cursor = conn.execute("DELETE FROM bonds WHERE id = ?", (bond_id,))
            if cursor.rowcount != 1:
                raise AppError(
                    "ERR-invalid-remove",
                    f"remove for position {bond_id} affected {cursor.rowcount} rows",
                )
    except AppError as exc:
        return error_page(exc.code, exc.message, "Remove failed", 400)
    flash("Invalid row removed", "success")
    return redirect(url_for("portfolio.portfolio_page", tab="holdings"))


@bp.route("/payout")
def payout_page():
    db_file = app_db()
    raw_bond = str(request.args.get("bond_id", "")).strip()
    try:
        bond_id = int(raw_bond)
    except ValueError:
        return error_page(
            "ERR-due-dates",
            f"bond_id must be an integer: {raw_bond!r}",
            "Payout schedule failed",
            400,
        )
    cycle = str(request.args.get("cycle", "")).strip().lower()
    try:
        with get_conn(db_file) as conn:
            if not cycle:
                row = conn.execute(
                    "SELECT payment_type, payout_cycle FROM bonds WHERE id = ?",
                    (bond_id,),
                ).fetchone()
                if row is None:
                    raise AppError("ERR-due-dates", f"bond not found: {bond_id!r}")
                cycle = payment_cycle_of(row["payment_type"])
                if cycle is None:
                    cycle = payment_cycle_of(row["payout_cycle"])
                if cycle is None:
                    cycle = "monthly"
            schedule = payout_schedule(conn, bond_id, cycle)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Payout schedule failed", 400)
    return render_template("payout.html", schedule=schedule)
