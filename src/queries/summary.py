from . import _resolve_today, _default_today
from ..engine import sort_rows
from ..status import compute_row_status_daywise, month_key, tenure_month_map
from ..validators import AppError, safe_float


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


def goal_derived(conn):
    try:
        returns_by_bond = {}
        for row in conn.execute(
            "SELECT bond_id, SUM(amount) AS received FROM payment_ledger "
            "WHERE paid = 1 AND amount > 0 GROUP BY bond_id"
        ).fetchall():
            returns_by_bond[row["bond_id"]] = safe_float(row["received"])
        bond_rows = conn.execute(
            "SELECT id, goal_id, company, isin, amount FROM bonds "
            "WHERE goal_id IS NOT NULL AND watch_state = 'holding' ORDER BY id"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-goals-op", f"derived: query failed: {exc}") from exc
    derived = {}
    for row in bond_rows:
        entry = derived.setdefault(
            row["goal_id"], {"invested": 0.0, "returns": 0.0, "bonds": []}
        )
        invested = safe_float(row["amount"])
        received = returns_by_bond.get(row["id"], 0.0)
        entry["invested"] += invested
        entry["returns"] += received
        entry["bonds"].append(
            {
                "id": row["id"],
                "company": row["company"] or "",
                "isin": row["isin"] or "",
                "invested": invested,
                "returns": received,
            }
        )
    return derived


def status_overview(conn, today=None):
    if today is None:
        today = _default_today()
    rows = conn.execute("SELECT * FROM bonds WHERE watch_state = 'holding'").fetchall()
    entries = []
    for row in rows:
        try:
            months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
            status = compute_row_status_daywise(
                months, row["tenure_months"], row["credit_day"], today
            )
        except AppError:
            status = "Invalid"
        try:
            float(row["amount"] or 0.0)
        except (TypeError, ValueError):
            status = "Invalid"
        entry = dict(row)
        entry["status"] = status
        entries.append(entry)
    return sort_rows(entries)


def _month_keys_span(start_key, end_key):
    year, mon = map(int, start_key.split("-"))
    end_year, end_mon = map(int, end_key.split("-"))
    total = (end_year - year) * 12 + (end_mon - mon)
    if total < 0:
        return []
    return [
        f"{year + (mon - 1 + offset) // 12:04d}-{(mon - 1 + offset) % 12 + 1:02d}"
        for offset in range(total + 1)
    ]


def summary_counts(conn, today=None):
    try:
        overview = status_overview(conn, today)
    except AppError as exc:
        raise AppError("ERR-query-counts", f"status computation failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-query-counts", f"status computation failed: {exc}") from exc
    counts = {"danger": 0, "ongoing": 0, "completed": 0, "invalid": 0, "total": len(overview)}
    for entry in overview:
        status = entry["status"]
        if status == "Danger":
            counts["danger"] += 1
        elif status == "On-going":
            counts["ongoing"] += 1
        elif status == "Completed":
            counts["completed"] += 1
        elif status == "Invalid":
            counts["invalid"] += 1
        else:
            raise AppError("ERR-query-counts", f"unknown status for bond {entry['id']}: {status!r}")
    if counts["danger"] + counts["ongoing"] + counts["completed"] + counts["invalid"] != counts["total"]:
        raise AppError("ERR-query-counts", "status counts do not sum to total bond count")
    return counts


def received_tds_gross(conn):
    from ..phase4 import tds_breakdown

    tds_total = 0
    gross_total = 0
    for row in conn.execute(
        "SELECT amount, tds_applied FROM payment_ledger WHERE paid = 1 AND amount > 0"
    ).fetchall():
        amount = safe_float(row["amount"])
        if amount <= 0:
            continue
        breakdown = tds_breakdown(amount, bool(row["tds_applied"]))
        tds_total += breakdown["tds"]
        gross_total += breakdown["gross"]
    return {"tds": tds_total, "gross": gross_total}


def summary_amounts(conn, today=None):
    try:
        totals = portfolio_totals(conn)
    except AppError as exc:
        raise AppError("ERR-query-summary-amounts", f"portfolio totals failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-query-summary-amounts", f"portfolio totals failed: {exc}") from exc
    breakdown = received_tds_gross(conn)
    today_value = _resolve_today(today)
    if today_value is None:
        return {
            "total_investment": totals["total_investment"],
            "till_return": totals["till_return"],
            "balance": totals["balance"],
            "received_tds": breakdown["tds"],
            "received_gross": breakdown["gross"],
            "month": None,
            "month_message": "current month could not be resolved",
        }
    return {
        "total_investment": totals["total_investment"],
        "till_return": totals["till_return"],
        "balance": totals["balance"],
        "received_tds": breakdown["tds"],
        "received_gross": breakdown["gross"],
        "month": month_key(today_value),
        "month_message": None,
    }
