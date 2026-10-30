from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.share import build_share_snapshot, share_csv
from src.validators import AppError, add_months

ALL_ON = {"totals": True, "per_bond": True, "history": True, "alerts": True}
RAW_TOKENS = ("123456.78", "₹", "data-amount")


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_portfolio(db_path, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    with get_conn(db_path) as conn:
        alpha = add_bond(conn, "Alpha Corp", "INE0000000731", add_months(base, -3).isoformat(), 6, amount=123456.78)
        add_bond(conn, "Beta Corp", "INE0000000732", base.isoformat(), 6, amount=50000.0)
        add_payment(conn, alpha, current, 2500.0)


def assert_masked(text):
    assert "••••" in text
    for token in RAW_TOKENS:
        assert token not in text, token
    assert "2500.00" not in text
    assert "50000.00" not in text


def test_tc73_html_masked_when_include_amounts_false(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(conn, ALL_ON, False)
    assert_masked(html)
    assert "Alpha Corp" in html
    assert "Alpha Corp" in html
    assert "INE0000000731" in html


def test_tc73_csv_masked_when_include_amounts_false(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        text = share_csv(conn, ALL_ON, False)
    assert_masked(text)
    assert "Alpha Corp" in text
    assert "section,totals" in text
    assert "section,per_bond" in text
    assert "section,history" in text
    assert "section,alerts" in text


def test_tc73_privacy_flag_masks_even_with_amounts_checked(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(conn, ALL_ON, True, privacy_on=True)
        text = share_csv(conn, ALL_ON, True, privacy_on=True)
    assert_masked(html)
    assert_masked(text)


def test_tc73_unmasked_control_contains_raw_values(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(conn, ALL_ON, True)
        text = share_csv(conn, ALL_ON, True)
    assert "123456.78" in html
    assert "123456.78" in text
    assert "••••" not in html
    assert "••••" not in text


def test_tc73_route_html_masked_without_include_amounts(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post(
        "/share/generate",
        data={"sections": ["totals", "per_bond", "history", "alerts"], "format": "html"},
    )
    assert response.status_code == 200
    assert 'filename="share_snapshot.html"' in response.headers["Content-Disposition"]
    assert_masked(response.get_data(as_text=True))


def test_tc73_route_csv_masked_without_include_amounts(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post(
        "/share/generate",
        data={"sections": ["totals", "per_bond", "history", "alerts"], "format": "csv"},
    )
    assert response.status_code == 200
    assert 'filename="share_snapshot.csv"' in response.headers["Content-Disposition"]
    assert response.headers["Content-Type"].startswith("text/csv")
    assert_masked(response.get_data(as_text=True))


def test_tc73_route_privacy_post_masks_despite_include_amounts(client, db_path):
    seed_portfolio(db_path, date.today())
    for fmt in ("html", "csv"):
        response = client.post(
            "/share/generate",
            data={
                "sections": ["totals", "per_bond"],
                "include_amounts": "on",
                "privacy": "on",
                "format": fmt,
            },
        )
        assert response.status_code == 200
        assert_masked(response.get_data(as_text=True))


def test_tc73_route_html_with_amounts_shows_raw(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post(
        "/share/generate",
        data={"sections": ["totals", "per_bond"], "include_amounts": "on", "format": "html"},
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "173456.78" in html
    assert "123456.78" in html
    assert "••••" not in html


def test_tc73_unknown_section_named_error(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            build_share_snapshot(conn, {"totals": True, "secrets": True}, True)
    assert exc_info.value.code == "ERR-share-export"
    assert "secrets" in exc_info.value.message
