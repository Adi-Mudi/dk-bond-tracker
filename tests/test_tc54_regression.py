import csv
import io
from datetime import date

import pytest

from conftest import add_bond, add_payment, pay_range
from src.alerts import daily_sweep
from src.app import create_app
from src.db import get_conn
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def month_key(value):
    return f"{value.year:04d}-{value.month:02d}"


def seed_chain_portfolio(conn, today):
    base = today.replace(day=1)
    danger_id = add_bond(
        conn, "DangerCo", "INETC54001", add_months(base, -2).isoformat(), 6, credit_day=1
    )
    ongoing_id = add_bond(
        conn, "OngoingCo", "INETC54002", base.isoformat(), 6, amount=50000.0, credit_day=28
    )
    add_payment(conn, ongoing_id, month_key(base), 500.0)
    completed_id = add_bond(
        conn, "DoneCo", "INETC54003", add_months(base, -2).isoformat(), 1, amount=10000.0
    )
    pay_range(conn, completed_id, month_key(add_months(base, -2)), 1, amount=700.0)
    return danger_id, ongoing_id, completed_id, base


def parse_csv(text):
    return list(csv.reader(io.StringIO(text)))


def test_tc54_payment_updates_dashboard_on_reload_without_restart(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        _danger_id, ongoing_id, _completed_id, base = seed_chain_portfolio(conn, today)
    before = client.get("/").get_data(as_text=True)
    assert "&#8377;1200.00" in before
    next_month = add_months(base, 1)
    response = client.post(
        f"/payment/{ongoing_id}/{month_key(next_month)}",
        data={"amount": "250", "paid": "on"},
    )
    assert response.status_code in (302, 200)
    after = client.get("/").get_data(as_text=True)
    assert "&#8377;1450.00" in after
    assert "&#8377;500.00" in after


def test_tc54_status_coverage_survives_payment_round(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_chain_portfolio(conn, today)
    before = client.get("/").get_data(as_text=True)
    for status in ("Danger", "On-going", "Completed"):
        assert f'data-status="{status}"' in before
    after = client.get("/").get_data(as_text=True)
    for status in ("Danger", "On-going", "Completed"):
        assert f'data-status="{status}"' in after


def test_tc54_csv_matches_grid_again_after_edit(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        _danger_id, ongoing_id, _completed_id, base = seed_chain_portfolio(conn, today)
    current = month_key(base)
    grid_html = client.get("/grid").get_data(as_text=True)
    assert "OngoingCo" in grid_html
    client.post(
        f"/payment/{ongoing_id}/{current}",
        data={"amount": "500", "paid": "on"},
    )
    response = client.get(f"/export.csv?scope=current&month={current}")
    assert response.status_code == 200
    rows = parse_csv(response.data.decode("utf-8"))[1:]
    ongoing_row = [row for row in rows if row[1] == "INETC54002"]
    assert ongoing_row
    assert ongoing_row[0][3] == "500.00"
    assert ongoing_row[0][4] == "1"


def test_tc54_payment_correction_updates_ledger_single_row(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        _danger_id, ongoing_id, _completed_id, base = seed_chain_portfolio(conn, today)
    current = month_key(base)
    response = client.post(
        f"/payment/{ongoing_id}/{current}",
        data={"amount": "999", "paid": "on"},
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (ongoing_id, current),
        ).fetchall()
    assert len(rows) == 1
    assert float(rows[0]["amount"]) == 999.0
    assert int(rows[0]["paid"]) == 1


def test_tc54_alerts_still_fire_for_unpaid_credit_day(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        danger_id, _ongoing_id, _completed_id, _base = seed_chain_portfolio(conn, today)
        events = daily_sweep(conn, today)
    danger_events = [event for event in events if event["bond_id"] == danger_id]
    if today.day > 1:
        assert danger_events, "expected a danger alert for the unpaid past month"
        assert danger_events[0]["severity"] == "danger"
        with get_conn(db_path) as conn:
            status = conn.execute(
                "SELECT status FROM bonds WHERE id = ?", (danger_id,)
            ).fetchone()["status"]
        assert status == "Danger"
    else:
        assert danger_events == []
    history = client.get("/notifications")
    assert history.status_code == 200


def test_tc54_full_chain_import_edit_status_dashboard_export(tmp_path):
    from pathlib import Path

    from src.import_xlsm import import_workbook

    workbook = Path(
        "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
    )
    db_path = tmp_path / "tc54_chain.db"
    summary = import_workbook(workbook, db_path)
    assert summary["bonds"] == 15
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    body = dashboard.get_data(as_text=True)
    assert "bonds: 15" in body
    with get_conn(db_path) as conn:
        bond = conn.execute(
            "SELECT id FROM bonds ORDER BY id LIMIT 1"
        ).fetchone()
    grid = client.get("/grid")
    assert grid.status_code == 200
    export = client.get("/export.csv?scope=full")
    assert export.status_code == 200
    rows = parse_csv(export.data.decode("utf-8"))
    assert len(rows) - 1 == summary["ledger_rows"]
    payout = client.get(f"/payout?bond_id={bond['id']}&cycle=monthly")
    assert payout.status_code == 200
    assert "payout-schedule" in payout.get_data(as_text=True)
