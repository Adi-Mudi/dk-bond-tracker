import re
from pathlib import Path

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.views.watch import WATCH_BROKERS, WATCH_RATINGS

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")

CANDIDATE = {
    "company": "Autocomplete Alpha Ltd",
    "isin": "INE4000A1001",
    "rating": "AA",
    "coupon_pct": "8.0",
    "expected_yield_pct": "8.5",
    "broker": "Zerodha",
}


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def candidate_id(db_path, isin="INE4000A1001"):
    with get_conn(db_path) as conn:
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def move_payload(**overrides):
    data = {
        "purchase_date": "2026-08-01",
        "start_date": "2026-08-01",
        "end_date": "2028-08-01",
        "credit_day": "5",
        "qty": "100",
        "amount": "100000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def candidate_row(html):
    match = re.search(r'<tr class="candidate-row"[^>]*>(.*?)</tr>', html, re.S)
    assert match, "candidate row must render"
    return match.group(1)


def details_row(html, bond_id):
    match = re.search(
        r'<tr class="details-row" id="details-' + str(bond_id) + r'" hidden>\s*<td colspan="8">(.*?)</td>\s*</tr>',
        html,
        re.S,
    )
    assert match, "details row must render"
    return match.group(1)


def test_ui04_add_form_collapsed_by_default_and_opens_on_error(client, db_path):
    html = client.get("/watch").get_data(as_text=True)
    assert 'id="add-candidate-panel" hidden' in html
    assert 'id="add-candidate-toggle"' in html
    assert 'aria-controls="add-candidate-form"' in html
    assert 'id="add-candidate-form"' in html
    response = client.post(
        "/watch",
        data={"company": "Bad Co", "isin": "nope", "rating": "AA", "coupon_pct": "8", "expected_yield_pct": "8"},
    )
    assert response.status_code == 400
    assert 'id="add-candidate-panel" hidden' not in response.get_data(as_text=True)


def test_ui04_company_autocomplete_combobox_markup(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Existing Register Co", "INE4000A1002", "2026-01-01", 12)
    html = client.get("/watch").get_data(as_text=True)
    assert 'role="combobox"' in html
    assert 'aria-autocomplete="list"' in html
    assert 'aria-controls="c-company-list"' in html
    assert 'aria-expanded="false"' in html
    assert 'id="c-company-list"' in html
    assert 'role="listbox"' in html
    assert 'role="option"' in html
    assert 'data-value="Existing Register Co"' in html
    assert "aria-activedescendant" in TEMPLATE


def test_ui04_company_history_strip_beside_field(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Existing Register Co", "INE4000A1002", "2026-01-01", 12)
    html = client.get("/watch").get_data(as_text=True)
    assert 'id="company-history"' in html
    assert 'data-company="existing register co"' in html
    assert "INE4000A1002" in html
    assert 'class="history-block"' in html


def test_ui04_isin_forced_uppercase_on_store(client, db_path):
    response = client.post("/watch", data={**CANDIDATE, "isin": "ine4000a1001"})
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT isin FROM bonds WHERE isin = 'INE4000A1001'").fetchone()
    assert row is not None
    assert "toUpperCase" in TEMPLATE


def test_ui04_duplicate_popup_with_inline_alert_and_aria_invalid(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    response = client.post("/watch", data={**CANDIDATE, "isin": "ine4000a1001"})
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert 'id="watch-error" role="alert"' in html
    assert 'aria-invalid="true"' in html
    assert 'id="c-isin-error" role="alert"' in html
    assert 'aria-describedby="c-isin-help c-isin-error"' in html
    assert "field-error-icon" in html
    assert 'id="add-candidate-panel" hidden' not in html


def test_ui04_duplicate_highlights_isin_match_and_company_only(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    isin_dup = client.post("/watch", data={**CANDIDATE, "isin": "ine4000a1001"})
    assert isin_dup.status_code == 409
    isin_html = isin_dup.get_data(as_text=True)
    assert 'id="c-isin-error" role="alert"' in isin_html
    assert 'id="c-isin" name="isin"' in isin_html
    assert 'aria-invalid="true"' in isin_html

    with get_conn(db_path) as conn:
        add_bond(conn, "Taken Co", "INE4000A1004", "2026-01-01", 12)
    company_dup = client.post(
        "/watch",
        data={**CANDIDATE, "company": "Taken Co", "isin": "INE4000A1005"},
    )
    assert company_dup.status_code == 409
    company_html = company_dup.get_data(as_text=True)
    assert 'id="c-company-error" role="alert"' in company_html
    assert 'id="c-isin-error" role="alert"' not in company_html


def test_ui04_duplicate_holding_offers_view_existing_to_portfolio_detail(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Held Dup Co", "INE4000A1010", "2026-01-01", 12)
    response = client.post(
        "/watch",
        data={**CANDIDATE, "company": "Held Dup Co", "isin": "INE4000A1010"},
    )
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert 'id="dup-view-existing"' in html
    assert f'href="/portfolio/{bond_id}"' in html
    assert "View existing" in html
    assert 'id="dup-edit-isin"' in html
    assert "Edit ISIN" in html
    assert 'aria-controls="c-isin"' in html
    assert "isin.focus()" in TEMPLATE
    assert "isin.select()" in TEMPLATE


def test_ui04_duplicate_watching_offers_view_existing_to_candidate_row(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    bond_id = candidate_id(db_path)
    response = client.post("/watch", data={**CANDIDATE, "isin": "ine4000a1001"})
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert f'id="candidate-{bond_id}"' in html
    assert f'href="#candidate-{bond_id}"' in html
    assert 'id="dup-view-existing"' in html
    assert 'id="dup-edit-isin"' in html


def test_ui04_error_banner_actions_only_on_duplicate(client, db_path):
    response = client.post(
        "/watch",
        data={**CANDIDATE, "isin": "not-an-isin"},
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert 'id="watch-error"' in html
    assert 'id="dup-view-existing"' not in html
    assert 'id="dup-edit-isin"' not in html


def test_ui04_rating_options_ceiling_bbb_minus_only(client, db_path):
    html = client.get("/watch").get_data(as_text=True)
    block = re.search(r'<select id="c-rating" name="rating".*?</select>', html, re.S).group(0)
    values = [value for value in re.findall(r'<option value="([^"]*)"', block) if value]
    assert values == list(WATCH_RATINGS)
    assert WATCH_RATINGS[-1] == "BBB-"
    for lower in ("BB+", "BB", "B", "C", "D"):
        assert lower not in values


def test_ui04_rating_below_bbb_minus_rejected(client, db_path):
    response = client.post("/watch", data={**CANDIDATE, "isin": "INE4000A1003", "rating": "BB"})
    assert response.status_code == 400
    assert "investment grade AAA to BBB-" in response.get_data(as_text=True)


def test_ui04_agency_and_broker_presets_plus_custom_persist(client, db_path):
    response = client.post(
        "/watch",
        data={**CANDIDATE, "rating_agency": "My Custom Agency", "broker": "My Custom Broker"},
    )
    assert response.status_code == 302
    html = client.get("/watch").get_data(as_text=True)
    agencies = re.search(r'<datalist id="c-agency-options">(.*?)</datalist>', html, re.S).group(1)
    brokers = re.search(r'<datalist id="c-broker-options">(.*?)</datalist>', html, re.S).group(1)
    assert "CRISIL" in agencies
    assert "Infomerics" in agencies
    assert "My Custom Agency" in agencies
    assert "ICICI Direct" in brokers
    assert "SBI Sec" in brokers
    assert "My Custom Broker" in brokers
    for preset in WATCH_BROKERS:
        assert preset in brokers


def test_ui04_row_actions_are_move_and_details_only(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    bond_id = candidate_id(db_path)
    html = client.get("/watch").get_data(as_text=True)
    row = candidate_row(html)
    assert "move-toggle" in row
    assert "details-toggle" in row
    assert f'action="/watch/{bond_id}/delete"' not in row
    assert f'id="delete-candidate-{bond_id}"' not in row
    assert "delete" not in row.lower()


def test_ui04_delete_lives_inside_details_behind_named_confirm(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    bond_id = candidate_id(db_path)
    html = client.get("/watch").get_data(as_text=True)
    details = details_row(html, bond_id)
    assert f'action="/watch/{bond_id}/delete"' in details
    assert f'id="delete-candidate-{bond_id}"' in details
    assert f'data-company="{CANDIDATE["company"]}"' in details
    assert f'data-isin="{CANDIDATE["isin"]}"' in details
    assert "return confirm(" in details
    assert 'role="alertdialog"' in html
    assert 'id="delete-confirm-cancel"' in html
    assert 'id="delete-confirm-accept"' in html
    assert "cancel.focus()" in TEMPLATE
    assert "type the" not in details.lower()


def test_ui04_candidate_table_sticky_ends_and_scroll_region(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    html = client.get("/watch").get_data(as_text=True)
    assert 'class="table-wrap watch-scroll"' in html
    assert 'tabindex="0"' in html
    assert 'role="region"' in html
    assert 'aria-label="Watchlist candidates' in html
    assert "#watch-list tr.candidate-row > td:first-child" in TEMPLATE
    assert "#watch-list tr.candidate-row > td:last-child" in TEMPLATE
    assert "#watch-list thead th:first-child { left: 0; z-index: 4; }" in TEMPLATE
    assert "#watch-list thead th:last-child { right: 0; z-index: 5; }" in TEMPLATE
    assert html.count('class="candidate-row"') == 1


def test_ui04_move_form_has_no_tabs_goal_is_plain_field(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    html = client.get("/watch").get_data(as_text=True)
    assert 'data-mtab=' not in html, "owner removed tabs — goal must be a plain field"
    assert 'name="goal_id"' not in html, "goal field hidden while zero goals"
    with get_conn(db_path) as conn:
        conn.execute("INSERT INTO financial_goals (name, target_amount) VALUES ('House', 600000)")
    html = client.get("/watch").get_data(as_text=True)
    assert 'data-mtab=' not in html
    assert 'name="goal_id"' in html
    assert "Financial goal" in html
    assert "House" in html


def test_ui04_move_flow_removes_candidate(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    bond_id = candidate_id(db_path)
    response = client.post(f"/watch/{bond_id}/move", data=move_payload())
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        state = conn.execute(
            "SELECT watch_state FROM bonds WHERE id = ?", (bond_id,)
        ).fetchone()["watch_state"]
    assert state == "holding"
    html = client.get("/watch").get_data(as_text=True)
    assert f'id="move-panel-{bond_id}"' not in html
    assert 'class="candidate-row"' not in html


def test_ui04_move_form_keeps_required_fields_inside_tab_panel(client, db_path):
    assert client.post("/watch", data=CANDIDATE).status_code == 302
    bond_id = candidate_id(db_path)
    html = client.get("/watch").get_data(as_text=True)
    panel = re.search(
        r'<tr class="move-row" id="move-panel-' + str(bond_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    ).group(1)
    assert 'action="/watch/%d/move"' % bond_id in panel
    assert 'name="purchase_date"' in panel
    assert 'name="qty"' in panel
    assert 'name="amount"' in panel
    assert f'id="move-cancel-{bond_id}"' in panel
    assert 'id="move-panel-purchase-%d"' % bond_id in panel
