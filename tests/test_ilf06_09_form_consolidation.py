"""TC-ILF-06..09 form consolidation tests - batch B4, issue #283."""
import re

from src.app import create_app
from src.db import get_conn
from tests.test_fr77_move_purchase_details import make_candidate, valid_move


def _client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def _candidate_form(**overrides):
    data = {
        "company": "Consolidate Ltd",
        "isin": "INE9100A0100",
        "rating": "AA",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def _move_panel(html, candidate_id):
    match = re.search(
        r'<tr class="move-row" id="move-panel-' + str(candidate_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert match, "move panel must render as a hidden row"
    return match.group(1)


def _set_maturity(db_path, candidate_id, maturity):
    with get_conn(db_path) as conn:
        conn.execute(
            "UPDATE bonds SET maturity_date = ? WHERE id = ?", (maturity, candidate_id)
        )


def _row(db_path, candidate_id):
    with get_conn(db_path) as conn:
        return dict(
            conn.execute("SELECT * FROM bonds WHERE id = ?", (candidate_id,)).fetchone()
        )


def test_tc_ilf_06_add_form_has_no_invested_qty_or_per_bond_inputs(db_path):
    html = _client(db_path).get("/watch").get_data(as_text=True)
    for field in ("watch_investment", "qty", "c-invested", "c-qty", "c-perbond"):
        assert not re.search(r'<input[^>]*(name|id)="' + field + '"', html), field
    assert "Number of bonds" not in html
    assert "Price per bond" not in html


def test_tc_ilf_06_add_post_without_money_trio_creates_candidate(db_path):
    response = _client(db_path).post("/watch", data=_candidate_form(), follow_redirects=False)
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT watch_state, watch_investment, qty FROM bonds WHERE isin = ?",
            ("INE9100A0100",),
        ).fetchone()
    assert row["watch_state"] == "watching"
    assert row["watch_investment"] is None
    assert row["qty"] is None


def test_tc_ilf_07_move_end_input_hidden_when_maturity_is_known(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    _set_maturity(db_path, candidate_id, "2029-03-15")
    panel = _move_panel(client.get("/watch").get_data(as_text=True), candidate_id)
    assert 'name="end_date"' not in panel


def test_tc_ilf_07_move_end_input_shown_when_maturity_is_missing(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    panel = _move_panel(client.get("/watch").get_data(as_text=True), candidate_id)
    assert 'name="end_date"' in panel


def test_tc_ilf_07_move_end_date_derives_from_maturity(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    _set_maturity(db_path, candidate_id, "2029-03-15")
    data = valid_move(start_date="2026-08-01")
    data.pop("end_date")
    response = client.post(f"/watch/{candidate_id}/move", data=data, follow_redirects=False)
    assert response.status_code == 302
    assert _row(db_path, candidate_id)["end_date"] == "2029-03-15"


def test_tc_ilf_08_move_start_defaults_from_purchase_date_when_blank(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    _set_maturity(db_path, candidate_id, "2029-03-15")
    data = valid_move(purchase_date="2026-08-01", start_date="")
    response = client.post(f"/watch/{candidate_id}/move", data=data, follow_redirects=False)
    assert response.status_code == 302
    assert _row(db_path, candidate_id)["start_date"] == "2026-08-01"


def test_tc_ilf_08_move_start_is_editable_when_given(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    _set_maturity(db_path, candidate_id, "2029-03-15")
    data = valid_move(purchase_date="2026-08-01", start_date="2026-08-10")
    response = client.post(f"/watch/{candidate_id}/move", data=data, follow_redirects=False)
    assert response.status_code == 302
    assert _row(db_path, candidate_id)["start_date"] == "2026-08-10"


def test_tc_ilf_09_move_broker_is_optional(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path)
    _set_maturity(db_path, candidate_id, "2029-03-15")
    data = valid_move(broker="")
    response = client.post(f"/watch/{candidate_id}/move", data=data, follow_redirects=False)
    assert response.status_code == 302
    assert _row(db_path, candidate_id)["broker"] is None


def test_tc_ilf_09_move_broker_input_is_not_required_but_prefilled(db_path):
    client = _client(db_path)
    candidate_id = make_candidate(client, db_path, broker="Kotak Securities")
    panel = _move_panel(client.get("/watch").get_data(as_text=True), candidate_id)
    broker_tag = re.search(r'<input[^>]*name="broker"[^>]*>', panel).group(0)
    assert "required" not in broker_tag
    assert 'value="Kotak Securities"' in broker_tag
