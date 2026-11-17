import json
from pathlib import Path

from src.app import create_app
from src.bond_master.cache import BondMasterCache

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
NSDL_MASTER = "nsdl_corporate_bond_master.json"
ISIN = "INE205A07DV2"
COMPANY = "Acme Infrastructure Ltd"


def fixture_text(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def nsdl_transport():
    payload = fixture_text(NSDL_MASTER)

    def transport(url, timeout):
        return payload

    return transport


def make_client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = nsdl_transport()
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client()


def test_tc_ilf_01_lookup_endpoint_returns_the_fetch_payload_as_json(db_path):
    client = make_client(db_path)
    response = client.get(f"/watch/lookup?isin={ISIN}")
    assert response.status_code == 200
    assert response.mimetype == "application/json"
    payload = json.loads(response.get_data(as_text=True))
    assert payload["isin"] == ISIN
    assert payload["state"] == "found"
    assert payload["facts"]["company"] == COMPANY
    assert payload["values"]["company"] == COMPANY
    assert payload["asof"]


def test_tc_ilf_01_lookup_endpoint_rejects_a_bad_isin(db_path):
    client = make_client(db_path)
    response = client.get("/watch/lookup?isin=NOTANISIN")
    assert response.status_code == 400
    assert json.loads(response.get_data(as_text=True))["error"] == "ERR-watch-lookup"


def test_tc_ilf_01_template_fetches_json_and_has_no_page_navigation():
    template = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")
    assert 'fetch("/watch/lookup?" + serialize()' in template
    assert "window.location.assign" not in template
    assert "function applyLookupPayload(payload)" in template


def test_tc_ilf_02_apply_marks_the_isin_applied_and_suppresses_restore(db_path):
    client = make_client(db_path)
    client.get(f"/watch?isin={ISIN}")
    response = client.post("/watch/lookup/applied", data={"isin": ISIN})
    assert response.status_code == 200
    assert json.loads(response.get_data(as_text=True))["status"] == "ok"
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'id="fetch-details"' not in html
    assert 'id="fetch-details-tpl"' in html
    assert 'data-fetch-isin="" hidden' in html


def test_tc_ilf_02_without_apply_get_still_shows_the_popup(db_path):
    client = make_client(db_path)
    html = client.get(f"/watch?isin={ISIN}").get_data(as_text=True)
    assert 'id="fetch-details"' in html
    assert f'data-fetch-isin="{ISIN}"' in html


def test_tc_ilf_02_apply_rejects_a_bad_isin(db_path):
    client = make_client(db_path)
    response = client.post("/watch/lookup/applied", data={"isin": "BAD"})
    assert response.status_code == 400
