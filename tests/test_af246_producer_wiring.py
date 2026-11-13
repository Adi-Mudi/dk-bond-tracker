from pathlib import Path

import json

import src.app as app_module
from src.app import create_app
from src.bond_master import service as service_module
from src.bond_master.cache import BondMasterCache
from src.db import get_conn

FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
ISIN = "INE205A07DV2"
COMPANY = "Acme Infrastructure Ltd"
FUTURE = 2_000_000_000.0
FUTURE_ASOF = "2033-05-18T03:33:20+00:00"


def _nsdl_payload():
    return (FIXTURES / "nsdl_corporate_bond_master.json").read_text(encoding="utf-8")


def transport(body=None):
    payload = _nsdl_payload() if body is None else body

    def send(url, timeout):
        return payload

    return send


def offline_transport(url, timeout):
    raise ConnectionError("offline")


def make_app(db_path, send, monkeypatch):
    monkeypatch.setattr(app_module, "_auto_refresh_started", True)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = send
    return app


def open_form(app, **params):
    query = "".join(f"&{key}={value}" for key, value in params.items())
    return app.test_client().get(f"/watch?isin={ISIN}{query}")


def new_session(cache):
    cache._session_results.clear()
    cache._last_refresh_at = None
    return cache


def test_form_autofetch_writes_a_row_a_later_lookup_offers_cached(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    row = BondMasterCache(db_path).lookup(ISIN)
    assert row is not None
    assert row["company"] == COMPANY
    assert row["rating"] == "AA+"
    assert row["rating_agency"] == "CRISIL"
    assert row["source"] == "NSDL"
    assert row["fetched_at"]

    new_session(service_module.shared_cache(str(db_path)))
    app.extensions.pop("bond_master_service", None)
    app.config["BOND_MASTER_TRANSPORT"] = offline_transport
    html = open_form(app).get_data(as_text=True)
    assert COMPANY in html
    assert row["fetched_at"] in html


def test_refresh_all_keeps_the_asof_when_the_facts_are_unchanged(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    row0 = BondMasterCache(db_path).lookup(ISIN)
    assert row0["company"] == COMPANY

    fresh = BondMasterCache(db_path, clock=lambda: FUTURE)
    monkeypatch.setattr(service_module, "shared_cache", lambda path: fresh)
    service_module.refresh_all(str(db_path), trigger="manual", transport=transport())
    row1 = BondMasterCache(db_path).lookup(ISIN)
    assert row1["company"] == COMPANY
    assert row1["fetched_at"] == row0["fetched_at"]


def test_refresh_all_advances_the_asof_when_the_facts_change(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    row0 = BondMasterCache(db_path).lookup(ISIN)

    fresh = BondMasterCache(db_path, clock=lambda: FUTURE)
    monkeypatch.setattr(service_module, "shared_cache", lambda path: fresh)
    changed = transport(_nsdl_payload().replace(COMPANY, COMPANY + " Renamed"))
    service_module.refresh_all(str(db_path), trigger="manual", transport=changed)
    row1 = BondMasterCache(db_path).lookup(ISIN)
    assert row1["company"] == COMPANY + " Renamed"
    assert row1["fetched_at"] == FUTURE_ASOF
    assert row1["fetched_at"] != row0["fetched_at"]


def test_refresh_all_leaves_a_naturally_written_row_untouched_on_failure(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    before = BondMasterCache(db_path).lookup(ISIN)
    assert before is not None

    fresh = BondMasterCache(db_path, clock=lambda: FUTURE)
    monkeypatch.setattr(service_module, "shared_cache", lambda path: fresh)
    service_module.refresh_all(str(db_path), trigger="manual", transport=offline_transport)
    assert BondMasterCache(db_path).lookup(ISIN) == before


def test_user_edited_fields_survive_a_refresh_save(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    live = service_module.shared_cache(str(db_path))
    open_form(app, dirty="coupon_pct", coupon_pct="7.5")
    assert live.edited_fields(ISIN) == frozenset({"coupon"})

    new_session(live)
    changed = transport(_nsdl_payload().replace('"coupon_rate": "8.75"', '"coupon_rate": "5.00"'))
    monkeypatch.setattr(service_module, "shared_cache", lambda path: live)
    service_module.refresh_all(str(db_path), trigger="manual", transport=changed)
    row = BondMasterCache(db_path).lookup(ISIN)
    assert row["coupon"] == 8.75
    assert row["company"] == COMPANY


def test_provenance_renders_from_a_naturally_written_row(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, watch_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'holding')",
            (COMPANY, ISIN, COMPANY, 100000.0, "2025-01-05", "2026-01-05", 12, 5),
        )
        bond_id = cursor.lastrowid
    html = app.test_client().get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert 'id="detail-provenance"' in html
    assert 'data-source="NSDL"' in html


def test_a_partial_found_fetch_does_not_null_stored_facts(db_path, monkeypatch):
    app = make_app(db_path, transport(), monkeypatch)
    open_form(app)
    full = BondMasterCache(db_path).lookup(ISIN)
    assert full["rating"] == "AA+"
    assert full["maturity"]

    partial = json.loads(_nsdl_payload())
    for key in ("credit_rating", "rating_agency", "maturity_date", "listing_status", "security_type"):
        partial["records"][0].pop(key, None)
    new_session(service_module.shared_cache(str(db_path)))
    app.extensions.pop("bond_master_service", None)
    app.config["BOND_MASTER_TRANSPORT"] = transport(json.dumps(partial))
    open_form(app)

    after = BondMasterCache(db_path).lookup(ISIN)
    assert after["company"] == COMPANY
    assert after["rating"] == "AA+"
    assert after["rating_agency"] == "CRISIL"
    assert after["issuer_type"] == full["issuer_type"]
    assert after["listing_status"] == full["listing_status"]
    assert after["maturity"] == full["maturity"]
