from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.queries import chart_data
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_negative_balance_portfolio(conn, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    bond_a = add_bond(conn, "ChartA", "INE0000000761", add_months(base, -2).isoformat(), 12, amount=100000.0, maturity=120000.0)
    bond_b = add_bond(conn, "ChartB", "INE0000000762", base.isoformat(), 12, amount=50000.0, maturity=60000.0)
    add_payment(conn, bond_a, current, 1000.0)
    add_payment(conn, bond_b, current, 500.0)
    return bond_a, bond_b


def test_tc76_bars_length_equals_bond_count(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        seed_negative_balance_portfolio(conn, today)
        data = chart_data(conn, today)
    assert len(data["bars"]) == 2
    for bar in data["bars"]:
        assert isinstance(bar["invested"], (int, float))
        assert isinstance(bar["received"], (int, float))
        assert bar["invested"] > 0
        assert bar["received"] >= 0


def test_tc76_empty_portfolio_empty_series(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        data = chart_data(conn, today)
    assert data["bars"] == []
    assert data["cumulative"] == []
    assert data["donut"] == {"danger": 0, "ongoing": 0, "completed": 0, "total": 0}


def test_tc76_cumulative_negative_flag_present(db_path):
    today = date(2026, 10, 30)
    with get_conn(db_path) as conn:
        seed_negative_balance_portfolio(conn, today)
        data = chart_data(conn, today)
    assert data["cumulative"], "cumulative series must not be empty"
    assert any(point["balance_flag_negative"] for point in data["cumulative"])
    assert data["cumulative"][-1]["month"] == "2026-10"


def test_tc76_dashboard_has_three_inline_svg_charts(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_negative_balance_portfolio(conn, today)
    html = client.get("/").get_data(as_text=True)
    assert 'id="chart-bars"' in html
    assert 'id="chart-cumulative"' in html
    assert 'id="chart-donut"' in html
    assert html.count("<svg") >= 3


def test_tc76_rendered_dashboard_zero_external_references(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_negative_balance_portfolio(conn, today)
    html = client.get("/").get_data(as_text=True)
    lowered = html.lower()
    assert "http://" not in lowered
    assert "https://" not in lowered
    assert "cdn" not in lowered


def test_tc76_negative_segment_rendered_in_red(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_negative_balance_portfolio(conn, today)
    html = client.get("/").get_data(as_text=True)
    assert "#e03131" in html
