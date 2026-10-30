import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import openpyxl

from .db import get_conn, init_db
from .validators import AppError, header_key, legacy_position

BOND_SHEET_TITLE = "Monthly Returns"
HOME_PLAN_SHEET_TITLE = "Home Plan"
WATCH_LIST_SHEET_TITLE = "Bond - Watch list"
FIRST_DATA_ROW = 2
MONTH_HEADER_START_COL = 14
MASTER_FIELDS = (
    "company",
    "isin",
    "status",
    "tenure_months",
    "start_month",
    "investment",
    "maturity",
)
WATCH_DETAIL_FIELDS = (
    "status",
    "broker",
    "yield",
    "rating",
    "face_value",
    "investment",
    "tlp_amount",
    "payment_type",
    "tenure_months",
    "discount_amount",
    "interest_payout",
    "total_amount",
    "qty",
)
DEFAULT_BASELINE = {
    "prd": {"investment": 1037142.01, "till_return": 111638.57, "balance": -925503.44},
    "workbook": {"investment": 1037142.01, "till_return": 56227.88, "balance": -1165738.34},
}


@dataclass(frozen=True)
class OpenedWorkbook:
    values: openpyxl.Workbook
    formulas: openpyxl.Workbook


def open_workbook(path):
    source = Path(path)
    if not source.is_file():
        raise AppError("ERR-workbook-open", f"workbook not found: {source}")
    try:
        values = openpyxl.load_workbook(source, read_only=True, data_only=True)
        formulas = openpyxl.load_workbook(source, read_only=True, data_only=False)
    except Exception as exc:
        raise AppError(
            "ERR-workbook-open",
            f"cannot open workbook {source}: {exc}",
        ) from exc
    return OpenedWorkbook(values=values, formulas=formulas)


def normalize_sheets(wb):
    return {name.strip(): name for name in wb.sheetnames}


def locate_sheet(wb, title):
    mapping = normalize_sheets(wb)
    key = str(title).strip()
    if key not in mapping:
        raise AppError("SHEET_NOT_FOUND", f"sheet not found: {title}")
    return mapping[key]


def is_blank(value):
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    return False


def cell_at(row, column):
    index = column - 1
    if index < 0 or index >= len(row):
        return None
    return row[index]


def detect_columns(ws_values):
    columns = {}
    header = next(ws_values.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header is None:
        return columns
    for index, value in enumerate(header, start=1):
        if not isinstance(value, str):
            continue
        key = header_key(value)
        if not key:
            continue
        if "status" in key or "staus" in key:
            columns.setdefault("status", index)
        elif key in ("isn", "isin") or key.startswith("isin"):
            columns.setdefault("isin", index)
        elif "company" in key:
            columns.setdefault("company", index)
        elif "tenure" in key:
            columns.setdefault("tenure_months", index)
        elif ("principle" in key or "principal" in key) and "amount" in key:
            columns.setdefault("investment", index)
        elif "maturity" in key and "amount" in key:
            columns.setdefault("maturity", index)
        elif ("start" in key or "begin" in key) and "month" in key:
            columns.setdefault("start_month", index)
    return columns


def parse_month_header(value):
    if isinstance(value, (datetime, date)):
        return f"{value.year:04d}-{value.month:02d}"
    if isinstance(value, str):
        text = value.strip()
        for pattern in ("%b-%y", "%b-%Y", "%Y-%m", "%Y-%m-%d"):
            try:
                parsed = datetime.strptime(text, pattern)
            except ValueError:
                continue
            return f"{parsed.year:04d}-{parsed.month:02d}"
    raise AppError("ERR-extract-grid", f"unparseable month header: {value!r}")


def to_float(value, field, row_number):
    if isinstance(value, bool):
        raise AppError("ERR-extract-masters", f"row {row_number}: unparseable {field}: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("₹", "")
        if text:
            try:
                return float(text)
            except ValueError:
                raise AppError(
                    "ERR-extract-masters", f"row {row_number}: unparseable {field}: {value!r}"
                ) from None
    raise AppError("ERR-extract-masters", f"row {row_number}: unparseable {field}: {value!r}")


def to_int(value, field, row_number):
    number = to_float(value, field, row_number)
    if not number.is_integer():
        raise AppError("ERR-extract-masters", f"row {row_number}: non-integer {field}: {value!r}")
    return int(number)


def coerce_amount(value, row_number, month):
    if value is None:
        return None
    if isinstance(value, bool):
        raise AppError("ERR-extract-grid", f"row {row_number}: non-numeric amount for {month}: {value!r}")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        negative = text.startswith("(") and text.endswith(")")
        if negative:
            text = text[1:-1]
        text = text.replace(",", "").replace("₹", "").replace(" ", "")
        try:
            amount = float(text)
        except ValueError:
            raise AppError(
                "ERR-extract-grid",
                f"row {row_number}: non-numeric amount for {month}: {value!r}",
            ) from None
        return -amount if negative else amount
    raise AppError("ERR-extract-grid", f"row {row_number}: non-numeric amount for {month}: {value!r}")


def extract_bond_master(ws_values, ws_formulas):
    columns = detect_columns(ws_values)
    missing = [field for field in MASTER_FIELDS if field not in columns]
    if missing:
        raise AppError("ERR-extract-masters", f"header keywords not detected: {', '.join(missing)}")
    bonds = []
    for offset, row in enumerate(ws_values.iter_rows(min_row=FIRST_DATA_ROW, values_only=True)):
        row_number = FIRST_DATA_ROW + offset
        if is_blank(cell_at(row, columns["company"])) and is_blank(cell_at(row, columns["isin"])):
            break
        record = {"row": row_number}
        for field in MASTER_FIELDS:
            value = cell_at(row, columns[field])
            if is_blank(value):
                raise AppError("ERR-extract-masters", f"row {row_number}: missing {field}")
            if field == "tenure_months":
                record[field] = to_int(value, field, row_number)
            elif field in ("investment", "maturity"):
                record[field] = to_float(value, field, row_number)
            else:
                record[field] = value
        bonds.append(record)
    return bonds


def extract_payment_grid(ws_values):
    columns = detect_columns(ws_values)
    key_fields = [field for field in ("company", "isin") if field in columns]
    if not key_fields:
        raise AppError("ERR-extract-grid", "row-1 key headers not detected: company, isin")
    header = next(ws_values.iter_rows(min_row=1, max_row=1, values_only=True), ())
    months = []
    month_columns = []
    for column in range(MONTH_HEADER_START_COL, len(header) + 1):
        value = header[column - 1]
        if is_blank(value):
            break
        months.append(parse_month_header(value))
        month_columns.append(column)
    if not months:
        raise AppError(
            "ERR-extract-grid",
            f"month grid empty: no date headers from column {MONTH_HEADER_START_COL}",
        )
    cells = []
    for offset, row in enumerate(ws_values.iter_rows(min_row=FIRST_DATA_ROW, values_only=True)):
        if all(is_blank(cell_at(row, columns[field])) for field in key_fields):
            break
        cells.append(
            {
                months[index]: coerce_amount(
                    cell_at(row, month_columns[index]),
                    FIRST_DATA_ROW + offset,
                    months[index],
                )
                for index in range(len(months))
            }
        )
    return months, cells


def detect_home_columns(header):
    columns = {}
    if header is None:
        return columns
    for index, value in enumerate(header, start=1):
        if not isinstance(value, str):
            continue
        key = header_key(value)
        if not key:
            continue
        if key == "month":
            columns.setdefault("label", index)
        elif "saving" in key:
            columns.setdefault("amount", index)
    return columns


def home_amount(value):
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("₹", "")
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
    return None


def extract_home_plan(ws_values):
    header = next(ws_values.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header is None or all(is_blank(value) for value in header):
        return []
    columns = detect_home_columns(header)
    missing = [field for field in ("label", "amount") if field not in columns]
    if missing:
        raise AppError(
            "ERR-extract-homeplan", f"header keywords not detected: {', '.join(missing)}"
        )
    rows = []
    for offset, row in enumerate(ws_values.iter_rows(min_row=FIRST_DATA_ROW, values_only=True)):
        row_number = FIRST_DATA_ROW + offset
        label = cell_at(row, columns["label"])
        if is_blank(label):
            continue
        if header_key(str(label)) in ("totall", "total", "grandtotal", "sum"):
            continue
        raw_amount = cell_at(row, columns["amount"])
        if is_blank(raw_amount):
            continue
        amount = home_amount(raw_amount)
        if amount is None:
            raise AppError(
                "ERR-extract-homeplan", f"row {row_number}: unparseable saving: {raw_amount!r}"
            )
        rows.append({"label": label, "amount": amount})
    return rows


def detect_watch_columns(header):
    columns = {}
    if header is None:
        return columns
    for index, value in enumerate(header, start=1):
        if not isinstance(value, str):
            continue
        key = header_key(value)
        if not key:
            continue
        if "status" in key or "staus" in key:
            columns.setdefault("status", index)
        elif key in ("isn", "isin") or key.startswith("isin"):
            columns.setdefault("isin", index)
        elif "company" in key:
            columns.setdefault("company", index)
        elif "broker" in key:
            columns.setdefault("broker", index)
        elif "yeild" in key or "yield" in key:
            columns.setdefault("yield", index)
        elif "rating" in key:
            columns.setdefault("rating", index)
        elif "face" in key and "value" in key:
            columns.setdefault("face_value", index)
        elif "discount" in key and "amount" in key:
            columns.setdefault("discount_amount", index)
        elif ("principle" in key or "principal" in key) and "amount" in key:
            columns.setdefault("investment", index)
        elif "tlp" in key:
            columns.setdefault("tlp_amount", index)
        elif "payment" in key and "type" in key:
            columns.setdefault("payment_type", index)
        elif "month" in key and ("no" in key or "number" in key):
            columns.setdefault("tenure_months", index)
        elif "interest" in key:
            columns.setdefault("interest_payout", index)
        elif "total" in key and "amount" in key:
            columns.setdefault("total_amount", index)
        elif key in ("qty", "quantity") or key.startswith("qty"):
            columns.setdefault("qty", index)
    return columns


def extract_watch_list(ws_values):
    header = next(ws_values.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if header is None or all(is_blank(value) for value in header):
        raise AppError("ERR-extract-watchlist", "sheet has no header row")
    columns = detect_watch_columns(header)
    missing = [field for field in ("company", "isin") if field not in columns]
    if missing:
        raise AppError(
            "ERR-extract-watchlist", f"header keywords not detected: {', '.join(missing)}"
        )
    rows = []
    for offset, row in enumerate(ws_values.iter_rows(min_row=FIRST_DATA_ROW, values_only=True)):
        row_number = FIRST_DATA_ROW + offset
        company = cell_at(row, columns["company"])
        isin = cell_at(row, columns["isin"])
        if is_blank(company) and is_blank(isin):
            break
        record = {"row": row_number, "company": company, "isin": isin}
        for field in WATCH_DETAIL_FIELDS:
            if field in columns:
                record[field] = cell_at(row, columns[field])
        rows.append(record)
    if not rows:
        raise AppError("ERR-extract-watchlist", "no bond rows found")
    return rows


def normalize_isin_set(items, field):
    result = set()
    for item in items:
        raw = item.get(field)
        if is_blank(raw):
            continue
        result.add(str(raw).strip().upper())
    return result


def validate_watch_vs_master(watch, bonds):
    watch_isins = normalize_isin_set(watch, "isin")
    master_isins = normalize_isin_set(bonds, "isin")
    if watch_isins != master_isins:
        missing = sorted(master_isins - watch_isins)
        extra = sorted(watch_isins - master_isins)
        raise AppError(
            "ERR-watch-mismatch",
            f"watch-list ISIN set differs from master: missing={missing} extra={extra}",
        )
    return {"matched": len(watch_isins)}


def validate_watch_analytics_inputs(watch):
    required = ("face_value", "interest_payout", "investment")
    for record in watch:
        missing = [field for field in required if is_blank(record.get(field))]
        if missing:
            raise AppError(
                "ERR-watch-analytics",
                f"bond {record.get('isin') or record.get('company')!r} "
                f"row {record.get('row')}: missing watch input {', '.join(missing)}",
            )
    return {"checked": len(watch)}


def recompute_kl(row_cells, maturity_j):
    if maturity_j is None:
        raise AppError("ERR-extract-masters", "maturity amount missing for K/L recompute")
    k_sum = sum(value for value in row_cells.values() if value is not None)
    return k_sum, k_sum - float(maturity_j)


def find_duplicate_isins(bonds):
    if bonds is None:
        raise AppError("ERR-duplicate-check", "bond set unavailable")
    grouped = {}
    for position, bond in enumerate(bonds):
        raw = bond.get("isin")
        if is_blank(raw):
            continue
        key = str(raw).strip().upper()
        entry = grouped.setdefault(key, {"rows": [], "values": []})
        entry["rows"].append(bond.get("row", position + FIRST_DATA_ROW))
        entry["values"].append(raw)
    duplicates = []
    for key, entry in grouped.items():
        if len(entry["rows"]) > 1:
            duplicates.append({"isin": key, "occurrences": entry["rows"], "values": entry["values"]})
    return duplicates


def validate_extracted(bonds, grid):
    duplicates = find_duplicate_isins(bonds)
    if duplicates:
        details = []
        for duplicate in duplicates:
            rows = ", ".join(str(row) for row in duplicate["occurrences"])
            values = ", ".join(repr(value) for value in duplicate["values"])
            details.append(f"{duplicate['isin']} at rows {rows} (values: {values})")
        raise AppError("ERR-04", "duplicate ISIN: " + "; ".join(details))
    for position, bond in enumerate(bonds):
        missing = [field for field in MASTER_FIELDS if is_blank(bond.get(field))]
        if missing:
            row_number = bond.get("row", position + FIRST_DATA_ROW)
            raise AppError("ERR-05", f"row {row_number}: missing {', '.join(missing)}")
    if len(grid) != len(bonds):
        raise AppError("ERR-05", f"grid rows {len(grid)} != bond rows {len(bonds)}")


def reconcile(bonds, k_values, baseline):
    if not baseline or not isinstance(baseline, dict):
        raise AppError("ERR-reconcile-baseline", "baseline figures missing")
    if k_values is None or len(k_values) != len(bonds):
        raise AppError(
            "ERR-reconcile-inputs",
            f"k_values {0 if k_values is None else len(k_values)} != bonds {len(bonds)}",
        )
    groups = baseline
    if all(not isinstance(figures, dict) for figures in baseline.values()):
        groups = {"given": baseline}
    computed = {
        "bond_count": len(bonds),
        "investment": round(sum(float(bond["investment"]) for bond in bonds), 2),
        "till_return": round(sum(float(value) for value in k_values), 2),
        "balance": round(
            sum(float(value) for value in k_values)
            - sum(float(bond["maturity"]) for bond in bonds),
            2,
        ),
    }
    match_flags = {}
    deltas = {}
    for group_name, figures in groups.items():
        for measure, target in figures.items():
            if measure not in computed:
                raise AppError("ERR-reconcile-baseline", f"unknown baseline measure: {measure}")
            delta = round(computed[measure] - float(target), 2)
            flag = f"{measure}_vs_{group_name}"
            deltas[flag] = delta
            match_flags[flag] = delta == 0
    return {
        "l1_status": "PENDING_BASELINE",
        "computed": computed,
        "baselines": groups,
        "match_flags": match_flags,
        "deltas": deltas,
        "mismatch_deltas": {flag: value for flag, value in deltas.items() if not match_flags[flag]},
        "balance_definition": (
            "workbook L = K - J (maturity amount) vs PRD Balance = Till Return - Total Investment"
        ),
    }


def _watch_number(record, field):
    value = record.get(field)
    if is_blank(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("₹", "")
        if text:
            try:
                return float(text)
            except ValueError:
                return None
    return None


def _watch_text(record, field):
    value = record.get(field)
    if is_blank(value):
        return None
    return str(value).strip()


def commit_import(db_path, bonds, grid, home_plan=(), watch=()):
    if len(bonds) != len(grid):
        raise AppError("ERR-commit-import", f"bond rows {len(bonds)} != grid rows {len(grid)}")
    watch_by_isin = {}
    for record in watch:
        raw = record.get("isin")
        if not is_blank(raw):
            watch_by_isin[str(raw).strip().upper()] = record
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    init_db(db_path)
    ledger_rows = 0
    goals = 0
    try:
        with get_conn(db_path) as conn:
            conn.execute("BEGIN")
            for bond, cells in zip(bonds, grid):
                start, end, tenure, credit = legacy_position(
                    bond["start_month"], bond["tenure_months"]
                )
                watch_record = watch_by_isin.get(str(bond["isin"]).strip().upper(), {})
                cursor = conn.execute(
                    "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
                    "tenure_months, credit_day, status, face_value, tlp_amount, payment_type, "
                    "interest_payout, qty, watch_investment) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        bond["company"],
                        bond["isin"],
                        bond["company"],
                        float(bond["investment"]),
                        float(bond["maturity"]),
                        start.isoformat(),
                        end.isoformat(),
                        tenure,
                        credit,
                        bond["status"],
                        _watch_number(watch_record, "face_value"),
                        _watch_number(watch_record, "tlp_amount"),
                        _watch_text(watch_record, "payment_type"),
                        _watch_number(watch_record, "interest_payout"),
                        _watch_number(watch_record, "qty"),
                        _watch_number(watch_record, "investment"),
                    ),
                )
                bond_id = cursor.lastrowid
                for month, value in cells.items():
                    if value is not None and value > 0:
                        conn.execute(
                            "INSERT INTO payment_ledger (bond_id, month, amount, paid) "
                            "VALUES (?, ?, ?, 1)",
                            (bond_id, month, float(value)),
                        )
                        ledger_rows += 1
            for entry in home_plan:
                conn.execute(
                    "INSERT INTO financial_goals (name, target_amount, target_end_date, note) "
                    "VALUES (?, ?, NULL, ?)",
                    (str(entry["label"]), float(entry["amount"]), "legacy home plan"),
                )
                goals += 1
            conn.commit()
    except AppError:
        raise
    except sqlite3.Error as exc:
        raise AppError("ERR-commit-import", f"import commit failed: {exc}") from exc
    return {"bonds": len(bonds), "ledger_rows": ledger_rows, "goals": goals}


def import_workbook(path, db_path):
    workbook = open_workbook(path)
    try:
        values_sheet = locate_sheet(workbook.values, BOND_SHEET_TITLE)
        formulas_sheet = locate_sheet(workbook.formulas, BOND_SHEET_TITLE)
        bonds = extract_bond_master(
            workbook.values[values_sheet], workbook.formulas[formulas_sheet]
        )
        months, grid = extract_payment_grid(workbook.values[values_sheet])
        validate_extracted(bonds, grid)
        home_values_sheet = locate_sheet(workbook.values, HOME_PLAN_SHEET_TITLE)
        watch_values_sheet = locate_sheet(workbook.values, WATCH_LIST_SHEET_TITLE)
        home_plan = extract_home_plan(workbook.values[home_values_sheet])
        watch_rows = extract_watch_list(workbook.values[watch_values_sheet])
        validate_watch_vs_master(watch_rows, bonds)
        validate_watch_analytics_inputs(watch_rows)
        k_values = [
            recompute_kl(cells, bond["maturity"])[0] for bond, cells in zip(bonds, grid)
        ]
        report = reconcile(bonds, k_values, DEFAULT_BASELINE)
        counts = commit_import(db_path, bonds, grid, home_plan, watch_rows)
    finally:
        workbook.values.close()
        workbook.formulas.close()
    return {
        "bonds": len(bonds),
        "months": len(months),
        "ledger_rows": counts["ledger_rows"],
        "goals": counts["goals"],
        "reconcile": report,
    }
