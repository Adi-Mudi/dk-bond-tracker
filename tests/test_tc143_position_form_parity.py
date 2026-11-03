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
        "isin": "INE0000001431",
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


@pytest.mark.parametrize("path", ["/add", "/portfolio"])
def test_tc143_negative_amount_rejected_on_both_entry_points(client, db_path, path):
    response = client.post(path, data=position_form(amount="-1"))
    assert response.status_code == 400
    assert "amount must not be negative" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


@pytest.mark.parametrize("path", ["/add", "/portfolio"])
def test_tc143_bad_credit_day_rejected_on_both_entry_points(client, db_path, path):
    response = client.post(path, data=position_form(credit_day="abc"))
    assert response.status_code == 400
    assert "credit day must be an integer in 1-31" in response.get_data(as_text=True)


@pytest.mark.parametrize("path", ["/add", "/portfolio"])
def test_tc143_bad_issuer_type_rejected_on_both_entry_points(client, db_path, path):
    response = client.post(path, data=position_form(issuer_type="equity"))
    assert response.status_code == 400
    assert "issuer_type must be one of" in response.get_data(as_text=True)


def test_tc143_portfolio_normalizes_isin_case(client, db_path):
    response = client.post("/portfolio", data=position_form(isin="ine0000001432"))
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT isin FROM bonds").fetchone()
    assert row["isin"] == "INE0000001432"
