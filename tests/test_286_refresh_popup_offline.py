"""Issue #286: forced-official /watch/refresh renders the offline popup combo (AF-03)."""
from datetime import datetime
from pathlib import Path

import pytest

from src.app import create_app
from src.bond_master import service as service_module
from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.cache import BondMasterCache
from src.bond_master.snapshot import SNAPSHOT_SOURCE
from src.views.watch import refresh_failure_code

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
TEMPLATE = (ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")

ISIN = "INE205A07DV2"
SECOND_ISIN = "INE205A07DW3"
COMPANY = "Acme Infrastructure Ltd"
STORED_ASOF = "11 Nov 2026, 09:42"


@pytest.fixture(autouse=True)
def _fast_service(monkeypatch):
    real_build = service_module.build_default_service

    def build(cache, transport, **kwargs):
        return real_build(
            cache,
            transport,
            retries=0,
            sleep=lambda _seconds: None,
            throttle_seconds=0.0,
        )

    monkeypatch.setattr(service_module, "build_default_service", build)


def seed_master(db_path, source="NSDL", fetched_at=STORED_ASOF):
    BondMasterCache(db_path).save(
        {
            "isin": ISIN,
            "company": COMPANY,
            "coupon": 8.75,
            "payout_cycle": "annual",
            "face_value": 1000.0,
            "rating": "AA+",
            "rating_agency": "CRISIL",
            "issuer_type": "ncd",
            "secured": 1,
            "listing_status": "listed",
            "maturity": "2030-03-31",
            "source": source,
            "fetched_at": fetched_at,
        }
    )


def dead_transport(url, timeout):
    raise ConnectionError("no network")


def make_client(db_path, transport):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = transport
    return app.test_client(), app


def fixture_transport(name="nsdl_corporate_bond_master.json"):
    body = (FIXTURES / name).read_text(encoding="utf-8")
    return lambda url, timeout: body


def refresh(client, isin=None):
    data = {} if isin is None else {"isin": isin}
    return client.post("/watch/refresh", data=data)


def test_refresh_offline_renders_the_popup_banner_with_cached_facts_and_asof(db_path):
    seed_master(db_path)
    client, _ = make_client(db_path, dead_transport)
    response = refresh(client, ISIN)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "refreshed"
    assert payload["message"] == "Could not reach the source"
    merged = payload["fetch"]
    assert merged["state"] == "offline"
    assert merged["message"] == "Could not reach the source"
    assert merged["isin"] == ISIN
    assert merged["asof"] == STORED_ASOF
    assert merged["cached"]["company"] == COMPANY
    assert merged["cached"]["coupon"] == 8.75
    assert merged["popup_facts"]["company"] == COMPANY
    assert merged["popup_facts"]["rating"] == "AA+"


def test_refresh_offline_popup_keeps_a_source_label_on_every_fact(db_path):
    seed_master(db_path)
    client, _ = make_client(db_path, dead_transport)
    merged = refresh(client, ISIN).get_json()["fetch"]
    assert merged["tier"] == "official"
    assert merged["source_names"] == ["NSDL"]
    assert set(merged["sources"]) == set(merged["facts"])
    assert set(merged["sources"].values()) == {"NSDL"}


def test_refresh_offline_asof_is_the_stored_fetched_at_not_today(db_path):
    seed_master(db_path)
    client, _ = make_client(db_path, dead_transport)
    merged = refresh(client, ISIN).get_json()["fetch"]
    assert merged["asof"] == STORED_ASOF
    assert merged["asof"] != datetime.now().strftime("%d %b %Y, %H:%M")
    assert BondMasterCache(db_path).lookup(ISIN)["fetched_at"] == STORED_ASOF


def test_refresh_offline_snapshot_row_offers_only_the_three_snapshot_facts(db_path):
    seed_master(db_path, source=None)
    client, _ = make_client(db_path, dead_transport)
    merged = refresh(client, ISIN).get_json()["fetch"]
    assert merged["state"] == "offline"
    assert merged["tier"] == "snapshot"
    assert set(merged["popup_facts"]) == {"company", "coupon", "maturity"}
    assert set(merged["sources"].values()) == {SNAPSHOT_SOURCE}


def test_refresh_without_a_viewed_isin_uses_the_single_known_bond(db_path):
    seed_master(db_path)
    client, _ = make_client(db_path, dead_transport)
    merged = refresh(client).get_json()["fetch"]
    assert merged["isin"] == ISIN
    assert merged["asof"] == STORED_ASOF


def test_refresh_without_a_viewed_isin_and_several_bonds_has_no_popup(db_path):
    seed_master(db_path)
    BondMasterCache(db_path).save(
        {"isin": SECOND_ISIN, "company": "Beta Capital Ltd", "source": "NSDL"}
    )
    client, _ = make_client(db_path, dead_transport)
    payload = refresh(client).get_json()
    assert "fetch" not in payload
    assert payload["message"] == "Bond master refresh finished"


def test_refresh_success_updates_facts_and_advances_fetched_at(db_path):
    seed_master(db_path, fetched_at=STORED_ASOF)
    client, _ = make_client(db_path, fixture_transport())
    payload = refresh(client, ISIN).get_json()
    assert "fetch" not in payload
    assert payload["message"] == "Bond master refresh finished"
    assert payload["summary"]["NSDL"]["failure_code"] == FAILURE_OK
    row = BondMasterCache(db_path).lookup(ISIN)
    assert row["company"] == COMPANY
    assert row["fetched_at"] != STORED_ASOF


def test_refresh_cooldown_gate_is_unchanged_and_carries_no_popup(db_path):
    seed_master(db_path)
    client, app = make_client(db_path, dead_transport)
    app.extensions["bond_master_cache"].begin_refresh()
    response = refresh(client, ISIN)
    assert response.status_code == 429
    payload = response.get_json()
    assert payload["status"] == "cooldown"
    assert "fetch" not in payload


def test_refresh_failure_code_maps_only_reach_and_blocked_failures():
    assert refresh_failure_code({"NSDL": {"failure_code": FAILURE_UNREACHABLE}}) == "OFFLINE"
    assert refresh_failure_code({"NSDL": {"failure_code": FAILURE_TIMEOUT}}) == "OFFLINE"
    assert refresh_failure_code({"NSDL": {"failure_code": FAILURE_UNREACHABLE}, "RBI": {"failure_code": FAILURE_BLOCKED}}) == FAILURE_BLOCKED
    assert refresh_failure_code({"NSDL": {"failure_code": FAILURE_OK}}) is None
    assert refresh_failure_code({"NSDL": {"failure_code": "PARSE_ERROR"}}) is None
    assert refresh_failure_code({}) is None


def test_refresh_response_drives_the_popup_and_banner_render():
    assert 'body: isin ? "isin=" + encodeURIComponent(isin) : ""' in TEMPLATE
    assert "window.renderWatchRefreshFetch" in TEMPLATE
    assert "function paintOfflineBanner(payload)" in TEMPLATE
    assert 'chip.className = "fetch-source fetch-source-cached"' in TEMPLATE
    assert 'chip.setAttribute("data-fetch-cached", field)' in TEMPLATE
    assert '"As of " + (payload.asof' in TEMPLATE
