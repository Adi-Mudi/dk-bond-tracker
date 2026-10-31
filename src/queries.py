import calendar
import re
from datetime import date

from .engine import (
    derive_health,
    display_label,
    entry_paid,
    payout_date_label,
    tenure_window,
)
from .status import (
    compute_row_status_daywise,
    month_key,
    tenure_month_map,
)
from .validators import AppError, add_months, parse_date_value

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
STATUS_COLORS = {"Danger": "red", "On-going": "orange", "Completed": "green", "Invalid": "grey"}
STATUS_ORDER = {"Danger": 0, "On-going": 1, "Completed": 2, "Invalid": 3}


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


HISTORY_MONTH_CAP = 120


def _resolve_today(today):
    if today is None:
        try:
            return date.today()
        except Exception:
            return None
    return today


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


def summary_amounts(conn, today=None):
    try:
        totals = portfolio_totals(conn)
    except AppError as exc:
        raise AppError("ERR-query-summary-amounts", f"portfolio totals failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-query-summary-amounts", f"portfolio totals failed: {exc}") from exc
    today_value = _resolve_today(today)
    if today_value is None:
        return {
            "total_investment": totals["total_investment"],
            "till_return": totals["till_return"],
            "balance": totals["balance"],
            "month": None,
            "month_message": "current month could not be resolved",
        }
    return {
        "total_investment": totals["total_investment"],
        "till_return": totals["till_return"],
        "balance": totals["balance"],
        "month": month_key(today_value),
        "month_message": None,
    }


def this_month_returns(conn, today=None):
    today_value = _resolve_today(today)
    if today_value is None:
        return {"month": None, "total": None, "message": "current month could not be resolved"}
    key = month_key(today_value)
    try:
        row = conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM payment_ledger "
            "WHERE month = ? AND paid = 1 AND amount > 0",
            (key,),
        ).fetchone()
    except Exception as exc:
        raise AppError("ERR-query-month-returns", f"this-month query failed: {exc}") from exc
    return {"month": key, "total": float(row["total"]), "message": None}


def active_bonds_in_month(conn, today=None):
    today_value = _resolve_today(today)
    if today_value is None:
        raise AppError("ERR-query-month-returns", "current month could not be resolved")
    current = month_key(today_value)
    try:
        rows = conn.execute(
            "SELECT id, company, start_date, tenure_months FROM bonds"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-query-month-returns", f"active-bond scan failed: {exc}") from exc
    active = []
    for row in rows:
        try:
            start = parse_date_value(row["start_date"], "start_date")
            tenure = int(row["tenure_months"])
        except (AppError, TypeError, ValueError) as exc:
            raise AppError(
                "ERR-active-bonds",
                f"bond {row['id']}: unparseable row metadata: {exc}",
            ) from exc
        if tenure < 1:
            raise AppError(
                "ERR-active-bonds",
                f"bond {row['id']}: tenure_months must be positive: {row['tenure_months']!r}",
            )
        first = month_key(start)
        last = month_key(add_months(start, tenure - 1))
        if first <= current <= last:
            active.append({"id": row["id"], "company": row["company"]})
    return active


def _history_window(conn, current):
    candidates = []
    try:
        ledger_row = conn.execute("SELECT MIN(month) AS earliest FROM payment_ledger").fetchone()
        if ledger_row is not None and ledger_row["earliest"]:
            candidates.append(str(ledger_row["earliest"]).strip())
        for row in conn.execute("SELECT start_date FROM bonds").fetchall():
            candidates.append(month_key(parse_date_value(row["start_date"], "start_date")))
    except AppError as exc:
        raise AppError("ERR-query-history", f"window derivation failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-query-history", f"window derivation failed: {exc}") from exc
    if not candidates:
        return []
    start = min(candidates)
    if start > current:
        start = current
    keys = _month_keys_span(start, current)
    if len(keys) > HISTORY_MONTH_CAP:
        keys = keys[-HISTORY_MONTH_CAP:]
    return keys


def monthly_history(conn, today=None):
    today_value = _resolve_today(today)
    if today_value is None:
        raise AppError("ERR-query-history", "current month could not be resolved")
    current = month_key(today_value)
    try:
        window = _history_window(conn, current)
        rows = conn.execute(
            "SELECT month, SUM(amount) AS total FROM payment_ledger "
            "WHERE paid = 1 AND amount > 0 GROUP BY month"
        ).fetchall()
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-query-history", f"monthly history aggregation failed: {exc}") from exc
    totals = {row["month"]: float(row["total"] or 0) for row in rows}
    return [{"month": m, "total": totals.get(m, 0.0)} for m in window]


def chart_data(conn, today=None):
    today_value = _resolve_today(today)
    if today_value is None:
        raise AppError("ERR-chart-data", "current month could not be resolved")
    try:
        counts = summary_counts(conn, today_value)
        current = month_key(today_value)
        window = _history_window(conn, current)
        ledger_rows = conn.execute(
            "SELECT bond_id, month, amount FROM payment_ledger WHERE paid = 1 AND amount > 0"
        ).fetchall()
        bond_rows = conn.execute(
            "SELECT id, company, name, amount, start_date FROM bonds"
        ).fetchall()
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-chart-data", f"chart series query failed: {exc}") from exc
    received_by_bond = {}
    received_by_month = {}
    for row in ledger_rows:
        received_by_bond[row["bond_id"]] = received_by_bond.get(row["bond_id"], 0.0) + float(row["amount"])
        received_by_month[row["month"]] = received_by_month.get(row["month"], 0.0) + float(row["amount"])
    bars = []
    invested_by_month = {}
    for row in bond_rows:
        label = row["company"] or row["name"] or f"Bond {row['id']}"
        invested = float(row["amount"] or 0)
        bars.append(
            {
                "bond": label,
                "invested": invested,
                "received": received_by_bond.get(row["id"], 0.0),
            }
        )
        try:
            start_key = month_key(parse_date_value(row["start_date"], "start_date"))
        except AppError as exc:
            raise AppError("ERR-chart-data", f"bond {row['id']}: unparseable start_date {row['start_date']!r}") from exc
        invested_by_month[start_key] = invested_by_month.get(start_key, 0.0) + invested
    cumulative = []
    if window:
        running_invested = sum(
            amount for key, amount in invested_by_month.items() if key <= window[0]
        )
        running_received = 0.0
        for index, month in enumerate(window):
            if index > 0:
                running_invested += invested_by_month.get(month, 0.0)
            running_received += received_by_month.get(month, 0.0)
            balance = running_received - running_invested
            cumulative.append(
                {
                    "month": month,
                    "cumulative_till_return": running_received,
                    "balance_flag_negative": balance < 0,
                }
            )
    return {"bars": bars, "cumulative": cumulative, "donut": counts}


def month_label(key):
    year, mon = key.split("-")
    return f"{calendar.month_abbr[int(mon)]}-{year}"


def grid_month_columns(first_keys, last_keys, current_key):
    if not first_keys or not last_keys:
        return []
    start = min(first_keys)
    end = max(max(last_keys), current_key)
    return _month_keys_span(start, end)


def grid_model(conn, today=None):
    today_value = _resolve_today(today)
    if today_value is None:
        raise AppError("ERR-render-grid", "current month could not be resolved")
    current = month_key(today_value)
    try:
        bond_rows = conn.execute(
            "SELECT id, company, isin, start_date, tenure_months, credit_day FROM bonds "
            "WHERE watch_state = 'holding' ORDER BY id"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-render-grid", f"bond scan failed: {exc}") from exc
    entries = []
    first_keys = []
    last_keys = []
    for row in bond_rows:
        try:
            start = parse_date_value(row["start_date"], "start_date")
            tenure = int(row["tenure_months"])
            if tenure < 1:
                raise AppError(
                    "ERR-render-grid",
                    f"bond {row['id']}: tenure_months must be positive: {row['tenure_months']!r}",
                )
            first = month_key(start)
            last = month_key(add_months(start, tenure - 1))
        except (AppError, TypeError, ValueError):
            entries.append({"row": row, "invalid": True, "tenure": row["tenure_months"]})
            continue
        entries.append(
            {"row": row, "invalid": False, "first": first, "last": last, "tenure": tenure}
        )
        first_keys.append(first)
        last_keys.append(last)
    months = grid_month_columns(first_keys, last_keys, current)
    headers = [
        {"key": key, "label": month_label(key), "current": key == current}
        for key in months
    ]
    model_rows = []
    for entry in entries:
        row = entry["row"]
        status = "Invalid"
        window = {}
        if not entry["invalid"]:
            try:
                window = tenure_month_map(conn, row["id"], row["start_date"], entry["tenure"])
                status = compute_row_status_daywise(
                    window, entry["tenure"], row["credit_day"], today_value
                )
            except AppError:
                status = "Invalid"
                window = {}
        cells = []
        for key in months:
            if key not in window:
                state = "future"
            elif window[key]:
                state = "paid"
            elif key <= current:
                state = "due"
            else:
                state = "future"
            cells.append({"month": key, "state": state, "bond_id": row["id"]})
        model_rows.append(
            {
                "id": row["id"],
                "company": row["company"],
                "isin": row["isin"],
                "status": status,
                "tenure_months": entry["tenure"],
                "cells": cells,
            }
        )
    model_rows.sort(
        key=lambda item: (
            STATUS_ORDER[item["status"]],
            str(item["company"] or "").lower(),
            item["id"],
        )
    )
    return {
        "months": headers,
        "rows": model_rows,
        "current": current,
        "bond_count": len(model_rows),
    }


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


def free_up_report(conn, today=None):
    try:
        overview = status_overview(conn, today)
    except AppError as exc:
        raise AppError("ERR-reinvestment", f"status computation failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError("ERR-reinvestment", f"status computation failed: {exc}") from exc
    by_status = {"Completed": 0.0, "On-going": 0.0, "Danger": 0.0}
    counts = {"Completed": 0, "On-going": 0, "Danger": 0}
    per_bond = {}
    for entry in overview:
        status = entry["status"]
        if status not in by_status:
            raise AppError("ERR-reinvestment", f"unknown status for bond {entry['id']}: {status!r}")
        amount = float(entry["amount"] or 0)
        by_status[status] += amount
        counts[status] += 1
        per_bond[entry["id"]] = {
            "freed": status == "Completed",
            "freed_amount": amount if status == "Completed" else None,
        }
    principal_freed = by_status["Completed"]
    active_locked = by_status["On-going"] + by_status["Danger"]
    return {
        "principal_freed_by_completed": principal_freed,
        "active_locked": active_locked,
        "deduction_breakdown": {
            "On-going": by_status["On-going"],
            "Danger": by_status["Danger"],
        },
        "by_status": by_status,
        "counts": counts,
        "per_bond": per_bond,
        "total_investment": sum(by_status.values()),
    }


def received_by_bond(conn):
    totals = {}
    for row in conn.execute(
        "SELECT bond_id, COALESCE(SUM(amount), 0) AS total FROM payment_ledger "
        "WHERE paid = 1 AND amount > 0 GROUP BY bond_id"
    ).fetchall():
        totals[row["bond_id"]] = float(row["total"])
    return totals


def _safe_invested(amount):
    try:
        return float(amount or 0.0)
    except (TypeError, ValueError):
        return 0.0


def portfolio_snapshot(conn):
    rows = conn.execute(
        "SELECT id, company, amount FROM bonds WHERE watch_state = 'holding' "
        "ORDER BY company COLLATE NOCASE, id"
    ).fetchall()
    return [
        {"id": row["id"], "company": row["company"], "invested": _safe_invested(row["amount"])}
        for row in rows
    ]


def position_detail(conn, bond_id, today=None):
    today_value = _resolve_today(today)
    row = conn.execute(
        "SELECT id, company, isin, rating, coupon_pct, expected_yield_pct, payout_cycle, "
        "amount, start_date, end_date, tenure_months, credit_day, watch_state, broker "
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
        try:
            amount = float(entry["amount"] or 0.0)
        except (TypeError, ValueError):
            amount = 0.0
        paid = bool(entry["paid"])
        entries[entry["month"]] = {"amount": entry["amount"], "paid": paid}
        payments.append({"month": entry["month"], "amount": amount, "paid": paid})
    received = sum(item["amount"] for item in payments if item["paid"] and item["amount"] > 0)
    bad_amount = False
    try:
        invested = float(row["amount"] or 0.0)
    except (TypeError, ValueError):
        invested = 0.0
        bad_amount = True
    try:
        health = display_label(derive_health(row, entries, today_value))
        next_payout = None
        if health != "Matured":
            for key in tenure_window(row["start_date"], row["tenure_months"]):
                if not entry_paid(entries.get(key)):
                    next_payout = payout_date_label(key, row["credit_day"])
                    break
    except AppError:
        health = "Invalid"
        next_payout = None
    if bad_amount:
        health = "Invalid"
        next_payout = None
    return {
        "id": row["id"],
        "company": row["company"],
        "isin": row["isin"] or "",
        "rating": row["rating"] or "",
        "coupon_pct": row["coupon_pct"],
        "expected_yield_pct": row["expected_yield_pct"],
        "frequency": row["payout_cycle"],
        "invested": invested,
        "received": received,
        "next_payout": next_payout,
        "status": health,
        "broker": row["broker"] or "",
        "payments": payments,
    }
