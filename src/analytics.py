from .queries import free_up_report, status_overview
from .validators import AppError


def bond_analytics(row):
    investment = row.get("watch_investment")
    tenure = row.get("tenure_months")
    face = row.get("face_value")
    interest = row.get("interest_payout")
    if face is None or interest is None or investment is None:
        return {"computable": False}
    try:
        tenure_value = int(tenure)
    except (TypeError, ValueError) as exc:
        raise AppError(
            "ERR-watch-analytics",
            f"bond {row.get('isin')!r}: unparseable tenure {tenure!r}",
        ) from exc
    if tenure_value < 1:
        raise AppError(
            "ERR-watch-analytics",
            f"bond {row.get('isin')!r}: tenure must be positive: {tenure!r}",
        )
    investment_value = float(investment)
    face_value = float(face)
    interest_value = float(interest)
    discount = face_value - investment_value
    total_amount = investment_value + interest_value + discount
    payment_type = str(row.get("payment_type") or "")
    quarterly = "quart" in payment_type.lower()
    per_month = (interest_value / tenure_value) * (3 if quarterly else 1)
    actual_per_month = (interest_value - discount) / tenure_value
    tds = per_month - per_month * 0.10
    twelve_month = per_month * 12
    tlp = row.get("tlp_amount")
    tlp_value = investment_value if tlp is None else float(tlp)
    qty = row.get("qty")
    qty_value = None if qty is None else float(qty)
    qty_tl = None if qty_value is None else tlp_value * qty_value
    return {
        "computable": True,
        "discount": discount,
        "total_amount": total_amount,
        "per_month": per_month,
        "actual_per_month": actual_per_month,
        "tds": tds,
        "twelve_month": twelve_month,
        "qty": qty_value,
        "qty_tl": qty_tl,
        "quarterly": quarterly,
    }


def compute_watch_analytics(conn):
    try:
        rows = conn.execute(
            "SELECT id, isin, company, amount, tenure_months, face_value, tlp_amount, "
            "payment_type, interest_payout, qty, watch_investment FROM bonds"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-watch-analytics", f"watch input query failed: {exc}") from exc
    return {row["id"]: bond_analytics(dict(row)) for row in rows}


def watch_model(conn, today=None):
    try:
        entries = status_overview(conn, today)
        analytics = compute_watch_analytics(conn)
        freeup = free_up_report(conn, today)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-watch-analytics", f"watch model failed: {exc}") from exc
    rows = []
    for entry in entries:
        row = dict(entry)
        row["analytics"] = analytics.get(entry["id"], {"computable": False})
        freed_entry = freeup["per_bond"].get(entry["id"], {})
        row["freed"] = bool(freed_entry.get("freed"))
        row["freed_amount"] = freed_entry.get("freed_amount")
        rows.append(row)
    return {
        "entries": rows,
        "freeup": {
            "principal_freed_by_completed": freeup["principal_freed_by_completed"],
            "active_locked": freeup["active_locked"],
            "deduction_breakdown": freeup["deduction_breakdown"],
        },
    }
