import re

from . import _resolve_today
from ..engine import purchase_date_label, purchase_qty_value, row_health_state
from ..validators import AppError, safe_float
from .summary import status_overview

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
        }
        for entry in status_overview(conn)
    ]


def position_detail(conn, bond_id, today=None):
    today_value = _resolve_today(today)
    row = conn.execute(
        "SELECT id, company, isin, name, rating, rating_agency, coupon_pct, "
        "expected_yield_pct, payout_cycle, issuer_type, secured, face_value, "
        "amount, start_date, end_date, tenure_months, credit_day, watch_state, broker, "
        "purchase_date, qty "
        "FROM bonds WHERE id = ?",
        (bond_id,),
    ).fetchone()
    if row is None:
        raise AppError("ERR-position-detail", f"position not found: {bond_id!r}")
    if row["watch_state"] != "holding":
        raise AppError(
            "ERR-position-detail", f"position {bond_id} is a candidate, not a holding"
        )
    entries = {}
    payments = []
    for entry in conn.execute(
        "SELECT month, amount, paid FROM payment_ledger WHERE bond_id = ? ORDER BY month",
        (bond_id,),
    ).fetchall():
        amount = safe_float(entry["amount"])
        paid = bool(entry["paid"])
        entries[entry["month"]] = {"amount": entry["amount"], "paid": paid}
        payments.append({"month": entry["month"], "amount": amount, "paid": paid})
    received = sum(item["amount"] for item in payments if item["paid"] and item["amount"] > 0)
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
        "next_payout": next_payout,
        "status": health,
        "broker": row["broker"] or "",
        "source_note": row["name"] or "",
        "purchase_date": purchase_date_label(row["purchase_date"]),
        "qty": purchase_qty_value(row["qty"]),
        "payments": payments,
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
