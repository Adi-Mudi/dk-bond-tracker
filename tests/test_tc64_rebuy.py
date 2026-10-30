from datetime import date

import pytest

from conftest import add_payment, bond_count, bond_status
from src.app import create_app
from src.db import get_conn
from src.status import recompute_all
from src.validators import add_months

FORM = {
    "company": "RebuyCo",
    "isin": "INE0000000641",
    "amount": "5000",
    "start_date": "2026-01-01",
    "end_date": "2026-04-01",
    "credit_day": "5",
}
REBUY_FORM = dict(FORM, isin="INE0000000642")
REBUY_BLOCKED_MESSAGE = "Cannot add position: RebuyCo has an active position (On-going) — no override"


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def current_count(db_path):
    with get_conn(db_path) as conn:
        return bond_count(conn)


def complete_first_position(db_path, bond_id):
    with get_conn(db_path) as conn:
        start = date(2026, 1, 1)
        for offset in range(3):
            month = add_months(start, offset)
            add_payment(conn, bond_id, f"{month.year:04d}-{month.month:02d}", 1000.0)
        changed = recompute_all(conn, date(2026, 4, 10))
        assert changed == [
            {"bond_id": bond_id, "company": "RebuyCo", "from": "On-going", "to": "Completed"}
        ]
        assert bond_status(conn, bond_id) == "Completed"


def test_tc64_completed_company_can_be_rebought_then_relocks(client, db_path):
    first = client.post("/add", data=FORM)
    assert first.status_code == 302
    with get_conn(db_path) as conn:
        rows = conn.execute("SELECT id FROM bonds WHERE company = ?", ("RebuyCo",)).fetchall()
        assert len(rows) == 1
        first_id = rows[0]["id"]
    complete_first_position(db_path, first_id)
    second = client.post("/add", data=REBUY_FORM)
    assert second.status_code == 302
    assert current_count(db_path) == 2
    with get_conn(db_path) as conn:
        new_row = conn.execute(
            "SELECT id, status, isin FROM bonds WHERE company = ? AND id != ?",
            ("RebuyCo", first_id),
        ).fetchone()
        assert new_row is not None
        assert new_row["isin"] == "INE0000000642"
        assert new_row["status"] == "On-going"
    third = client.post("/add", data=REBUY_FORM)
    assert third.status_code == 409
    html = third.get_data(as_text=True)
    assert REBUY_BLOCKED_MESSAGE in html
    assert "operation: ERR-active-position" in html
    assert current_count(db_path) == 2
