import re
from datetime import date

from .status import compute_row_status, tenure_month_map
from .validators import AppError

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
STATUS_COLORS = {"Danger": "red", "On-going": "orange", "Completed": "green"}
STATUS_ORDER = {"Danger": 0, "On-going": 1, "Completed": 2}


def _parse_month(month):
    if isinstance(month, str) and MONTH_PATTERN.match(month.strip()):
        return month.strip()
    raise AppError("ERR-ledger-insert", f"unparseable month (expected YYYY-MM): {month!r}")


def _positive_amount(amount):
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise AppError("ERR-ledger-insert", f"amount must be a number greater than zero: {amount!r}")
    value = float(amount)
    if value <= 0:
        raise AppError("ERR-ledger-insert", f"amount must be greater than zero: {amount!r}")
    return value


def _require_bond(conn, bond_id):
    row = conn.execute("SELECT id FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    if row is None:
        raise AppError("ERR-ledger-insert", f"bond not found: {bond_id!r}")
    return row


def insert_payment(conn, bond_id, month, amount):
    _require_bond(conn, bond_id)
    key = _parse_month(month)
    value = _positive_amount(amount)
    existing = conn.execute(
        "SELECT id, amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
        (bond_id, key),
    ).fetchone()
    if existing is None:
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, 1)",
            (bond_id, key, value),
        )
        return {"bond_id": bond_id, "month": key, "amount": value, "paid": 1, "action": "inserted"}
    existing_amount = existing["amount"]
    already_paid = bool(existing["paid"]) and existing_amount is not None and float(existing_amount) > 0
    if already_paid:
        raise AppError(
            "ERR-ledger-insert",
            f"payment already recorded for bond {bond_id} month {key}; "
            "use the correction path (AF-11)",
        )
    conn.execute(
        "UPDATE payment_ledger SET amount = ?, paid = 1 WHERE id = ?",
        (value, existing["id"]),
    )
    return {"bond_id": bond_id, "month": key, "amount": value, "paid": 1, "action": "updated"}


def void_payment(conn, bond_id, month):
    if not isinstance(month, str) or not MONTH_PATTERN.match(month.strip()):
        raise AppError(
            "ERR-ledger-edit",
            f"ledger row not found for bond {bond_id} month {month!r}",
        )
    key = month.strip()
    row = conn.execute(
        "SELECT id FROM payment_ledger WHERE bond_id = ? AND month = ?",
        (bond_id, key),
    ).fetchone()
    if row is None:
        raise AppError(
            "ERR-ledger-edit",
            f"ledger row not found for bond {bond_id} month {key}",
        )
    cursor = conn.execute(
        "UPDATE payment_ledger SET amount = 0, paid = 0 WHERE id = ?",
        (row["id"],),
    )
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-ledger-edit",
            f"ledger update for bond {bond_id} month {key} affected {cursor.rowcount} rows",
        )
    return {"bond_id": bond_id, "month": key, "amount": 0.0, "paid": 0}


def bond_month_totals(conn, bond_id):
    bond = conn.execute("SELECT maturity FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    if bond is None:
        raise AppError("ERR-query-totals", f"bond not found: {bond_id!r}")
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS till FROM payment_ledger "
            "WHERE bond_id = ? AND paid = 1 AND amount > 0",
            (bond_id,),
        ).fetchone()
    except Exception as exc:
        raise AppError("ERR-query-totals", f"ledger totals failed for bond {bond_id}: {exc}") from exc
    k_value = float(row["till"])
    maturity = float(bond["maturity"]) if bond["maturity"] is not None else 0.0
    return {"k": k_value, "l": k_value - maturity}


def portfolio_totals(conn):
    try:
        investment = float(
            conn.execute("SELECT COALESCE(SUM(amount), 0) AS value FROM bonds").fetchone()["value"]
        )
        maturity = float(
            conn.execute("SELECT COALESCE(SUM(maturity), 0) AS value FROM bonds").fetchone()["value"]
        )
        till_return = float(
            conn.execute(
                "SELECT COALESCE(SUM(amount), 0) AS value FROM payment_ledger "
                "WHERE paid = 1 AND amount > 0"
            ).fetchone()["value"]
        )
    except Exception as exc:
        raise AppError("ERR-query-portfolio", f"portfolio totals query failed: {exc}") from exc
    return {
        "total_investment": investment,
        "till_return": till_return,
        "balance": till_return - maturity,
    }


def status_overview(conn, today=None):
    if today is None:
        today = date.today()
    rows = conn.execute("SELECT * FROM bonds").fetchall()
    entries = []
    for row in rows:
        months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
        status = compute_row_status(months, row["tenure_months"], today)
        entry = dict(row)
        entry["status"] = status
        entry["color"] = STATUS_COLORS[status]
        entries.append(entry)
    entries.sort(
        key=lambda item: (
            STATUS_ORDER[item["status"]],
            str(item["company"] or "").lower(),
            item["id"],
        )
    )
    return entries
