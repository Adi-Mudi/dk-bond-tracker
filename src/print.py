import calendar
from datetime import date

from .engine import HEALTH_ORDER, display_label
from .notifications import list_notifications
from .queries import portfolio_totals, status_overview, summary_counts, this_month_returns
from .status import month_key
from .validators import AppError

STATUS_MARKS = {"Danger": "● D", "On-going": "○ O", "Completed": "● C", "Invalid": "✕ I"}
STATUS_KEYS = {"Danger": "danger", "On-going": "ongoing", "Completed": "completed", "Invalid": "invalid"}
STATUS_ORDER = tuple(sorted(STATUS_MARKS, key=lambda value: HEALTH_ORDER[display_label(value)]))
ALERTS_FOOTER_CAP = 5


def _format_date(value):
    return value.strftime("%d-%b-%Y")


def _month_window(today):
    year, mon = today.year, today.month
    last_day = calendar.monthrange(year, mon)[1]
    start = date(year, mon, 1)
    end = date(year, mon, last_day)
    return start, end


def _expected_amount(conn, bond_id, month):
    row = conn.execute(
        "SELECT amount FROM payment_ledger WHERE bond_id = ? AND month = ?",
        (bond_id, month),
    ).fetchone()
    if row is not None:
        return float(row["amount"] or 0.0)
    prior = conn.execute(
        "SELECT amount FROM payment_ledger "
        "WHERE bond_id = ? AND month < ? AND amount > 0 "
        "ORDER BY month DESC LIMIT 1",
        (bond_id, month),
    ).fetchone()
    if prior is not None:
        return float(prior["amount"] or 0.0)
    return 0.0


def _due_date(today, credit_day):
    return date(today.year, today.month, int(credit_day)).isoformat()


def _last_sweep(conn, today):
    row = conn.execute(
        "SELECT value FROM alert_prefs WHERE key = 'last_sweep'"
    ).fetchone()
    if row is not None and row["value"]:
        return str(row["value"])
    latest = conn.execute(
        "SELECT MAX(created_at) AS stamp FROM notifications"
    ).fetchone()
    if latest is not None and latest["stamp"]:
        return str(latest["stamp"])[:10]
    return today.isoformat()


def _alerts_footer(conn, today, month):
    notifications = list_notifications(conn)
    month_rows = [
        row
        for row in notifications
        if str(row.get("created_at") or "").startswith(month)
    ]
    return {
        "count": len(month_rows),
        "messages": [str(row["message"]) for row in month_rows[:ALERTS_FOOTER_CAP]],
        "last_sweep": _last_sweep(conn, today),
    }


def monthly_print_model(conn, today):
    if not isinstance(today, date):
        raise AppError("ERR-print-statement", f"today must be a date: {today!r}")
    month = month_key(today)
    start, end = _month_window(today)
    try:
        totals = portfolio_totals(conn)
        counts = summary_counts(conn, today)
        month_returns = this_month_returns(conn, today)
        overview = status_overview(conn, today)
        rows = []
        for entry in overview:
            if entry["status"] == "Invalid":
                credit_day = entry["credit_day"]
                rows.append(
                    {
                        "company": entry["company"],
                        "isin": entry["isin"],
                        "credit_day": credit_day if isinstance(credit_day, int) else "—",
                        "due_date": "—",
                        "amount": _expected_amount(conn, entry["id"], month),
                        "status": entry["status"],
                        "mark": STATUS_MARKS[entry["status"]],
                    }
                )
                continue
            rows.append(
                {
                    "company": entry["company"],
                    "isin": entry["isin"],
                    "credit_day": int(entry["credit_day"]),
                    "due_date": _due_date(today, entry["credit_day"]),
                    "amount": _expected_amount(conn, entry["id"], month),
                    "status": entry["status"],
                    "mark": STATUS_MARKS[entry["status"]],
                }
            )
        status_groups = []
        for status in STATUS_ORDER:
            members = [entry for entry in overview if entry["status"] == status]
            status_groups.append(
                {
                    "key": STATUS_KEYS[status],
                    "status": status,
                    "mark": STATUS_MARKS[status],
                    "count": len(members),
                    "members": [
                        f"{entry['company']} ({entry['isin']})" for entry in members
                    ],
                }
            )
        alerts_footer = _alerts_footer(conn, today, month)
    except AppError as exc:
        raise AppError("ERR-print-statement", exc.message) from exc
    except Exception as exc:
        raise AppError("ERR-print-statement", f"section load failed: {exc}") from exc
    return {
        "header": {
            "month": month,
            "month_label": f"{calendar.month_name[today.month]} {today.year}",
            "range": f"{_format_date(start)} – {_format_date(end)}",
            "generated": _format_date(today),
        },
        "summary": {
            "total_bonds": counts["total"],
            "total_investment": totals["total_investment"],
            "till_return": totals["till_return"],
            "balance": totals["balance"],
            "this_month": month_returns["total"] or 0.0,
        },
        "rows": rows,
        "status_groups": status_groups,
        "alerts_footer": alerts_footer,
    }
