import pytest

from conftest import add_ongoing_seed, bond_count
from src.app import create_app
from src.db import get_conn
from src.lock import check_add_allowed
from src.validators import AppError

HOLDING_ISIN = "IN1234567890"
HOLDING_COMPANY = "Beta Finance Ltd"
CANDIDATE_ISIN = "INE0000NEW99"
BASE_MESSAGE = "Cannot add position: Beta Finance Ltd has an active position (On-going)"
BLOCKED_MESSAGE = BASE_MESSAGE + " — no override"
MOVE_DATA = {
    "start_date": "2026-11-01",
    "end_date": "2027-11-01",
    "credit_day": "5",
    "qty": "100",
    "amount": "100000",
    "broker": "ICICI Direct",
}


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_candidate(client, company, isin):
    response = client.post(
        "/watch",
        data={
            "company": company,
            "isin": isin,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert response.status_code == 302


def seed_active_beta_finance(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, HOLDING_COMPANY, HOLDING_ISIN)


def candidate_id(db_path, isin):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (isin.upper(),)
        ).fetchone()["id"]


def current_bond_count(db_path):
    with get_conn(db_path) as conn:
        return bond_count(conn)


def test_tc67_blocked_move_returns_409_with_exact_banner(client, db_path):
    seed_candidate(client, "BETA FINANCE LTD", CANDIDATE_ISIN)
    seed_active_beta_finance(db_path)
    response = client.post(f"/watch/{candidate_id(db_path, CANDIDATE_ISIN)}/move", data=MOVE_DATA)
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert f'<div id="watch-error-message">{BLOCKED_MESSAGE}</div>' in html
    assert "Error: ERR-active-position" in html


def test_tc67_blocked_move_inserts_no_row(client, db_path):
    seed_candidate(client, "BETA FINANCE LTD", CANDIDATE_ISIN)
    seed_active_beta_finance(db_path)
    assert current_bond_count(db_path) == 2
    client.post(f"/watch/{candidate_id(db_path, CANDIDATE_ISIN)}/move", data=MOVE_DATA)
    assert current_bond_count(db_path) == 2


def test_tc67_all_surfaces_show_no_trace_of_blocked_duplicate(client, db_path):
    seed_candidate(client, "BETA FINANCE LTD", CANDIDATE_ISIN)
    seed_active_beta_finance(db_path)
    response = client.post(f"/watch/{candidate_id(db_path, CANDIDATE_ISIN)}/move", data=MOVE_DATA)
    assert response.status_code == 409
    with get_conn(db_path) as conn:
        states = [
            (row["company"], row["watch_state"])
            for row in conn.execute("SELECT company, watch_state FROM bonds ORDER BY id").fetchall()
        ]
    assert states == [("BETA FINANCE LTD", "watching"), (HOLDING_COMPANY, "holding")]
    portfolio = client.get("/portfolio").get_data(as_text=True)
    assert portfolio.count(HOLDING_COMPANY) == 1
    assert "BETA FINANCE LTD" not in portfolio
    assert CANDIDATE_ISIN not in portfolio
    assert current_bond_count(db_path) == 2


def test_tc67_isin_key_blocks_too(db_path):
    seed_active_beta_finance(db_path)
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as excinfo:
            check_add_allowed("Some Other Company", HOLDING_ISIN, conn)
    assert excinfo.value.code == "ERR-active-position"
    assert excinfo.value.message == BASE_MESSAGE
