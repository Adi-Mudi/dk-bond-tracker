import datetime
import json
import re
import sys
from pathlib import Path

import openpyxl

XLSM_PATH = Path(__file__).resolve().parent.parent / "v5.5_40L_Project_Tracker.xlsm"
MONTH_START_COL = 14
MONTH_SCAN_LIMIT = 300
SUM_COLS = {"G": 7, "K": 11, "L": 12}
MONTH_NAMES = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}


def month_label(value):
    if isinstance(value, datetime.datetime):
        return "%04d-%02d" % (value.year, value.month)
    if isinstance(value, datetime.date):
        return "%04d-%02d" % (value.year, value.month)
    if isinstance(value, str):
        match = re.match(r"^\s*([A-Za-z]{3,9})[\s\-/]+(\d{2,4})\s*$", value)
        if match:
            month = MONTH_NAMES.get(match.group(1)[:3].lower())
            if month:
                year = int(match.group(2))
                if year < 100:
                    year += 2000
                return "%04d-%02d" % (year, month)
    return None


def cell_json(value):
    if isinstance(value, datetime.datetime):
        return value.date().isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return value


def build_headers(ws):
    headers = {}
    for col in range(1, MONTH_START_COL):
        value = ws.cell(row=1, column=col).value
        if value is not None:
            headers[col] = str(value).strip()
    return headers


def find_col(headers, pattern):
    for col, text in sorted(headers.items()):
        if re.search(pattern, text, re.IGNORECASE):
            return col
    return None


def pick_name_col(ws, headers):
    detected = find_col(headers, r"company|name")
    if detected is not None:
        return detected
    for candidate in (1, 2):
        for row in range(2, ws.max_row + 1):
            value = ws.cell(row=row, column=candidate).value
            if value is not None and str(value).strip():
                return candidate
    return None


def collect(ws, rows, col):
    if col is None:
        return []
    return [cell_json(ws.cell(row=row, column=col).value) for row in rows]


def formula_census(wb):
    counts = {}
    for name in wb.sheetnames:
        formula = 0
        static = 0
        for row in wb[name].iter_rows():
            for cell in row:
                value = cell.value
                if isinstance(value, str) and value.startswith("="):
                    formula += 1
                elif value is not None:
                    static += 1
        counts[name] = {"formula": formula, "static": static}
    return counts


def dashboard_cache_state(wb_formula, wb_values):
    formula_cells = []
    for row in wb_formula["Dashboard"].iter_rows():
        for cell in row:
            if (
                isinstance(cell.value, str)
                and cell.value.startswith("=")
                and re.search(r"COUNTA|COUNTIF|SUM", cell.value, re.IGNORECASE)
            ):
                formula_cells.append(cell.coordinate)
    if not formula_cells:
        return False
    values = wb_values["Dashboard"]
    return all(values[coord].value is not None for coord in formula_cells)


def main():
    errors = []
    result = {
        "sheets": [],
        "bond_count": 0,
        "bond_names": [],
        "months": {"first": None, "last": None, "count": 0},
        "sums": {"G": None, "K": None, "L": None},
        "none_cells": 0,
        "formula_counts": {},
        "dashboard_cached": False,
        "errors": errors,
        "bond_rows": [],
        "isins": [],
        "statuses": [],
        "tenure_months": [],
        "start_months": [],
        "column_map": {},
        "month_grid": {"start_col": MONTH_START_COL, "first_data_col": None, "last_data_col": None, "trailing_empty_header_cells": 0},
    }
    try:
        wb_values = openpyxl.load_workbook(XLSM_PATH, data_only=True)
        wb_formula = openpyxl.load_workbook(XLSM_PATH, data_only=False)
        result["sheets"] = list(wb_formula.sheetnames)
        if "Monthly Returns" not in wb_formula.sheetnames:
            raise RuntimeError("sheet 'Monthly Returns' not found: %r" % (wb_formula.sheetnames,))
        if "Dashboard" not in wb_formula.sheetnames:
            raise RuntimeError("sheet 'Dashboard' not found: %r" % (wb_formula.sheetnames,))
        mr_values = wb_values["Monthly Returns"]
        mr_formula = wb_formula["Monthly Returns"]
        headers = build_headers(mr_formula)
        name_col = pick_name_col(mr_formula, headers)
        isin_col = find_col(headers, r"isn|isin")
        status_col = find_col(headers, r"status")
        tenure_col = find_col(headers, r"tenure")
        start_col = find_col(headers, r"start")
        result["column_map"] = {
            "name": {"col": name_col, "header": headers.get(name_col)},
            "isin": {"col": isin_col, "header": headers.get(isin_col)},
            "status": {"col": status_col, "header": headers.get(status_col)},
            "tenure": {"col": tenure_col, "header": headers.get(tenure_col)},
            "start_month": {"col": start_col, "header": headers.get(start_col)},
        }
        if name_col is None:
            raise RuntimeError("no bond-name column detected in Monthly Returns header row")
        rows = []
        for row in range(2, mr_formula.max_row + 1):
            value = mr_formula.cell(row=row, column=name_col).value
            if value is not None and str(value).strip():
                rows.append(row)
        result["bond_rows"] = rows
        result["bond_names"] = [str(mr_formula.cell(row=row, column=name_col).value).strip() for row in rows]
        result["bond_count"] = len(rows)
        result["isins"] = collect(mr_formula, rows, isin_col)
        result["statuses"] = collect(mr_formula, rows, status_col)
        result["tenure_months"] = collect(mr_formula, rows, tenure_col)
        result["start_months"] = collect(mr_formula, rows, start_col)
        sheet_max_col = mr_values.max_column
        month_cells = []
        for col in range(MONTH_START_COL, MONTH_SCAN_LIMIT + 1):
            label = month_label(mr_values.cell(row=1, column=col).value)
            if label is None:
                label = month_label(mr_formula.cell(row=1, column=col).value)
            if label is not None:
                month_cells.append((col, label))
        if month_cells:
            result["months"] = {
                "first": month_cells[0][1],
                "last": month_cells[-1][1],
                "count": len(month_cells),
            }
            result["month_grid"]["first_data_col"] = month_cells[0][0]
            result["month_grid"]["last_data_col"] = month_cells[-1][0]
            trailing = 0
            for col in range(month_cells[-1][0] + 1, min(sheet_max_col, MONTH_SCAN_LIMIT) + 1):
                if mr_values.cell(row=1, column=col).value is None:
                    trailing += 1
                else:
                    break
            result["month_grid"]["trailing_empty_header_cells"] = trailing
        else:
            errors.append("no month header cells parsed in row 1 from column %d" % MONTH_START_COL)
        sums = {}
        none_cells = 0
        for key, col in SUM_COLS.items():
            total = 0.0
            for row in rows:
                value = mr_values.cell(row=row, column=col).value
                if value is None:
                    none_cells += 1
                elif isinstance(value, (int, float)) and not isinstance(value, bool):
                    total += float(value)
                else:
                    errors.append("non-numeric value in %s%d: %r" % (key, row, value))
            sums[key] = round(total, 2)
        result["sums"] = sums
        result["none_cells"] = none_cells
        result["formula_counts"] = formula_census(wb_formula)
        result["dashboard_cached"] = dashboard_cache_state(wb_formula, wb_values)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as exc:
        errors.append("%s: %s" % (type(exc).__name__, exc))
        print(json.dumps(result, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
