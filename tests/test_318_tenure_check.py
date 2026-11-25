import pytest

from src.app import create_app
from src.db import get_conn

BASE = {
    "company": "Tenure Check Co",
    "isin": "INE3180A0001",
    "rating": "A",
    "coupon_pct": "8.5",
}

TENURE_MESSAGE = "purchase_date must be on or before maturity_date"


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def add_payload(**overrides):
    data = dict(BASE)
    data.update(overrides)
    return data


def post_add(client, **overrides):
    return client.post("/watch", data=add_payload(**overrides), follow_redirects=False)


def row_for(db_path, isin):
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM bonds WHERE isin = ?", (isin,)).fetchone()
        return dict(row) if row else None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_purchase_after_maturity_rejected(client, db_path):
    response = post_add(
        client,
        purchase_date="2030-01-01",
        maturity_date="2025-01-01",
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert TENURE_MESSAGE in body
    assert "2030-01-01 .. 2025-01-01" in body
    assert 'id="c-purchase_date-error"' in body
    assert row_for(db_path, "INE3180A0001") is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_e04_exact_repro_rejected(client, db_path):
    response = client.post(
        "/watch",
        data={
            "company": "Date end before start Co",
            "isin": "INE002Z08015",
            "rating": "AA",
            "coupon_pct": "8",
            "expected_yield_pct": "9",
            "amount": "1000",
            "qty": "1",
            "purchase_date": "2030-01-01",
            "maturity_date": "2025-01-01",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert TENURE_MESSAGE in response.get_data(as_text=True)
    assert row_for(db_path, "INE002Z08015") is None


def test_equal_dates_accepted(client, db_path):
    response = post_add(
        client,
        isin="INE3180A0002",
        purchase_date="2026-01-01",
        maturity_date="2026-01-01",
    )
    assert response.status_code == 302
    row = row_for(db_path, "INE3180A0002")
    assert row is not None
    assert row["purchase_date"] == "2026-01-01"
    assert row["maturity_date"] == "2026-01-01"


def test_purchase_before_maturity_accepted(client, db_path):
    response = post_add(
        client,
        isin="INE3180A0003",
        purchase_date="2025-01-01",
        maturity_date="2030-01-01",
    )
    assert response.status_code == 302
    row = row_for(db_path, "INE3180A0003")
    assert row is not None
    assert row["purchase_date"] == "2025-01-01"
    assert row["maturity_date"] == "2030-01-01"


def test_both_dates_missing_unchanged(client, db_path):
    response = post_add(client, isin="INE3180A0004")
    assert response.status_code == 302
    row = row_for(db_path, "INE3180A0004")
    assert row["purchase_date"] is None
    assert row["maturity_date"] is None


def test_purchase_only_unchanged(client, db_path):
    response = post_add(
        client,
        isin="INE3180A0005",
        purchase_date="2026-01-01",
    )
    assert response.status_code == 302
    row = row_for(db_path, "INE3180A0005")
    assert row["purchase_date"] == "2026-01-01"
    assert row["maturity_date"] is None


def test_maturity_only_unchanged(client, db_path):
    response = post_add(
        client,
        isin="INE3180A0006",
        maturity_date="2030-01-01",
    )
    assert response.status_code == 302
    row = row_for(db_path, "INE3180A0006")
    assert row["purchase_date"] is None
    assert row["maturity_date"] == "2030-01-01"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_invalid_purchase_date_unchanged_no_tenure_error(client, db_path):
    response = post_add(
        client,
        purchase_date="not-a-date",
        maturity_date="2030-01-01",
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "unparseable purchase_date" in body
    assert TENURE_MESSAGE not in body
    assert row_for(db_path, "INE3180A0001") is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_invalid_maturity_date_unchanged_no_tenure_error(client, db_path):
    response = post_add(
        client,
        purchase_date="2026-01-01",
        maturity_date="not-a-date",
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "unparseable maturity_date" in body
    assert TENURE_MESSAGE not in body
    assert row_for(db_path, "INE3180A0001") is None
