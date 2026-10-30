import csv
import io

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.export_csv import LEDGER_HEADERS, current_view_csv, full_ledger_csv
from src.validators import AppError

NASTY_COMPANY = 'Acme, "Beta" Ltd\nSecond Line'


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_nasty(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, NASTY_COMPANY, "INE0000000291", "2026-07-01", 6)
        add_payment(conn, bond_id, "2026-08", 1500.0)


def parse(text):
    return list(csv.reader(io.StringIO(text, newline="")))


def test_tc29_current_view_roundtrips_commas_quotes_newlines():
    rows = [
        {
            "bond": NASTY_COMPANY,
            "isin": "INE0000000291",
            "month": "2026-10",
            "amount": 1500.0,
            "paid": 1,
            "status": "On-going",
        },
        {
            "bond": "Plain Co",
            "isin": "INE0000000292",
            "month": "2026-10",
            "amount": 0.0,
            "paid": 0,
            "status": "Danger",
        },
    ]
    text = current_view_csv(rows, headers=list(LEDGER_HEADERS))
    parsed = parse(text)
    assert parsed[0] == ["bond", "isin", "month", "amount", "paid", "status"]
    assert parsed[1][0] == NASTY_COMPANY
    assert parsed[1][3] == "1500.00"
    assert parsed[1][4] == "1"
    assert parsed[2][0] == "Plain Co"
    assert parsed[2][4] == "0"


def test_tc29_full_ledger_roundtrips_special_company(db_path):
    seed_nasty(db_path)
    with get_conn(db_path) as conn:
        text = full_ledger_csv(conn)
    parsed = parse(text)
    assert parsed[0] == ["bond", "isin", "month", "amount", "paid", "status"]
    assert parsed[1][0] == NASTY_COMPANY
    assert parsed[1][2] == "2026-08"
    assert float(parsed[1][3]) == 1500.0
    assert int(parsed[1][4]) == 1


def test_tc29_records_separated_by_crlf_no_bare_lf():
    rows = [
        {"bond": "Alpha Co", "isin": "INE0000000293", "month": "2026-10", "amount": 1.0, "paid": 1, "status": "On-going"},
        {"bond": "Beta Co", "isin": "INE0000000294", "month": "2026-10", "amount": 2.5, "paid": 0, "status": "Danger"},
    ]
    text = current_view_csv(rows, headers=list(LEDGER_HEADERS))
    assert text.endswith("\r\n")
    remainder = text.replace("\r\n", "")
    assert "\n" not in remainder
    assert "\r" not in remainder
    assert text.count("\r\n") == 3


def test_tc29_exact_header_rows(db_path):
    seed_nasty(db_path)
    with get_conn(db_path) as conn:
        full_text = full_ledger_csv(conn)
    assert full_text.split("\r\n")[0] == "bond,isin,month,amount,paid,status"
    rows = [
        {"bond": "X", "isin": "Y", "month": "2026-10", "amount": 0.0, "paid": 0, "status": "Danger"}
    ]
    view_text = current_view_csv(rows)
    assert view_text.split("\r\n")[0] == "bond,isin,month,amount,paid,status"


def test_tc29_quoted_field_uses_doubled_quotes():
    rows = [{"bond": 'Say "hi", now', "isin": "INE0000000295", "month": "2026-10", "amount": 3.0, "paid": 1, "status": "On-going"}]
    text = current_view_csv(rows, headers=list(LEDGER_HEADERS))
    assert '"Say ""hi"", now"' in text
    assert parse(text)[1][0] == 'Say "hi", now'


def test_tc29_route_export_roundtrips_special_company(client, db_path):
    seed_nasty(db_path)
    response = client.get("/export.csv?scope=full")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    parsed = parse(text)
    assert parsed[0] == ["bond", "isin", "month", "amount", "paid", "status"]
    assert parsed[1][0] == NASTY_COMPANY


def test_tc29_current_view_csv_rejects_missing_rows():
    with pytest.raises(AppError) as exc_info:
        current_view_csv(None)
    assert exc_info.value.code == "ERR-export-view"


def test_tc29_current_view_csv_empty_without_headers_rejected():
    with pytest.raises(AppError) as exc_info:
        current_view_csv([])
    assert exc_info.value.code == "ERR-export-view"
