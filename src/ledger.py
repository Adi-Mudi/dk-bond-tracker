from .validators import safe_float


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
