from pathlib import Path

import pytest

from conftest import bond_count
from src.app import create_app
from src.db import get_conn

SRC = Path(__file__).resolve().parents[1] / "src"

POSITION_FORM = {
    "company": "Direct Co",
    "isin": "INE9000A01777",
    "amount": "50000",
    "credit_day": "15",
    "start_date": "2026-10-01",
    "end_date": "2027-03-31",
    "coupon_pct": "7.5",
    "expected_yield_pct": "8.0",
    "broker": "ICICI Direct",
}


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def test_fr75_ac1_portfolio_has_no_add_position_ui(client, db_path):
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0
    html = client.get("/portfolio").get_data(as_text=True)
    assert 'id="add-position"' not in html
    assert "+ Add Position" not in html
    assert 'action="/portfolio"' not in html
    assert "<h2>Add Position</h2>" not in html


def test_fr75_ac2_post_portfolio_returns_405_and_writes_nothing(client, db_path):
    response = client.post("/portfolio", data=POSITION_FORM)
    assert response.status_code == 405
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


def test_fr75_ac3_legacy_add_route_returns_404(client, db_path):
    assert client.get("/add").status_code == 404
    assert client.post("/add", data=POSITION_FORM).status_code == 404
    assert not (SRC / "templates" / "add_position.html").exists()
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 0


def test_fr75_ac4_no_source_references_to_removed_symbols():
    removed = ("add_position.html", "_add_portfolio_position", "insert_position")
    offenders = []
    for path in sorted(SRC.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for token in removed:
            if token in text:
                offenders.append(f"{path.relative_to(SRC.parent)}: {token}")
    assert offenders == []
