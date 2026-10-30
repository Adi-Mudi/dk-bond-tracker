import csv
import io
from datetime import date
from pathlib import Path

import pytest

from conftest import add_bond, add_payment, pay_range
from src.app import create_app
from src.db import get_conn
from src.import_xlsm import import_workbook
from src.validators import add_months

WORKBOOK = Path(
    "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)

LEDGER_HEADERS = ("bond", "isin", "month", "amount", "paid", "status")


@pytest.fixture(scope="module")
def imported_client(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("tc53") / "regression.db"
    summary = import_workbook(WORKBOOK, db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), db_path, summary


def parse_csv(text):
    return list(csv.reader(io.StringIO(text)))


def assert_csv_shape(rows, headers):
    assert rows, "csv has no rows"
    assert tuple(rows[0]) == headers
    width = len(headers)
    for row in rows[1:]:
        assert len(row) == width, f"ragged row: {row!r}"


def test_tc53_full_ledger_csv_parses_cleanly(imported_client):
    client, db_path, summary = imported_client
    response = client.get("/export.csv?scope=full")
    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert "�" not in text
    rows = parse_csv(text)
    assert_csv_shape(rows, LEDGER_HEADERS)
    with get_conn(db_path) as conn:
        ledger_count = conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"]
    assert len(rows) - 1 == ledger_count == summary["ledger_rows"]
    for row in rows[1:]:
        float(row[3])
        assert row[4] in ("0", "1")
        assert row[5] in ("Danger", "On-going", "Completed")


def test_tc53_current_view_csv_matches_grid_and_amounts(imported_client):
    client, db_path, _summary = imported_client
    with get_conn(db_path) as conn:
        month_row = conn.execute(
            "SELECT month, SUM(amount) AS total FROM payment_ledger "
            "WHERE paid = 1 AND amount > 0 GROUP BY month ORDER BY month LIMIT 1"
        ).fetchone()
        assert month_row is not None
        month = month_row["month"]
        expected_total = float(month_row["total"])
        expected_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM bonds"
        ).fetchone()["n"]
    response = client.get(f"/export.csv?scope=current&month={month}")
    assert response.status_code == 200
    rows = parse_csv(response.data.decode("utf-8"))
    assert_csv_shape(rows, LEDGER_HEADERS)
    assert len(rows) - 1 == expected_rows
    month_total = sum(float(row[3]) for row in rows[1:] if row[2] == month and row[4] == "1")
    assert month_total == pytest.approx(expected_total, abs=1e-6)
    for row in rows[1:]:
        assert row[2] == month
        float(row[3])


def test_tc53_csv_amounts_match_database_row_for_row(imported_client):
    client, db_path, _summary = imported_client
    with get_conn(db_path) as conn:
        sample = conn.execute(
            "SELECT b.isin, l.month, l.amount, l.paid FROM payment_ledger l "
            "JOIN bonds b ON b.id = l.bond_id ORDER BY l.bond_id, l.month LIMIT 20"
        ).fetchall()
    response = client.get("/export.csv?scope=full")
    rows = parse_csv(response.data.decode("utf-8"))[1:]
    by_key = {(row[1], row[2]): row for row in rows}
    for record in sample:
        key = (record["isin"], record["month"])
        assert key in by_key
        assert float(by_key[key][3]) == pytest.approx(float(record["amount"]), abs=1e-9)
        assert int(by_key[key][4]) == int(record["paid"])


def test_tc53_share_csv_opens_cleanly(imported_client):
    client, _db_path, _summary = imported_client
    response = client.post(
        "/share/generate",
        data={"format": "csv", "sections": ["totals", "history"], "include_amounts": "on"},
    )
    assert response.status_code == 200
    text = response.data.decode("utf-8")
    assert "�" not in text
    rows = parse_csv(text)
    assert rows


def test_tc53_chain_import_dashboard_grid_watch_still_green(imported_client):
    client, _db_path, summary = imported_client
    assert summary["bonds"] == 15
    for path in ("/", "/grid", "/watch", "/goals", "/print"):
        response = client.get(path)
        assert response.status_code == 200, path


def test_tc53_rupee_columns_survive_round_trip(tmp_path):
    db_path = tmp_path / "tc53_rupee.db"
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    today = date.today()
    base = today.replace(day=1)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Rupee & Co", "INETC53001", base.isoformat(), 6, amount=123456.78)
        add_payment(conn, bond_id, f"{base.year:04d}-{base.month:02d}", 9876.54)
    response = client.get("/export.csv?scope=current")
    text = response.data.decode("utf-8")
    assert "�" not in text
    rows = parse_csv(text)
    assert_csv_shape(rows, LEDGER_HEADERS)
    rupee_row = [row for row in rows[1:] if row[1] == "INETC53001"]
    assert rupee_row
    assert rupee_row[0][3] == "9876.54"
    assert rupee_row[0][0] == "Rupee & Co"
