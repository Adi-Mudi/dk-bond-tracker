import csv
import io
from datetime import date

from .queries import status_overview
from .validators import AppError

LEDGER_HEADERS = ("bond", "isin", "month", "amount", "paid", "status")


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return f"{value:.2f}"
    return str(value)


def serialize_records(records):
    buffer = io.StringIO()
    writer = csv.writer(buffer, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
    for record in records:
        writer.writerow(record)
    return buffer.getvalue()


def current_view_csv(rows, headers=None):
    if rows is None:
        raise AppError("ERR-export-view", "current view rows are unavailable")
    material = list(rows)
    if headers is None:
        if not material:
            raise AppError(
                "ERR-export-view",
                "current view has no rows and no headers were supplied",
            )
        first = material[0]
        if not hasattr(first, "keys"):
            raise AppError(
                "ERR-export-view",
                f"current view rows must carry named columns: {type(first).__name__}",
            )
        headers = list(first.keys())
    records = [list(headers)]
    for row in material:
        if hasattr(row, "keys"):
            records.append([_cell(row.get(header)) for header in headers])
        else:
            records.append([_cell(value) for value in row])
    try:
        return serialize_records(records)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-export-view", f"CSV serialization failed: {exc}") from exc


def current_view_rows(conn, month, today=None):
    today_value = today if today is not None else date.today()
    try:
        overview = status_overview(conn, today_value)
        ledger = {
            row["bond_id"]: row
            for row in conn.execute(
                "SELECT bond_id, amount, paid FROM payment_ledger WHERE month = ?",
                (month,),
            ).fetchall()
        }
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-export-view", f"current view query failed: {exc}") from exc
    rows = []
    for entry in overview:
        record = ledger.get(entry["id"])
        rows.append(
            {
                "bond": entry["company"],
                "isin": entry["isin"],
                "month": month,
                "amount": float(record["amount"] or 0.0) if record else 0.0,
                "paid": int(record["paid"] or 0) if record else 0,
                "status": entry["status"],
            }
        )
    return rows


def full_ledger_csv(conn):
    try:
        ledger = conn.execute(
            "SELECT b.company AS bond, b.isin, l.month, l.amount, l.paid, l.bond_id "
            "FROM payment_ledger l JOIN bonds b ON b.id = l.bond_id "
            "ORDER BY l.bond_id, l.month"
        ).fetchall()
        overview = status_overview(conn, date.today())
    except AppError as exc:
        raise AppError("ERR-export-ledger", exc.message) from exc
    except Exception as exc:
        raise AppError("ERR-export-ledger", f"ledger query failed: {exc}") from exc
    status_by_id = {entry["id"]: entry["status"] for entry in overview}
    records = [list(LEDGER_HEADERS)]
    for row in ledger:
        records.append(
            [
                row["bond"],
                row["isin"],
                row["month"],
                _cell(row["amount"]),
                _cell(row["paid"]),
                status_by_id.get(row["bond_id"], ""),
            ]
        )
    try:
        return serialize_records(records)
    except AppError:
        raise
    except Exception as exc:
        raise AppError("ERR-export-ledger", f"CSV serialization failed: {exc}") from exc
