from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.share import build_share_snapshot, share_csv
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_portfolio(db_path, today):
    base = today.replace(day=1)
    current = f"{base.year:04d}-{base.month:02d}"
    with get_conn(db_path) as conn:
        alpha = add_bond(conn, "Alpha Corp", "INE0000000721", add_months(base, -3).isoformat(), 6, amount=123456.78)
        add_bond(conn, "Beta Corp", "INE0000000722", base.isoformat(), 6, amount=50000.0)
        add_payment(conn, alpha, current, 2500.0)


ALL_ON = {"totals": True, "per_bond": True, "history": True, "alerts": True}


def test_tc72_only_selected_sections_in_html(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(
            conn,
            {"totals": True, "per_bond": True, "history": False, "alerts": False},
            True,
        )
    assert 'id="share-totals"' in html
    assert 'id="share-per-bond"' in html
    assert 'id="share-history"' not in html
    assert 'id="share-alerts"' not in html
    assert "Monthly history" not in html
    assert "Alpha Corp" in html


def test_tc72_totals_excluded_when_unchecked(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(
            conn,
            {"totals": False, "per_bond": True, "history": True, "alerts": True},
            True,
        )
    assert 'id="share-totals"' not in html
    assert "Portfolio totals" not in html
    assert "Total investment" not in html
    assert 'id="share-per-bond"' in html
    assert 'id="share-history"' in html
    assert 'id="share-alerts"' in html


def test_tc72_alerts_section_only_when_checked(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        without = build_share_snapshot(
            conn,
            {"totals": True, "per_bond": False, "history": False, "alerts": False},
            True,
        )
        with_alerts = build_share_snapshot(conn, ALL_ON, True)
    assert 'id="share-alerts"' not in without
    assert 'id="share-alerts"' in with_alerts


def test_tc72_include_amounts_off_masks_and_hides_raw_values(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(conn, ALL_ON, False)
    assert "••••" in html
    assert "123456.78" not in html
    assert "123456" not in html
    assert "₹" not in html
    assert "data-amount" not in html
    assert "Alpha Corp" in html
    assert "INE0000000721" in html


def test_tc72_include_amounts_on_shows_raw_values(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        html = build_share_snapshot(conn, ALL_ON, True)
    assert "₹123456.78" in html
    assert 'data-amount="123456.78"' in html
    assert "••••" not in html


def test_tc72_no_sections_selected_raises_named_error(db_path):
    seed_portfolio(db_path, date.today())
    from src.validators import AppError

    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            build_share_snapshot(conn, {"totals": False, "per_bond": False, "history": False, "alerts": False}, True)
    assert exc_info.value.code == "ERR-share-export"


def test_tc72_share_csv_contains_only_selected_sections(db_path):
    seed_portfolio(db_path, date.today())
    with get_conn(db_path) as conn:
        text = share_csv(
            conn,
            {"totals": True, "per_bond": True, "history": False, "alerts": False},
            True,
        )
    assert "section,totals" in text
    assert "section,per_bond" in text
    assert "section,history" not in text
    assert "section,alerts" not in text


def test_tc72_route_share_form_renders(client):
    response = client.get("/share")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'action="/share/generate"' in html
    for value in ("totals", "per_bond", "history", "alerts"):
        assert f'value="{value}"' in html
    assert 'name="include_amounts"' in html
    assert 'value="html"' in html
    assert 'value="csv"' in html


def test_tc72_route_generate_subset_snapshot(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post(
        "/share/generate",
        data={"sections": ["totals", "per_bond"], "include_amounts": "on", "format": "html"},
    )
    assert response.status_code == 200
    assert 'filename="share_snapshot.html"' in response.headers["Content-Disposition"]
    html = response.get_data(as_text=True)
    assert 'id="share-totals"' in html
    assert 'id="share-per-bond"' in html
    assert 'id="share-history"' not in html
    assert "₹123456.78" in html


def test_tc72_route_generate_totals_excluded(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post(
        "/share/generate",
        data={"sections": ["per_bond", "history", "alerts"], "include_amounts": "on", "format": "html"},
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="share-totals"' not in html
    assert "Total investment" not in html


def test_tc72_route_no_sections_is_named_error(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post("/share/generate", data={"format": "html"})
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "ERR-share-export" in html


def test_tc72_route_post_to_share_also_generates(client, db_path):
    seed_portfolio(db_path, date.today())
    response = client.post(
        "/share",
        data={"sections": ["history"], "format": "csv"},
    )
    assert response.status_code == 200
    assert 'filename="share_snapshot.csv"' in response.headers["Content-Disposition"]
    text = response.get_data(as_text=True)
    assert "section,history" in text
    assert "section,totals" not in text
