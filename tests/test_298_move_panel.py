import pytest
pytest.skip("Retired per issue #337: old frontend removal", allow_module_level=True)
import re
from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn

ROOT = Path(__file__).resolve().parents[1]
WATCH_TEMPLATE = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")

BASE_WATCH = {
    "company": "Move Panel Co",
    "rating": "AA",
    "coupon_pct": "8.0",
    "expected_yield_pct": "8.5",
}

MOVE_PAYLOAD = {
    "purchase_date": "2026-08-01",
    "start_date": "2026-08-01",
    "end_date": "2028-08-01",
    "credit_day": "5",
    "qty": "100",
    "amount": "100000",
    "broker": "Zerodha",
}


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), db_path


def make_candidate(http, db_path, isin, maturity=None):
    data = dict(BASE_WATCH, isin=isin, company="Move Panel " + isin)
    if maturity:
        data["maturity_date"] = maturity
    response = http.post("/watch", data=data, follow_redirects=False)
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (isin,)
        ).fetchone()["id"]


def move_panel(html, candidate_id):
    match = re.search(
        r'<tr class="move-row" id="move-panel-' + str(candidate_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert match, "move panel must render as a hidden row"
    return match.group(1)


def fieldset_blocks(panel):
    return re.findall(r"<fieldset[^>]*>(.*?)</fieldset>", panel, re.S)


def test_298_a_maturity_present_derived_readonly_no_editable_input(client, db_path):
    http, db = client
    candidate = make_candidate(http, db, "INE2980A0101", maturity="2028-10-17")
    panel = move_panel(http.get("/watch").get_data(as_text=True), candidate)
    assert "End date" in panel
    assert "2028-10-17 — from maturity date" in panel
    assert "from maturity date" in panel
    assert "never asked again" in panel
    assert 'name="end_date"' not in panel
    assert 'id="move-end-' + str(candidate) + '"' not in panel
    assert 'class="move-derived"' in panel
    assert "readonly" in panel


def test_298_b_maturity_missing_editable_input_with_helper_caption(client, db_path):
    http, db = client
    candidate = make_candidate(http, db, "INE2980A0102")
    panel = move_panel(http.get("/watch").get_data(as_text=True), candidate)
    assert 'name="end_date"' in panel
    assert 'name="end_date" required' in panel
    assert 'id="move-end-' + str(candidate) + '"' in panel
    assert "complete the bond facts" in panel
    assert "No maturity date on file." in panel
    assert "from maturity date" not in panel
    assert "never asked again" not in panel
    assert "move-derived" not in panel


def test_298_c_layout_vertical_fieldsets_buttons_in_own_row(client, db_path):
    http, db = client
    candidate = make_candidate(http, db, "INE2980A0103", maturity="2028-10-17")
    panel = move_panel(http.get("/watch").get_data(as_text=True), candidate)
    assert "move-form-stack" in panel
    base_css = re.search(r"\.move-form\s*\{([^}]*)\}", WATCH_TEMPLATE).group(1)
    stack_css = re.search(r"\.move-form-stack\s*\{([^}]*)\}", WATCH_TEMPLATE).group(1)
    assert "display: flex" in base_css
    assert "display: grid" not in base_css
    assert "flex-direction: column" in stack_css
    legends = re.findall(r"<legend>([^<]+)</legend>", panel)
    assert legends == ["Dates", "Amount", "Optional"]
    assert panel.index("<legend>Dates</legend>") < panel.index("<legend>Amount</legend>")
    assert panel.index("<legend>Amount</legend>") < panel.index("<legend>Optional</legend>")
    blocks = fieldset_blocks(panel)
    assert len(blocks) == 3
    for block in blocks:
        assert "move-actions" not in block
        assert 'id="move-' + str(candidate) + '"' not in block
        assert ">Move</button>" not in block
        assert ">Cancel</button>" not in block
    assert "move-actions" in panel
    assert panel.rindex("</fieldset>") < panel.index("move-actions")
    assert panel.index("move-actions") < panel.index(">Move</button>")


def test_298_d_field_contracts_unchanged_and_post_still_redirects(client, db_path):
    http, db = client
    candidate = make_candidate(http, db, "INE2980A0104", maturity="2028-10-17")
    panel = move_panel(http.get("/watch").get_data(as_text=True), candidate)
    for name in ("purchase_date", "start_date", "amount", "qty", "broker", "goal_id", "credit_day"):
        assert 'name="' + name + '"' in panel
    for field_id in (
        "move-purchase-",
        "move-start-",
        "move-amount-",
        "move-qty-",
        "move-perbond-",
        "move-broker-",
        "move-goal-",
        "move-credit-",
    ):
        assert 'id="' + field_id + str(candidate) + '"' in panel
    assert 'action="/watch/' + str(candidate) + '/move"' in panel
    assert 'id="move-' + str(candidate) + '"' in panel
    assert "move-cancel" in panel
    response = http.post(
        f"/watch/{candidate}/move",
        data=MOVE_PAYLOAD,
        follow_redirects=False,
    )
    assert response.status_code == 302
    with get_conn(db) as conn:
        row = conn.execute(
            "SELECT watch_state, end_date FROM bonds WHERE id = ?", (candidate,)
        ).fetchone()
    assert row["watch_state"] == "holding"
    assert row["end_date"] == "2028-08-01"


def test_298_e_months_readout_contract_intact(client, db_path):
    http, db = client
    candidate = make_candidate(http, db, "INE2980A0105", maturity="2028-10-17")
    panel = move_panel(http.get("/watch").get_data(as_text=True), candidate)
    assert 'class="months-readout"' in panel
    assert 'id="move-months-' + str(candidate) + '"' in panel
    assert 'data-months-for="move"' in panel
    assert 'data-purchase="move-purchase-' + str(candidate) + '"' in panel
    assert 'data-maturity="2028-10-17"' in panel
    assert 'data-end="move-end-' + str(candidate) + '"' in panel
    assert 'data-cycle="' in panel
    assert 'aria-live="polite"' in panel
    assert "data-months-for='move'" in WATCH_TEMPLATE
    assert "var moveReadouts = document.querySelectorAll" in WATCH_TEMPLATE


def test_298_state_matrix_mixed_watchlist_renders_both_branches(client, db_path):
    http, db = client
    fetched = make_candidate(http, db, "INE2980A0201", maturity="2029-01-31")
    manual = make_candidate(http, db, "INE2980A0202")
    html = http.get("/watch").get_data(as_text=True)
    fetched_panel = move_panel(html, fetched)
    manual_panel = move_panel(html, manual)
    assert 'name="end_date"' not in fetched_panel
    assert "2029-01-31 — from maturity date" in fetched_panel
    assert "never asked again" in fetched_panel
    assert 'name="end_date"' in manual_panel
    assert "complete the bond facts" in manual_panel
    assert "from maturity date" not in manual_panel
    assert fetched_panel != manual_panel


def test_298_state_matrix_move_without_end_date_uses_stored_maturity(client, db_path):
    http, db = client
    candidate = make_candidate(http, db, "INE2980A0203", maturity="2028-10-17")
    payload = {key: value for key, value in MOVE_PAYLOAD.items() if key != "end_date"}
    response = http.post(
        f"/watch/{candidate}/move",
        data=payload,
        follow_redirects=False,
    )
    assert response.status_code == 302
    with get_conn(db) as conn:
        row = conn.execute(
            "SELECT watch_state, end_date, maturity_date FROM bonds WHERE id = ?",
            (candidate,),
        ).fetchone()
    assert row["watch_state"] == "holding"
    assert row["maturity_date"] == "2028-10-17"
    assert row["end_date"] == "2028-10-17"


def test_298_state_matrix_months_readout_present_for_both_branches(client, db_path):
    http, db = client
    fetched = make_candidate(http, db, "INE2980A0204", maturity="2028-10-17")
    manual = make_candidate(http, db, "INE2980A0205")
    html = http.get("/watch").get_data(as_text=True)
    fetched_panel = move_panel(html, fetched)
    manual_panel = move_panel(html, manual)
    assert 'data-maturity="2028-10-17"' in fetched_panel
    assert 'data-maturity=""' in manual_panel
    assert 'id="move-months-' + str(fetched) + '"' in fetched_panel
    assert 'id="move-months-' + str(manual) + '"' in manual_panel
