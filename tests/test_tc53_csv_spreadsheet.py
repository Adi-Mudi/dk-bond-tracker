import csv
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn, init_db


def _seed(db_path):
    init_db(db_path)
    with get_conn(db_path) as conn:
        bid = add_bond(conn, "CSV CO ONE", "INE9000A01011", "2026-01-01", 6, credit_day=5)
        add_payment(conn, bid, "2026-01", 1000.0, paid=1)
        add_payment(conn, bid, "2026-02", 1000.0, paid=0)


def test_tc53_full_export_parses_as_consistent_csv(db_path):
    _seed(db_path)
    app = create_app(str(db_path))
    r = app.test_client().get("/export.csv?scope=full")
    assert r.status_code == 200
    text = r.get_data(as_text=True)
    rows = list(csv.reader(io.StringIO(text)))
    assert len(rows) >= 2, "header plus at least one data row"
    header = rows[0]
    assert [h.strip().lower() for h in header] == [
        "bond",
        "isin",
        "month",
        "amount",
        "paid",
        "status",
    ]
    width = len(header)
    for row in rows:
        assert len(row) == width, f"ragged CSV row: {row!r}"


def test_tc53_export_opens_with_excel_safe_header(db_path):
    _seed(db_path)
    app = create_app(str(db_path))
    r = app.test_client().get("/export.csv?scope=full")
    text = r.get_data(as_text=True)
    assert "CSV CO ONE" in text
    assert text.count('"') % 2 == 0, "quotes must be balanced for spreadsheet import"
