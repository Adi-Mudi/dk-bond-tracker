from datetime import date

import pytest

from conftest import add_bond, add_payment, bond_count, bond_status
from src.app import create_app
from src.db import get_conn
from src.ledger import save_payment
from src.validators import AppError, add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def month_key_of(day):
    return f"{day.year:04d}-{day.month:02d}"


def ledger_row(conn, bond_id, month):
    return conn.execute(
        "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
        (bond_id, month),
    ).fetchone()


def ledger_count(conn, bond_id, month):
    return conn.execute(
        "SELECT COUNT(*) AS n FROM payment_ledger WHERE bond_id = ? AND month = ?",
        (bond_id, month),
    ).fetchone()["n"]


def seed_paid_ongoing(db_path):
    today = date.today()
    base = today.replace(day=1)
    start = add_months(base, -2)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "RoundCo", "INE0000000281", start.isoformat(), 6, credit_day=5)
        for offset in range(3):
            add_payment(conn, bond_id, month_key_of(add_months(start, offset)), 1000.0)
    return bond_id, base, start


def test_tc28_post_zero_amount_flips_status_and_redirects(client, db_path):
    bond_id, base, start = seed_paid_ongoing(db_path)
    with get_conn(db_path) as conn:
        assert bond_status(conn, bond_id) == "On-going"
    older = month_key_of(start)
    response = client.post(
        f"/payment/{bond_id}/{older}",
        data={"amount": "0"},
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert response.headers["Location"] == "/grid"
    with get_conn(db_path) as conn:
        row = ledger_row(conn, bond_id, older)
        assert row is not None
        assert float(row["amount"]) == 0.0
        assert int(row["paid"]) == 0
        assert ledger_count(conn, bond_id, older) == 1
        assert bond_status(conn, bond_id) == "Danger"
    page = client.get("/grid").get_data(as_text=True)
    assert 'data-status="Danger"' in page
    assert f'cell cell-due" data-bond="{bond_id}" data-month="{older}"' in page


def test_tc28_duplicate_post_takes_correction_path(client, db_path):
    bond_id, base, start = seed_paid_ongoing(db_path)
    target = month_key_of(base)
    first = client.post(
        f"/payment/{bond_id}/{target}", data={"amount": "900", "paid": "on"}
    )
    second = client.post(
        f"/payment/{bond_id}/{target}", data={"amount": "1100", "paid": "on"}
    )
    assert first.status_code == 302
    assert second.status_code == 302
    with get_conn(db_path) as conn:
        assert ledger_count(conn, bond_id, target) == 1
        row = ledger_row(conn, bond_id, target)
        assert float(row["amount"]) == 1100.0
        assert int(row["paid"]) == 1


def test_tc28_edit_completing_tenure_flips_completed(client, db_path):
    today = date.today()
    base = today.replace(day=1)
    start = add_months(base, -2)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "DoneCo", "INE0000000282", start.isoformat(), 3, credit_day=5)
        add_payment(conn, bond_id, month_key_of(start), 1000.0)
        add_payment(conn, bond_id, month_key_of(add_months(start, 1)), 1000.0)
    target = month_key_of(base)
    response = client.post(
        f"/payment/{bond_id}/{target}", data={"amount": "1000", "paid": "on"}
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        assert bond_status(conn, bond_id) == "Completed"
    page = client.get("/grid").get_data(as_text=True)
    assert f'data-status="Completed"' in page
    assert f'cell cell-paid" data-bond="{bond_id}" data-month="{target}"' in page


def test_tc28_invalid_amount_shows_named_error_no_redirect(client, db_path):
    bond_id, base, start = seed_paid_ongoing(db_path)
    target = month_key_of(start)
    response = client.post(
        f"/payment/{bond_id}/{target}", data={"amount": "abc", "paid": "on"}
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert 'id="error-banner"' in html
    assert "operation: ERR-ledger-insert" in html
    with get_conn(db_path) as conn:
        assert bond_status(conn, bond_id) == "On-going"
        row = ledger_row(conn, bond_id, target)
        assert float(row["amount"]) == 1000.0


def test_tc28_missing_bond_shows_named_error(client, db_path):
    response = client.post("/payment/9999/2026-01", data={"amount": "100", "paid": "on"})
    assert response.status_code == 400
    assert "operation: ERR-ledger-insert" in response.get_data(as_text=True)


def test_tc28_unknown_month_string_shows_named_error(client, db_path):
    bond_id, base, start = seed_paid_ongoing(db_path)
    response = client.post(
        f"/payment/{bond_id}/not-a-month", data={"amount": "100", "paid": "on"}
    )
    assert response.status_code == 400
    assert "operation: ERR-ledger-insert" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 1


def test_tc28_save_payment_rejects_negative_amount(db_path):
    bond_id, base, start = seed_paid_ongoing(db_path)
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            save_payment(conn, bond_id, month_key_of(base), -5.0, True)
        assert exc_info.value.code == "ERR-ledger-insert"
