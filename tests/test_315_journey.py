import json
from pathlib import Path

from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.bond_master.snapshot import snapshot_lookup
from src.db import init_db

SNAPSHOT_ISIN = "INE2YB724070"
OFFICIAL_FIELDS = ("rating", "rating_agency", "issuer_type", "payout_cycle", "secured")
POPUP_ROWS = (
    ("rating", "Rating"),
    ("rating_agency", "Rating agency"),
    ("issuer_type", "Issuer type"),
    ("secured", "Secured"),
    ("payout_cycle", "Payout cycle"),
)
FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"


def _official_body_for(isin):
    document = json.loads(
        (FIXTURES / "nsdl_corporate_bond_master.json").read_text(encoding="utf-8")
    )
    record = dict(document["records"][0])
    record["isin"] = isin
    return json.dumps({**document, "records": [record]})


def _given_snapshot_known_isin_with_official_transport(db_path, isin):
    init_db(db_path)
    seed = snapshot_lookup(isin)
    assert seed is not None
    body = _official_body_for(isin)

    def official_transport(url, timeout):
        return body

    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = official_transport
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client(), seed


def _when_lookup_runs(client, isin):
    payload = client.get(f"/watch/lookup?isin={isin}").get_json()
    html = client.get(f"/watch?isin={isin}").get_data(as_text=True)
    start = html.index('id="fetch-details"')
    end = html.index("table-wrap watch-scroll", start)
    return payload, html[start:end]


def _then_official_facts_and_popup_rows(payload, popup, seed):
    for field in OFFICIAL_FIELDS:
        assert payload["popup_facts"].get(field) is not None
        assert payload["sources"].get(field) == "NSDL"
    for field in ("company", "coupon", "maturity"):
        assert payload["popup_facts"].get(field) == getattr(seed, field)
        assert payload["sources"].get(field) == "india-isin-data (CC0)"
    for fact, label in POPUP_ROWS:
        assert f'data-fetch-detail="{fact}"' in popup
        assert f'data-fetch-source="{fact}">NSDL<' in popup
        assert f">{label}<" in popup


def test_given_snapshot_isin_when_lookup_runs_then_full_fact_popup_renders(db_path):
    given_client, given_seed = _given_snapshot_known_isin_with_official_transport(
        db_path, SNAPSHOT_ISIN
    )
    when_payload, when_popup = _when_lookup_runs(given_client, SNAPSHOT_ISIN)
    _then_official_facts_and_popup_rows(when_payload, when_popup, given_seed)
