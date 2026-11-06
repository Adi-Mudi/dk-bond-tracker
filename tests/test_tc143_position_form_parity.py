from datetime import date, timedelta

import pytest

from conftest import bond_count
from src.app import create_app
from src.db import get_conn
from src.validators import add_months

_START = date.today() - timedelta(days=30)
_START_ISO = _START.isoformat()
_END_ISO = add_months(_START, 3).isoformat()


def position_form(**overrides):
    data = {
        "company": "Parity Co",
        "isin": "INE9000A0141",
        "amount": "10000",
        "start_date": _START_ISO,
        "end_date": _END_ISO,
        "credit_day": "5",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
    }
    data.update(overrides)
    return data


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def watch_candidate(client, isin, **overrides):
    data = {
        "company": "Parity Co",
        "isin": isin,
        "rating": "AA",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
    }
    data.update(overrides)
    return client.post("/watch", data=data)


def candidate_id(db_path, isin):
    with get_conn(db_path) as conn:
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def test_tc143_removed_entry_points_reject_writes(client, db_path):
    assert client.get("/add").status_code == 404
    assert client.post("/add", data=position_form()).status_code == 404
    assert client.post("/portfolio", data=position_form()).status_code == 405
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


def test_tc143_negative_amount_has_no_entry_point(client, db_path):
    response = client.post("/portfolio", data=position_form(amount="-1"))
    assert response.status_code == 405
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


def test_tc143_bad_credit_day_rejected_on_move_path(client, db_path):
    response = watch_candidate(client, "INE9000A0141")
    assert response.status_code == 302
    move = client.post(
        f"/watch/{candidate_id(db_path, 'INE9000A0141')}/move",
        data={"start_date": _START_ISO, "end_date": _END_ISO, "credit_day": "abc"},
    )
    assert move.status_code == 400
    assert "credit day must be an integer in 1-31" in move.get_data(as_text=True)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT watch_state FROM bonds WHERE isin = 'INE9000A0141'"
        ).fetchone()
    assert row["watch_state"] == "watching"


def test_tc143_bad_issuer_type_rejected_on_watch_path(client, db_path):
    response = watch_candidate(client, "INE9000A0141", issuer_type="equity")
    assert response.status_code == 400
    assert "issuer_type must be one of" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


def test_tc143_portfolio_post_normalizes_nothing(client, db_path):
    response = client.post("/portfolio", data=position_form(isin="ine9000a0142"))
    assert response.status_code == 405
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT isin FROM bonds").fetchone()
    assert row is None
