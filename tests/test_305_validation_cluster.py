import pytest

from src.app import create_app
from src.db import get_conn
from src.views.watch import WATCH_RATINGS

BASE = {
    "company": "Validation Cluster Co",
    "isin": "INE3050A0001",
    "rating": "A",
    "coupon_pct": "8.5",
}

ACCEPTED_RATINGS = [
    (rating, f"INE3050A{100 + index:04d}") for index, rating in enumerate(WATCH_RATINGS)
]
REJECTED_RATINGS = [
    (rating, f"INE3050B{200 + index:04d}")
    for index, rating in enumerate(("BB+", "BB", "B+", "B", "NR", "XXX"))
]


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


def move_payload(**overrides):
    data = {
        "credit_day": "5",
        "purchase_date": "2026-11-01",
        "start_date": "2026-11-01",
        "end_date": "2027-11-01",
        "qty": "10",
        "amount": "100000",
    }
    data.update(overrides)
    return data


def candidate_id(db_path, isin="INE3050A0001"):
    return row_for(db_path, isin)["id"]


def test_v1_minimal_add_with_coupon_succeeds(client, db_path):
    response = post_add(client)
    assert response.status_code == 302
    row = row_for(db_path, "INE3050A0001")
    assert row["coupon_pct"] == 8.5
    assert row["expected_yield_pct"] is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v1_missing_coupon_names_coupon_field(client):
    response = post_add(client, coupon_pct="")
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "coupon is required" in body
    assert 'id="c-coupon-error"' in body


def test_v2_est_yield_absent_is_optional(client, db_path):
    response = post_add(client)
    assert response.status_code == 302
    assert row_for(db_path, "INE3050A0001")["expected_yield_pct"] is None


def test_v2_est_yield_valid_is_stored(client, db_path):
    response = post_add(client, expected_yield_pct="9.2")
    assert response.status_code == 302
    assert row_for(db_path, "INE3050A0001")["expected_yield_pct"] == 9.2


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v2_est_yield_invalid_is_field_error(client):
    response = post_add(client, expected_yield_pct="abc")
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "est yield must be a number" in body
    assert 'id="c-yield-error"' in body


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v3_lowercase_isin_rejected(client, db_path):
    response = post_add(client, isin="ine3050a0001")
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "ISIN format invalid" in body
    assert 'id="c-isin-error"' in body
    assert row_for(db_path, "INE3050A0001") is None


def test_v3_uppercase_isin_accepted(client, db_path):
    response = post_add(client, isin="INE3050A0002")
    assert response.status_code == 302
    assert row_for(db_path, "INE3050A0002") is not None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v4_amount_zero_rejected(client, db_path):
    response = post_add(client, amount="0")
    assert response.status_code == 400
    assert "amount must be greater than 0" in response.get_data(as_text=True)
    assert row_for(db_path, "INE3050A0001") is None


def test_v4_amount_positive_stored(client, db_path):
    response = post_add(client, amount="100000")
    assert response.status_code == 302
    assert row_for(db_path, "INE3050A0001")["amount"] == 100000.0


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v5_invalid_purchase_date_field_error(client, db_path):
    response = post_add(client, purchase_date="not-a-date")
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "purchase_date" in body
    assert 'id="c-purchase_date-error"' in body
    assert row_for(db_path, "INE3050A0001") is None


def test_v5_valid_purchase_date_stored_verbatim(client, db_path):
    response = post_add(client, purchase_date="2026-11-01")
    assert response.status_code == 302
    assert row_for(db_path, "INE3050A0001")["purchase_date"] == "2026-11-01"


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v6_all_errors_shown_next_to_own_fields_at_once(client):
    response = client.post(
        "/watch",
        data={"company": "", "isin": "BAD", "rating": "A", "coupon_pct": ""},
        follow_redirects=False,
    )
    assert response.status_code == 400
    body = response.get_data(as_text=True)
    assert "company is required" in body
    assert "ISIN format invalid" in body
    assert "coupon is required" in body
    assert 'id="c-company-error"' in body
    assert 'id="c-isin-error"' in body
    assert 'id="c-coupon-error"' in body
    assert body.count('class="field-error"') >= 3


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_v7_move_amount_only_requires_qty(client, db_path):
    assert post_add(client).status_code == 302
    response = client.post(
        f"/watch/{candidate_id(db_path)}/move",
        data=move_payload(qty=""),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "qty must be a positive integer" in response.get_data(as_text=True)
    assert row_for(db_path, "INE3050A0001")["watch_state"] == "watching"


def test_v7_move_amount_and_qty_together_saves(client, db_path):
    assert post_add(client).status_code == 302
    response = client.post(
        f"/watch/{candidate_id(db_path)}/move",
        data=move_payload(),
        follow_redirects=False,
    )
    assert response.status_code == 302
    row = row_for(db_path, "INE3050A0001")
    assert row["watch_state"] == "holding"
    assert row["qty"] == 10
    assert row["amount"] == 100000.0


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_move_amount_zero_rejected(client, db_path):
    assert post_add(client).status_code == 302
    response = client.post(
        f"/watch/{candidate_id(db_path)}/move",
        data=move_payload(amount="0"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "amount must be greater than 0" in response.get_data(as_text=True)


def test_state_matrix_fresh_add_succeeds(client, db_path):
    assert post_add(client).status_code == 302
    assert row_for(db_path, "INE3050A0001") is not None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_matrix_persisted_duplicate_still_err_watch_dup(client, db_path):
    assert post_add(client).status_code == 302
    duplicate = post_add(client)
    assert duplicate.status_code == 409
    body = duplicate.get_data(as_text=True)
    assert "ERR-watch-dup" in body
    assert 'id="c-isin-error"' in body


@pytest.mark.parametrize(("rating", "isin"), ACCEPTED_RATINGS)
def test_state_matrix_rating_contract_accepts_aaa_to_bbb_minus(client, rating, isin):
    assert post_add(client, rating=rating, isin=isin).status_code == 302


@pytest.mark.parametrize(("rating", "isin"), REJECTED_RATINGS)
@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_state_matrix_rating_contract_rejects_below_bbb_minus(client, rating, isin):
    response = post_add(client, rating=rating, isin=isin)
    assert response.status_code == 400
    assert "rating must be investment grade" in response.get_data(as_text=True)
