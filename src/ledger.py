import re

from .validators import AppError, safe_float

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def _parse_month(month):
    if isinstance(month, str) and MONTH_PATTERN.match(month.strip()):
        return month.strip()
    raise AppError("ERR-ledger-insert", f"unparseable month (expected YYYY-MM): {month!r}")


def _require_bond(conn, bond_id):
    row = conn.execute("SELECT id FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    if row is None:
        raise AppError("ERR-ledger-insert", f"bond not found: {bond_id!r}")
    return row


def ledger_by_bond(conn, bond_ids=None):
    query = "SELECT bond_id, month, amount, paid FROM payment_ledger"
    params = []
    if bond_ids is not None:
        ids = list(bond_ids)
        if not ids:
            return {}
        query += " WHERE bond_id IN (%s)" % ",".join("?" for _ in ids)
        params = ids
    months_by_bond = {}
    for row in conn.execute(query, params).fetchall():
        amount = safe_float(row["amount"])
        paid = bool(row["paid"]) and row["amount"] is not None and amount > 0
        months_by_bond.setdefault(row["bond_id"], {})[row["month"]] = {
            "paid": paid,
            "amount": amount,
        }
    return months_by_bond


def paid_map(conn, bond_id, window):
    months = ledger_by_bond(conn, [bond_id]).get(bond_id, {})
    return {key: bool(months.get(key, {}).get("paid")) for key in window}


def save_payment(conn, bond_id, month, amount, paid):
    _require_bond(conn, bond_id)
    key = _parse_month(month)
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise AppError("ERR-ledger-insert", f"amount must be a number: {amount!r}")
    value = float(amount)
    if value < 0:
        raise AppError("ERR-ledger-insert", f"amount must not be negative: {amount!r}")
    flag = 1 if (paid and value > 0) else 0
    existing = conn.execute(
        "SELECT id FROM payment_ledger WHERE bond_id = ? AND month = ?",
        (bond_id, key),
    ).fetchone()
    if existing is None:
        cursor = conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            (bond_id, key, value, flag),
        )
        action = "inserted"
    else:
        cursor = conn.execute(
            "UPDATE payment_ledger SET amount = ?, paid = ? WHERE id = ?",
            (value, flag, existing["id"]),
        )
        action = "corrected"
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-ledger-edit",
            f"ledger write for bond {bond_id} month {key} affected {cursor.rowcount} rows",
        )
    return {"bond_id": bond_id, "month": key, "amount": value, "paid": flag, "action": action}


def insert_position(conn, company, isin, amount, start_date, end_date, tenure_months, credit_day):
    if isinstance(amount, bool) or not isinstance(amount, (int, float)):
        raise AppError("ERR-add-insert", f"amount must be a number: {amount!r}")
    value = float(amount)
    if value < 0:
        raise AppError("ERR-add-insert", f"amount must not be negative: {amount!r}")
    cursor = conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
        "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            company,
            isin,
            company,
            value,
            None,
            start_date.isoformat(),
            end_date.isoformat(),
            int(tenure_months),
            int(credit_day),
            "On-going",
        ),
    )
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-add-insert",
            f"position insert for {company} affected {cursor.rowcount} rows",
        )
    return cursor.lastrowid
