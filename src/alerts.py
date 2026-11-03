from datetime import date

from .status import credit_day_overdue, tenure_month_map
from .validators import AppError, validate_credit_day


def daily_sweep(conn, today):
    if not isinstance(today, date):
        raise AppError("ERR-credit-sweep", f"today must be a date: {today!r}")
    events = []
    current_month = f"{today.year:04d}-{today.month:02d}"
    rows = conn.execute(
        "SELECT id, company, start_date, tenure_months, credit_day, status FROM bonds ORDER BY id"
    ).fetchall()
    for row in rows:
        if row["status"] == "Completed":
            continue
        credit_day = validate_credit_day(row["credit_day"], "ERR-credit-sweep", context=f"bond {row['id']}")
        try:
            months = tenure_month_map(conn, row["id"], row["start_date"], row["tenure_months"])
        except AppError as exc:
            raise AppError("ERR-credit-sweep", f"bond {row['id']}: {exc.message}") from exc
        if not credit_day_overdue(months, row["tenure_months"], credit_day, today):
            continue
        conn.execute("UPDATE bonds SET status = ? WHERE id = ?", ("Danger", row["id"]))
        events.append(
            {
                "bond_id": row["id"],
                "company": row["company"],
                "month": current_month,
                "credit_day": credit_day,
                "severity": "danger",
            }
        )
    return events
