import pytest
pytest.skip("Retired per issue #337: old frontend removal", allow_module_level=True)
import re
from pathlib import Path

from src.app import create_app
from src.bond_master.base import FetchResult
from src.bond_master.cache import BondMasterCache
from src.db import get_conn
from src.views.watch import apply_fetch, fetch_payload
from tests.test_af248_popup_countdown import AF14_ISIN, _af14_transport
from tests.test_fr77_move_purchase_details import valid_move

ROOT = Path(__file__).resolve().parents[1]
WATCH_TEMPLATE = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")
FULL_ISIN = AF14_ISIN
PARTIAL_ISIN = "INE4000F0303"
EMPTY_ISIN = "INE4000F0404"

EXPECTED_APPLY_VALUES = {
    "company": "Acme Infrastructure Ltd",
    "coupon_pct": "8.75",
    "maturity_date": "2030-03-31",
    "rating": "AA+",
    "rating_agency": "CRISIL",
    "issuer_type": "ncd",
    "payout_cycle": "annual",
    "secured": "1",
}


def _client(db_path, transport=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    if transport is not None:
        app.config["BOND_MASTER_TRANSPORT"] = transport
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client()


def _apply_rows(html):
    return dict(re.findall(r'data-apply-field="([a-z_]+)" data-apply-value="([^"]*)"', html))


def _lookup(db_path, isin, dirty=""):
    response = _client(db_path, _af14_transport()).get(
        "/watch/lookup", query_string={"isin": isin, "dirty": dirty}
    )
    assert response.status_code == 200
    return response.get_json()


def _candidate_id(db_path, isin):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id FROM bonds WHERE upper(trim(isin)) = upper(?)", (isin,)
        ).fetchone()["id"]


def _move_panel(html, candidate_id):
    match = re.search(
        r'<tr class="move-row" id="move-panel-' + str(candidate_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert match, "move panel must render as a hidden row"
    return match.group(1)


def test_a_full_payload_popup_apply_covers_every_fact(db_path):
    html = _client(db_path, _af14_transport()).get(f"/watch?isin={FULL_ISIN}").get_data(as_text=True)
    rows = _apply_rows(html)
    for field, value in EXPECTED_APPLY_VALUES.items():
        assert rows.get(field) == value, f"apply row missing or wrong for {field}"


def test_a_full_payload_lookup_values_cover_every_form_field(db_path):
    payload = _lookup(db_path, FULL_ISIN)
    for field, value in EXPECTED_APPLY_VALUES.items():
        assert payload["values"].get(field) == value, f"lookup value missing for {field}"
    assert payload["values"].get("face_value") == "1000"


def test_a_js_apply_writes_payload_values_and_maps_maturity():
    assert "var appliedValues = {};" in WATCH_TEMPLATE
    assert "function writeFactValues(values) {" in WATCH_TEMPLATE
    assert "Object.keys(values || {}).forEach(function (field) {" in WATCH_TEMPLATE
    assert "appliedValues = payload.values || {};" in WATCH_TEMPLATE
    assert "writeFactValues(appliedValues);" in WATCH_TEMPLATE
    assert '["maturity", "maturity_date", "c-maturity"]' in WATCH_TEMPLATE
    assert "('maturity', 'maturity_date')" in WATCH_TEMPLATE
    assert '["maturity", "maturity_date", "Maturity"]' in WATCH_TEMPLATE


def test_b_partial_payload_fills_only_supplied_fields(db_path):
    result = FetchResult(
        isin=PARTIAL_ISIN,
        company="Partial Co",
        coupon=7.5,
        sources={"company": "NSDL", "coupon": "NSDL"},
    )
    values, _ = apply_fetch({}, fetch_payload(result), set())
    assert values == {"company": "Partial Co", "coupon_pct": "7.5"}
    assert "maturity_date" not in values
    assert "rating" not in values


def test_b_partial_popup_only_exposes_supplied_apply_rows(db_path):
    body = (
        '{"source": "NSDL", "published": "2026-11-12", "records": ['
        '{"isin": "' + PARTIAL_ISIN + '", "issuer_name": "Partial Co", '
        '"coupon_rate": "7.5"}]}'
    )
    html = _client(db_path, lambda url, timeout: body).get(
        f"/watch?isin={PARTIAL_ISIN}"
    ).get_data(as_text=True)
    rows = _apply_rows(html)
    assert rows == {"company": "Partial Co", "coupon_pct": "7.5"}


def test_c_empty_payload_does_not_crash_and_keeps_form_untouched(db_path):
    payload = fetch_payload(FetchResult(isin=EMPTY_ISIN))
    assert payload["popup_facts"] == {}
    values, _ = apply_fetch({}, payload, set())
    assert values == {}
    html = _client(db_path).get("/watch").get_data(as_text=True)
    assert 'id="fetch-details-tpl"' in html
    assert _apply_rows(html) == {}


def test_c_js_apply_guards_missing_popup_and_null_values():
    assert "function applyFetchedFacts() {" in WATCH_TEMPLATE
    assert "if (!popup) {" in WATCH_TEMPLATE
    assert "if (value === null || value === undefined) {" in WATCH_TEMPLATE
    assert "var element = fieldElement(field);" in WATCH_TEMPLATE


def test_d_full_apply_candidate_has_maturity_and_move_has_no_typed_end_date(db_path):
    client = _client(db_path, _af14_transport())
    assert client.get(f"/watch?isin={FULL_ISIN}").status_code == 200
    data = dict(EXPECTED_APPLY_VALUES)
    data["isin"] = FULL_ISIN
    data["expected_yield_pct"] = "9.2"
    response = client.post("/watch", data=data, follow_redirects=False)
    assert response.status_code == 302
    candidate_id = _candidate_id(db_path, FULL_ISIN)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT maturity_date FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row["maturity_date"] == "2030-03-31"
    panel = _move_panel(client.get("/watch").get_data(as_text=True), candidate_id)
    assert 'name="end_date"' not in panel
    move = valid_move(start_date="2026-08-01")
    move.pop("end_date")
    assert client.post(f"/watch/{candidate_id}/move", data=move).status_code == 302
    with get_conn(db_path) as conn:
        moved = conn.execute(
            "SELECT end_date FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert moved["end_date"] == "2030-03-31"


def test_state_fresh_form_full_payload_prefills_every_input(db_path):
    html = _client(db_path, _af14_transport()).get(f"/watch?isin={FULL_ISIN}").get_data(as_text=True)
    for field_id, value in (
        ("c-company", "Acme Infrastructure Ltd"),
        ("c-coupon", "8.75"),
        ("c-maturity", "2030-03-31"),
        ("c-rating-agency", "CRISIL"),
    ):
        tag = re.search(r'<[^>]*id="' + field_id + r'"[^>]*>', html).group(0)
        assert f'value="{value}"' in tag, field_id


def test_state_reapply_different_isin_replaces_not_merges(db_path):
    full = FetchResult(
        isin=FULL_ISIN,
        company="Old Co",
        coupon=8.75,
        maturity="2030-03-31",
        rating="AA+",
        sources={"company": "NSDL"},
    )
    full_values, _ = apply_fetch({}, fetch_payload(full), set())
    assert full_values["maturity_date"] == "2030-03-31"
    partial = FetchResult(
        isin=PARTIAL_ISIN,
        company="New Co",
        coupon=7.5,
        sources={"company": "NSDL", "coupon": "NSDL"},
    )
    partial_values, _ = apply_fetch({}, fetch_payload(partial), set())
    assert partial_values == {"company": "New Co", "coupon_pct": "7.5"}
    assert "maturity_date" not in partial_values
    assert "rating" not in partial_values
    assert "if (isinValue() === fetched) {" in WATCH_TEMPLATE
    assert "clearFetchedFacts();" in WATCH_TEMPLATE


def test_state_manual_edits_preserved_when_payload_lacks_the_field(db_path):
    result = FetchResult(
        isin=FULL_ISIN,
        company="Fetched Co",
        coupon=8.75,
        sources={"company": "NSDL", "coupon": "NSDL"},
    )
    current = {"rating": "A", "maturity_date": "2031-01-01"}
    values, _ = apply_fetch(current, fetch_payload(result), set())
    assert "rating" not in values
    assert "maturity_date" not in values
    assert values == {"company": "Fetched Co", "coupon_pct": "8.75"}
    full = FetchResult(
        isin=FULL_ISIN,
        company="Fetched Co",
        rating="AA+",
        sources={"company": "NSDL", "rating": "NSDL"},
    )
    dirty_values, _ = apply_fetch({"rating": "A"}, fetch_payload(full), {"rating"})
    assert "rating" not in dirty_values
    assert "if (dirty[field]) {" in WATCH_TEMPLATE
