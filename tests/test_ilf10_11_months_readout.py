import pytest
"""TC-ILF-10..11 months-remaining readouts - batch B5, issue #283."""
import re
from datetime import date, timedelta

from src.app import create_app
from src.maturity import months_remaining


def _client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def _months(client, **params):
    response = client.get("/watch/months", query_string=params)
    assert response.status_code == 200
    return response.get_json()["months_remaining"]


def test_tc_ilf_10_add_readout_is_anchored_today(db_path):
    client = _client(db_path)
    maturity = (date.today() + timedelta(days=400)).isoformat()
    value = _months(client, maturity=maturity, cycle="quarterly")
    assert value == months_remaining(date.today().isoformat(), maturity, "quarterly")
    assert isinstance(value, int) and value > 0


def test_tc_ilf_10_add_readout_is_none_without_maturity(db_path):
    client = _client(db_path)
    assert _months(client, maturity="", cycle="annual") is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_ilf_10_add_form_has_readout_hook(db_path):
    html = _client(db_path).get("/watch").get_data(as_text=True)
    assert re.search(r'<span[^>]*id="c-months"[^>]*data-months-for="add"', html)
    assert "/watch/months?" in html


def test_tc_ilf_11_move_readout_is_anchored_at_purchase(db_path):
    client = _client(db_path)
    purchase = "2026-01-01"
    maturity = "2028-01-01"
    value = _months(client, purchase=purchase, maturity=maturity, cycle="monthly")
    assert value == months_remaining(purchase, maturity, "monthly")
    assert value == 24


def test_tc_ilf_11_move_readout_differs_from_today_anchor(db_path):
    client = _client(db_path)
    maturity = (date.today() + timedelta(days=400)).isoformat()
    anchored_today = _months(client, maturity=maturity, cycle="annual")
    anchored_purchase = _months(
        client, purchase="2020-01-01", maturity=maturity, cycle="annual"
    )
    assert anchored_purchase > anchored_today


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_tc_ilf_11_move_panel_has_readout_hook(db_path):
    from tests.test_fr77_move_purchase_details import make_candidate

    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    html = client.get("/watch").get_data(as_text=True)
    assert f'id="move-months-{candidate_id}"' in html
    assert f'data-purchase="move-purchase-{candidate_id}"' in html
