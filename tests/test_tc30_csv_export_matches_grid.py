import csv
import io
from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.export_csv import LEDGER_HEADERS, full_ledger_csv
from src.queries import grid_model
from src.validators import add_months

BOM = b"\xef\xbb\xbf"


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_ledger(db_path, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    with get_conn(db_path) as conn:
        alpha = add_bond(conn, "Alpha Corp", "INE0000000301", add_months(base, -3).isoformat(), 6, amount=100000.0)
        beta = add_bond(conn, "Beta Corp", "INE0000000302", base.isoformat(), 6, amount=50000.0)
        add_payment(conn, alpha, f"{add_months(base, -2).year:04d}-{add_months(base, -2).month:02d}", 1500.0)
        add_payment(conn, alpha, f"{add_months(base, -1).year:04d}-{add_months(base, -1).month:02d}", 1500.0)
        add_payment(conn, alpha, current, 1500.0)
        add_payment(conn, beta, current, 800.0)
        unpaid_month = f"{add_months(base, -1).year:04d}-{add_months(base, -1).month:02d}"
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, 0, 0)",
            (beta, unpaid_month),
        )
    return today


def parse(text):
    return list(csv.reader(io.StringIO(text, newline="")))


def test_tc30_full_ledger_matches_direct_query(db_path):
    today = seed_ledger(db_path, date.today())
    with get_conn(db_path) as conn:
        text = full_ledger_csv(conn)
        direct = conn.execute(
            "SELECT b.company AS bond, b.isin, l.month, l.amount, l.paid "
            "FROM payment_ledger l JOIN bonds b ON b.id = l.bond_id "
            "ORDER BY l.bond_id, l.month"
        ).fetchall()
    rows = parse(text)
    assert rows[0] == list(LEDGER_HEADERS)
    body = rows[1:]
    assert len(body) == len(direct)
    for csv_row, db_row in zip(body, direct):
        assert csv_row[0] == db_row["bond"]
        assert csv_row[1] == db_row["isin"]
        assert csv_row[2] == db_row["month"]
        assert float(csv_row[3]) == float(db_row["amount"])
        assert int(csv_row[4]) == int(db_row["paid"])


def test_tc30_paid_flags_match_grid_model_cells(db_path):
    today = seed_ledger(db_path, date.today())
    with get_conn(db_path) as conn:
        text = full_ledger_csv(conn)
        model = grid_model(conn, today)
    rows = parse(text)[1:]
    cell_state = {}
    status_by_isin = {}
    for model_row in model["rows"]:
        status_by_isin[model_row["isin"]] = model_row["status"]
        for cell in model_row["cells"]:
            cell_state[(model_row["isin"], cell["month"])] = cell["state"]
    for csv_row in rows:
        isin, month, paid = csv_row[1], csv_row[2], int(csv_row[4])
        assert (isin, month) in cell_state, (isin, month)
        state = cell_state[(isin, month)]
        if paid == 1:
            assert float(csv_row[3]) > 0
            assert state == "paid"
        else:
            assert state != "paid"
        assert csv_row[5] == status_by_isin[isin]


def test_tc30_every_paid_grid_cell_has_csv_row(db_path):
    today = seed_ledger(db_path, date.today())
    with get_conn(db_path) as conn:
        text = full_ledger_csv(conn)
        model = grid_model(conn, today)
    csv_paid = {
        (csv_row[1], csv_row[2])
        for csv_row in parse(text)[1:]
        if int(csv_row[4]) == 1
    }
    grid_paid = set()
    for model_row in model["rows"]:
        for cell in model_row["cells"]:
            if cell["state"] == "paid":
                grid_paid.add((model_row["isin"], cell["month"]))
    assert csv_paid == grid_paid


def test_tc30_amount_values_match_grid_paid_month_amounts(db_path):
    today = seed_ledger(db_path, date.today())
    with get_conn(db_path) as conn:
        text = full_ledger_csv(conn)
        model = grid_model(conn, today)
    paid_months = {
        (model_row["isin"], cell["month"])
        for model_row in model["rows"]
        for cell in model_row["cells"]
        if cell["state"] == "paid"
    }
    for csv_row in parse(text)[1:]:
        if (csv_row[1], csv_row[2]) in paid_months:
            assert float(csv_row[3]) > 0


def test_tc30_utf8_no_bom_from_route(client, db_path):
    seed_ledger(db_path, date.today())
    response = client.get("/export.csv?scope=full")
    assert response.status_code == 200
    data = response.data
    assert not data.startswith(BOM)
    assert data[:3] != BOM
    text = data.decode("utf-8")
    assert text.split("\r\n")[0] == "bond,isin,month,amount,paid,status"
    assert "Alpha Corp" in text
    assert "1500.00" in text


def test_tc30_utf8_no_bom_current_view(client, db_path):
    seed_ledger(db_path, date.today())
    response = client.get("/export.csv?scope=current")
    assert response.status_code == 200
    data = response.data
    assert not data.startswith(BOM)
    text = data.decode("utf-8")
    assert text.split("\r\n")[0] == "bond,isin,month,amount,paid,status"


def test_tc30_empty_ledger_headers_only(db_path):
    with get_conn(db_path) as conn:
        text = full_ledger_csv(conn)
    assert text == "bond,isin,month,amount,paid,status\r\n"


def test_tc30_unknown_scope_named_error(client, db_path):
    response = client.get("/export.csv?scope=everything")
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-export-view" in html
    assert "everything" in html


def test_tc30_invalid_month_named_error(client, db_path):
    response = client.get("/export.csv?scope=current&month=2026-99")
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-export-view" in html


def test_tc30_current_scope_uses_latest_month_with_data(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    prior = add_months(base, -2)
    prior_key = f"{prior.year:04d}-{prior.month:02d}"
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "SepOnly Co", "INE0000000303", add_months(base, -3).isoformat(), 6)
        add_payment(conn, bond_id, prior_key, 700.0)
    response = client.get("/export.csv?scope=current")
    assert response.status_code == 200
    text = response.get_data(as_text=True)
    rows = parse(text)[1:]
    assert rows
    assert all(row[2] == prior_key for row in rows)
    assert any(float(row[3]) == 700.0 for row in rows)
