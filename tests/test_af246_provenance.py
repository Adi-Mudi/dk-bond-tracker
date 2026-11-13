from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.db import get_conn

ISIN = "INE111111111"
COMPANY = "Acme Ltd"


def _add_holding(db_path):
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, watch_state) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'holding')",
            (COMPANY, ISIN, COMPANY, 100000.0, "2025-01-05", "2026-01-05", 12, 5),
        )
        return cursor.lastrowid


def _seed_master(db_path, source="NSDL"):
    BondMasterCache(db_path).save({"isin": ISIN, "company": COMPANY, "source": source})


def make_client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), app


def test_position_detail_renders_provenance_when_present(db_path):
    bond_id = _add_holding(db_path)
    _seed_master(db_path, "NSDL")
    client, _ = make_client(db_path)
    html = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert 'id="detail-provenance"' in html
    assert 'data-source="NSDL"' in html


def test_position_detail_has_no_provenance_when_absent(db_path):
    bond_id = _add_holding(db_path)
    client, _ = make_client(db_path)
    html = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert 'id="detail-provenance"' not in html


def test_position_detail_json_carries_provenance_when_present(db_path):
    bond_id = _add_holding(db_path)
    _seed_master(db_path, "RBI")
    client, _ = make_client(db_path)
    payload = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert payload["provenance"]["source"] == "RBI"
    assert payload["provenance"]["as_of"]


def test_position_detail_json_provenance_is_none_when_absent(db_path):
    bond_id = _add_holding(db_path)
    client, _ = make_client(db_path)
    payload = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert payload["provenance"] is None


def test_holdings_render_provenance_when_present(db_path):
    _add_holding(db_path)
    _seed_master(db_path, "NSDL")
    client, _ = make_client(db_path)
    html = client.get("/portfolio").get_data(as_text=True)
    assert "fetched from NSDL" in html
    assert 'data-fetch-source="NSDL"' in html


def test_holdings_are_unchanged_when_provenance_is_absent(db_path):
    _add_holding(db_path)
    client, _ = make_client(db_path)
    html = client.get("/portfolio").get_data(as_text=True)
    assert "fetched from" not in html


def test_status_overview_carries_provenance_when_present(db_path):
    from src.queries import status_overview

    _add_holding(db_path)
    _seed_master(db_path, "NSE")
    with get_conn(db_path) as conn:
        entries = status_overview(conn)
    assert entries[0]["provenance"]["source"] == "NSE"
    assert entries[0]["provenance"]["as_of"]


def test_status_overview_provenance_is_none_when_absent(db_path):
    from src.queries import status_overview

    _add_holding(db_path)
    with get_conn(db_path) as conn:
        entries = status_overview(conn)
    assert entries[0]["provenance"] is None
