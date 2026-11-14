import csv
import io

from .export_csv import BACKUP_BOND_HEADERS, BACKUP_GOAL_HEADERS, BACKUP_PAYMENT_HEADERS
from .validators import AppError, parse_date_value

MAX_IMPORT_BYTES = 5 * 1024 * 1024


def _sections(text):
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    sections = {}
    current = None
    expected = None
    for number, row in enumerate(rows, start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if row[0] == "section":
            if len(row) != 2 or row[1] not in ("bonds", "payments", "goals"):
                raise AppError("ERR-import-format", f"unknown section marker on row {number}")
            current = row[1]
            expected = {"bonds": BACKUP_BOND_HEADERS, "payments": BACKUP_PAYMENT_HEADERS, "goals": BACKUP_GOAL_HEADERS}[current]
            sections[current] = {"header_row": number, "header": None, "rows": []}
            continue
        if current is None:
            raise AppError("ERR-import-format", f"data before any section marker on row {number}")
        target = sections[current]
        if target["header"] is None:
            header = [cell.strip() for cell in row]
            for name in expected:
                if name not in header:
                    raise AppError("ERR-import-columns", f"missing required column '{name}' in {current} section")
            for name in header:
                if name not in expected:
                    raise AppError("ERR-import-columns", f"unknown column '{name}' in {current} section")
            target["header"] = header
            continue
        if len(row) != len(target["header"]):
            raise AppError("ERR-import-row", f"row {number} has {len(row)} cells, expected {len(target['header'])}")
        target["rows"].append((number, dict(zip(target["header"], [cell.strip() for cell in row]))))
    for name in ("bonds", "payments", "goals"):
        if name not in sections or sections[name]["header"] is None:
            raise AppError("ERR-import-format", f"missing {name} section")
    return sections


def _parse_float(value, field, number):
    try:
        return float(value) if value != "" else None
    except ValueError as exc:
        raise AppError("ERR-import-row", f"row {number}: {field} is not a number: {value!r}") from exc


def _parse_int(value, field, number):
    try:
        return int(value) if value != "" else None
    except ValueError as exc:
        raise AppError("ERR-import-row", f"row {number}: {field} is not an integer: {value!r}") from exc


def _validate(sections):
    bonds = []
    seen_rows = {}
    for number, record in sections["bonds"]["rows"]:
        isin = record["isin"]
        if not isin:
            raise AppError("ERR-import-row", f"row {number}: isin is required")
        seen_rows.setdefault(isin, []).append(number)
        for field in ("start_date", "end_date"):
            try:
                parse_date_value(record[field], field)
            except AppError as exc:
                raise AppError("ERR-import-row", f"row {number}: {exc.message}") from exc
        bonds.append(
            (
                isin,
                record["company"],
                record["name"],
                _parse_float(record["amount"], "amount", number),
                _parse_float(record["maturity"], "maturity", number),
                record["start_date"],
                record["end_date"],
                _parse_int(record["tenure_months"], "tenure_months", number),
                _parse_int(record["credit_day"], "credit_day", number),
                record["status"] or "On-going",
            )
        )
    isins = {bond[0] for bond in bonds}
    if len(isins) != len(bonds):
        detail = "; ".join(
            f"{isin} on rows {', '.join(str(n) for n in rows)}"
            for isin, rows in seen_rows.items()
            if len(rows) > 1
        )
        raise AppError("ERR-import-row", f"duplicate isin in bonds section: {detail}")
    payments = []
    for number, record in sections["payments"]["rows"]:
        if record["isin"] not in isins:
            raise AppError("ERR-import-row", f"row {number}: isin {record['isin']!r} has no bond row")
        try:
            parse_date_value(record["month"], "month")
        except AppError as exc:
            raise AppError("ERR-import-row", f"row {number}: {exc.message}") from exc
        payments.append(
            (
                record["isin"],
                record["month"],
                _parse_float(record["amount"], "amount", number),
                _parse_int(record["paid"], "paid", number) or 0,
                _parse_int(record["tds_applied"], "tds_applied", number) if record["tds_applied"] != "" else 1,
            )
        )
    goals = []
    for number, record in sections["goals"]["rows"]:
        goals.append(
            (
                record["name"],
                _parse_float(record["target_amount"], "target_amount", number),
                record["target_end_date"],
                record["note"],
                _parse_float(record["saved_amount"], "saved_amount", number) or 0.0,
            )
        )
    return bonds, payments, goals


def import_backup_csv(conn, text):
    if len(text.encode("utf-8")) > MAX_IMPORT_BYTES:
        raise AppError("ERR-import-size", "backup file is too large")
    sections = _sections(text)
    bonds, payments, goals = _validate(sections)
    existing = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    if existing:
        raise AppError(
            "ERR-import-exists",
            "this backup is already restored: the database already holds ledger rows",
        )
    counts = {"bonds": 0, "payments": 0, "goals": 0}
    try:
        conn.execute("BEGIN")
        isin_to_id = {}
        for bond in bonds:
            cursor = conn.execute(
                "INSERT INTO bonds (isin, company, name, amount, maturity, start_date, end_date, "
                "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                bond,
            )
            isin_to_id[bond[0]] = cursor.lastrowid
            counts["bonds"] += 1
        for isin, month, amount, paid, tds in payments:
            conn.execute(
                "INSERT INTO payment_ledger (bond_id, month, amount, paid, tds_applied) VALUES (?, ?, ?, ?, ?)",
                (isin_to_id[isin], month, amount, paid, tds),
            )
            counts["payments"] += 1
        for goal in goals:
            conn.execute(
                "INSERT INTO financial_goals (name, target_amount, target_end_date, note, saved_amount) "
                "VALUES (?, ?, ?, ?, ?)",
                goal,
            )
            counts["goals"] += 1
        conn.execute("COMMIT")
    except AppError:
        conn.execute("ROLLBACK")
        raise
    except Exception as exc:
        conn.execute("ROLLBACK")
        raise AppError("ERR-import-write", f"restore failed, ledger unchanged: {exc}") from exc
    return counts
