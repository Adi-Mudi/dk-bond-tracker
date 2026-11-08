from . import _resolve_today
from ..engine import tenure_window
from ..status import month_key
from ..validators import AppError, parse_date_value, safe_float
from .detail import MONTH_PATTERN
from .grid import month_label
from .summary import _month_keys_span, summary_counts

HISTORY_MONTH_CAP = 120


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


def returns_history(conn, today=None):
    today_value = _resolve_today(today)
    if today_value is None:
        raise AppError("ERR-query-returns", "current month could not be resolved")
    current = month_key(today_value)
    window = _history_window(conn, current, code="ERR-query-returns", skip_bad_dates=True)
    try:
        ledger_rows = conn.execute(
            "SELECT month, SUM(amount) AS total FROM payment_ledger "
            "WHERE paid = 1 AND amount > 0 GROUP BY month"
        ).fetchall()
        paid_rows = conn.execute(
            "SELECT bond_id, month FROM payment_ledger WHERE paid = 1 AND amount > 0"
        ).fetchall()
        bond_rows = conn.execute(
            "SELECT id, start_date, tenure_months FROM bonds WHERE watch_state = 'holding'"
        ).fetchall()
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-query-returns", f"returns aggregation failed: {exc}") from exc

    interest_by_month = {}
    for row in ledger_rows:
        month = str(row["month"] or "").strip()
        if not MONTH_PATTERN.match(month):
            continue
        interest_by_month[month] = safe_float(row["total"])
    paid_pairs = {
        (row["bond_id"], str(row["month"] or "").strip())
        for row in paid_rows
        if MONTH_PATTERN.match(str(row["month"] or "").strip())
    }
    active_by_month = {}
    for row in bond_rows:
        try:
            keys = tenure_window(row["start_date"], row["tenure_months"])
        except AppError:
            continue
        for key in keys:
            active_by_month.setdefault(key, set()).add(row["id"])
    rows = []
    running = 0.0
    for key in window:
        interest = interest_by_month.get(key, 0.0)
        running += interest
        active = active_by_month.get(key, set())
        paid_count = sum(1 for bond_id in active if (bond_id, key) in paid_pairs)
        rows.append(
            {
                "month": key,
                "label": month_label(key),
                "interest": interest,
                "paid_count": paid_count,
                "pending_count": max(len(active) - paid_count, 0),
                "cumulative": running,
                "is_current": key == current,
            }
        )
    rows.reverse()
    return {"rows": rows, "active_count": len(active_by_month.get(current, set()))}


def _history_window(conn, current, code="ERR-query-history", skip_bad_dates=False):
    candidates = []
    try:
        ledger_row = conn.execute("SELECT MIN(month) AS earliest FROM payment_ledger").fetchone()
        if ledger_row is not None and ledger_row["earliest"]:
            earliest = str(ledger_row["earliest"]).strip()
            if MONTH_PATTERN.match(earliest):
                candidates.append(earliest)
        for row in conn.execute("SELECT start_date FROM bonds").fetchall():
            try:
                candidates.append(month_key(parse_date_value(row["start_date"], "start_date")))
            except AppError:
                if skip_bad_dates:
                    continue
                raise
    except AppError as exc:
        raise AppError(code, f"window derivation failed: {exc.message}") from exc
    except Exception as exc:
        raise AppError(code, f"window derivation failed: {exc}") from exc
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
        ledger_value = safe_float(row["amount"])
        received_by_bond[row["bond_id"]] = received_by_bond.get(row["bond_id"], 0.0) + ledger_value
        received_by_month[row["month"]] = received_by_month.get(row["month"], 0.0) + ledger_value
    bars = []
    invested_by_month = {}
    for row in bond_rows:
        label = row["company"] or row["name"] or f"Bond {row['id']}"
        invested = safe_float(row["amount"])
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
