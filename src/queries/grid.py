import calendar

from . import _resolve_today
from ..engine import sort_rows
from ..status import compute_row_status_daywise, month_key, tenure_month_map
from ..validators import AppError, add_months, parse_date_value
from .summary import _month_keys_span, status_overview


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
    model_rows = sort_rows(model_rows)
    return {
        "months": headers,
        "rows": model_rows,
        "current": current,
        "bond_count": len(model_rows),
    }


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
