from datetime import date, timedelta

import pytest

from src.app import create_app
from src.db import get_conn
from src.validators import add_months

_START = date.today() - timedelta(days=30)
_START_ISO = _START.isoformat()
_END_ISO = add_months(_START, 36).isoformat()


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def insert_holding(db_path, isin):
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, amount, start_date, end_date, tenure_months, credit_day, watch_state) "
            "VALUES ('Listing Co', ?, 10000, ?, ?, 36, 5, 'holding')",
            (isin, _START_ISO, _END_ISO),
        )
        return cursor.lastrowid


def listing_of(db_path, bond_id):
    with get_conn(db_path) as conn:
        return conn.execute("SELECT listing_status FROM bonds WHERE id = ?", (bond_id,)).fetchone()[
            "listing_status"
        ]


def test_listing_status_post_redirects_to_detail_on_success(client, db_path):
    bond_id = insert_holding(db_path, "INE9000A0274")
    response = client.post(
        f"/portfolio/{bond_id}/listing_status", data={"listing_status": "listed"}
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith(f"/portfolio/{bond_id}")
    assert listing_of(db_path, bond_id) == "listed"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_listing_status_post_invalid_value_returns_error_page(client, db_path):
    bond_id = insert_holding(db_path, "INE9000A0275")
    response = client.post(
        f"/portfolio/{bond_id}/listing_status", data={"listing_status": "bogus"}
    )
    assert response.status_code == 400
    assert b"invalid listing_status" in response.data
    assert listing_of(db_path, bond_id) == "unknown"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_listing_status_post_missing_bond_returns_not_found_page(client, db_path):
    response = client.post(
        "/portfolio/999999/listing_status", data={"listing_status": "listed"}
    )
    assert response.status_code == 404
    assert b"<html" in response.data.lower() or b"<!doctype" in response.data.lower()
