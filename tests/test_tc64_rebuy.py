import re
from datetime import date, timedelta

import pytest

from conftest import add_payment, bond_count
from src.app import create_app
from src.db import get_conn
from src.lock import check_add_allowed
from src.validators import add_months

_TODAY = date.today()
_START = _TODAY - timedelta(days=40)
_START_ISO = _START.isoformat()
_END_ISO = add_months(_START, 3).isoformat()

FORM = {
    "company": "RebuyCo",
    "isin": "INE0000000641",
    "amount": "5000",
    "start_date": _START_ISO,
    "end_date": _END_ISO,
    "credit_day": "5",
}
REBUY_FORM = dict(FORM, isin="INE0000000642")
REBUY_BLOCKED_PREFIX = "Cannot add position: RebuyCo has an active position ("
REBUY_BLOCKED_SUFFIX = " — no override"


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
        for offset in range(3):
            month = add_months(_START, offset)
            add_payment(conn, bond_id, f"{month.year:04d}-{month.month:02d}", 1000.0)
        assert check_add_allowed("RebuyCo", "INE0000000641", conn)


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
    assert REBUY_BLOCKED_PREFIX in html
    assert REBUY_BLOCKED_SUFFIX in html
    assert re.search(r"active position \((On-going|Danger)\)", html)
    assert "operation: ERR-active-position" in html
    assert current_count(db_path) == 2
