import re

from . import _resolve_today
from ..engine import (
    entry_paid,
    month_due_passed,
    purchase_date_label,
    purchase_qty_value,
    row_health_state,
    tenure_window,
)
from ..status import month_key
from ..validators import AppError, safe_float
from .grid import month_label
from .summary import bond_master_provenance, status_overview

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def received_by_bond(conn):
    totals = {}
    for row in conn.execute(
        "SELECT bond_id, COALESCE(SUM(amount), 0) AS total FROM payment_ledger "
        "WHERE paid = 1 AND amount > 0 GROUP BY bond_id"
    ).fetchall():
        totals[row["bond_id"]] = float(row["total"])
    return totals


def portfolio_snapshot(conn):
    return [
        {
            "id": entry["id"],
            "company": entry["company"],
            "invested": safe_float(entry["amount"]),
            "provenance": entry.get("provenance"),
        }
        for entry in status_overview(conn)
    ]


def _month_state(entry, key, credit_day, today):
    if entry is not None:
        try:
            paid = entry_paid(entry)
        except AppError:
            paid = False
        amount = safe_float(entry["amount"])
        if paid and amount > 0:
            return "paid", amount
        if month_due_passed(key, credit_day, today):
            return "unpaid", None
        return "soon", None
    if month_due_passed(key, credit_day, today):
        return "unpaid", None
    return "soon", None


def _payment_months(row, entries, today):
    try:
        window = tenure_window(row["start_date"], row["tenure_months"])
    except AppError:
        return []
    current = month_key(today)
    keys = [key for key in window if key <= current]
    if not keys:
        return []
    chips = []
    for key in keys:
        try:
            state, amount = _month_state(entries.get(key), key, row["credit_day"], today)
        except AppError:
            return []
        chips.append(
            {"key": key, "label": month_label(key), "state": state, "amount": amount}
        )
    chips.reverse()
    return chips


def position_detail(conn, bond_id, today=None):
    from ..phase4 import tds_breakdown

    today_value = _resolve_today(today)
    row = conn.execute(
        "SELECT id, company, isin, name, rating, rating_agency, coupon_pct, "
        "expected_yield_pct, payout_cycle, issuer_type, secured, face_value, "
        "amount, start_date, end_date, tenure_months, credit_day, watch_state, broker, "
        "purchase_date, qty, goal_id "
        "FROM bonds WHERE id = ?",
        (bond_id,),
    ).fetchone()
    if row is None:
        raise AppError("ERR-position-detail", f"position not found: {bond_id!r}")
    if row["watch_state"] != "holding":
        raise AppError(
            "ERR-position-detail", f"position {bond_id} is a candidate, not a holding"
        )
    goal = None
    if row["goal_id"] is not None:
        goal = conn.execute(
            "SELECT id, name, target_amount FROM financial_goals WHERE id = ?",
            (row["goal_id"],),
        ).fetchone()
    entries = {}
    payments = []
    for entry in conn.execute(
        "SELECT month, amount, paid, tds_applied FROM payment_ledger WHERE bond_id = ? ORDER BY month",
        (bond_id,),
    ).fetchall():
        amount = safe_float(entry["amount"])
        paid = bool(entry["paid"])
        tds_applied = bool(entry["tds_applied"])
        entries[entry["month"]] = {
            "amount": entry["amount"],
            "paid": paid,
            "tds_applied": tds_applied,
        }
        payments.append(
            {
                "month": entry["month"],
                "amount": amount,
                "paid": paid,
                "tds_applied": tds_applied,
            }
        )
    received = 0.0
    tds_total = 0
    gross_total = 0
    for item in payments:
        if item["paid"] and item["amount"] > 0:
            received += item["amount"]
            part = tds_breakdown(item["amount"], item["tds_applied"])
            tds_total += part["tds"]
            gross_total += part["gross"]
    invested, health, next_payout, bad_amount = row_health_state(
        row, entries, today_value, None
    )
    return {
        "id": row["id"],
        "company": row["company"],
        "isin": row["isin"] or "",
        "rating": row["rating"] or "",
        "rating_agency": row["rating_agency"] or "",
        "coupon_pct": row["coupon_pct"],
        "expected_yield_pct": row["expected_yield_pct"],
        "frequency": row["payout_cycle"],
        "issuer_type": row["issuer_type"] or "",
        "secured": row["secured"],
        "face_value": row["face_value"],
        "invested": invested,
        "received": received,
        "tds": tds_total,
        "gross": gross_total,
        "next_payout": next_payout,
        "status": health,
        "broker": row["broker"] or "",
        "source_note": row["name"] or "",
        "purchase_date": purchase_date_label(row["purchase_date"]),
        "qty": purchase_qty_value(row["qty"]),
        "credit_day": row["credit_day"],
        "end_date": row["end_date"],
        "tenure_months": row["tenure_months"],
        "payment_months": _payment_months(row, entries, today_value),
        "payments": payments,
        "goal_id": row["goal_id"],
        "goal_name": (goal["name"] if goal is not None else None),
        "goal_target": (goal["target_amount"] if goal is not None else None),
        "provenance": bond_master_provenance(conn, row["isin"]),
    }


def delete_candidate(conn, bond_id):
    conn.execute("DELETE FROM payment_ledger WHERE bond_id = ?", (bond_id,))
    cursor = conn.execute("DELETE FROM bonds WHERE id = ?", (bond_id,))
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-watch-delete",
            f"delete for candidate {bond_id} affected {cursor.rowcount} rows",
        )
    return bond_id
