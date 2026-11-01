import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from conftest import add_bond
from src.app import create_app
from src.db import get_conn, init_db


def _seed_text_amounts(db_path):
    init_db(db_path)
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "TEXT AMOUNT CO", "INE9000A01010", "2026-01-01", 6, credit_day=5
        )
        conn.execute(
            "UPDATE bonds SET amount = ? WHERE id = ?", ("not-a-number", bond_id)
        )
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            (bond_id, "2026-01", "oops-text", 1),
        )
    return bond_id


def test_obs2_text_amount_no_route_500s(db_path):
    bond_id = _seed_text_amounts(db_path)
    app = create_app(str(db_path))
    client = app.test_client()
    for route in [
        "/",
        "/grid",
        "/portfolio",
        "/watch",
        "/notifications",
        "/goals",
        f"/portfolio/{bond_id}/detail",
        "/export.csv?scope=full",
        "/print",
        "/payout?bond_id=1",
    ]:
        r = client.get(route)
        assert r.status_code != 500, f"{route} returned 500 with TEXT amounts"


def test_obs2_text_amount_marked_invalid_on_portfolio(db_path):
    bond_id = _seed_text_amounts(db_path)
    app = create_app(str(db_path))
    html = app.test_client().get("/portfolio").get_data(as_text=True)
    assert "TEXT AMOUNT CO" in html
    assert "Invalid" in html


def test_obs2_text_amount_dashboard_totals_do_not_crash(db_path):
    _seed_text_amounts(db_path)
    app = create_app(str(db_path))
    r = app.test_client().get("/")
    assert r.status_code == 200
