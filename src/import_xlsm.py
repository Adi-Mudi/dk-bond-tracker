from dataclasses import dataclass
from pathlib import Path

import openpyxl

from .validators import AppError


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
