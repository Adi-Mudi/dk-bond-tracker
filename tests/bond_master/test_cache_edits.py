from src.bond_master.base import FetchResult
from src.bond_master.cache import BOND_MASTER_FIELDS, BondMasterCache
from src.db import get_conn, init_db

ISIN = "INE0000000001"
ASOF_AT_1700000000 = "2023-11-14T22:13:20+00:00"


def _columns(db_path, table):
    with get_conn(db_path) as conn:
        return [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _legacy_bond_master(db_path):
    with get_conn(db_path) as conn:
        conn.execute("CREATE TABLE bond_master (isin TEXT PRIMARY KEY, company TEXT)")


def test_coupon_is_in_the_bond_master_field_model():
    assert "coupon" in BOND_MASTER_FIELDS


def test_a_fresh_db_has_a_coupon_column(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    assert "coupon" in _columns(db_path, "bond_master")


def test_a_migrated_legacy_db_gains_a_coupon_column(tmp_path):
    db_path = tmp_path / "bonds.db"
    _legacy_bond_master(db_path)
    init_db(db_path)
    assert "coupon" in _columns(db_path, "bond_master")


def test_a_fetched_coupon_round_trips_on_a_fresh_db(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    result = FetchResult(isin=ISIN, company="Acme Ltd", coupon=8.75, sources={"coupon": "NSE"})
    cache = BondMasterCache(db_path)
    cache.save(
        {
            "isin": result.isin,
            "company": result.company,
            "coupon": result.coupon,
            "source": result.source_of("coupon"),
        }
    )
    row = cache.lookup(ISIN)
    assert row["coupon"] == 8.75
    assert row["company"] == "Acme Ltd"


def test_a_fetched_coupon_round_trips_on_a_migrated_db(tmp_path):
    db_path = tmp_path / "bonds.db"
    _legacy_bond_master(db_path)
    init_db(db_path)
    cache = BondMasterCache(db_path)
    cache.save(
        {
            "isin": ISIN,
            "company": "Acme Ltd",
            "coupon": 8.75,
            "source": "nse",
            "fetched_at": ASOF_AT_1700000000,
        }
    )
    row = cache.lookup(ISIN)
    assert row["coupon"] == 8.75
    assert row["company"] == "Acme Ltd"


def test_a_user_edited_field_survives_a_refresh_write(db_path):
    cache = BondMasterCache(db_path)
    cache.save({"isin": ISIN, "company": "Acme", "coupon": 9.0, "source": "nsdl"})
    cache.mark_edited(ISIN, "coupon")
    assert cache.edited_fields(ISIN) == frozenset({"coupon"})
    cache.save(
        {"isin": ISIN, "company": "Acme Ltd", "coupon": 8.75, "rating": "AA", "source": "nse"}
    )
    row = cache.lookup(ISIN)
    assert row["coupon"] == 9.0
    assert row["company"] == "Acme Ltd"
    assert row["rating"] == "AA"
    assert row["source"] == "nse"


def test_a_non_edited_field_is_still_refreshed(db_path):
    cache = BondMasterCache(db_path)
    cache.save({"isin": ISIN, "company": "Acme", "coupon": 9.0, "source": "nsdl"})
    cache.save({"isin": ISIN, "company": "Acme Ltd", "coupon": 8.75, "source": "nse"})
    row = cache.lookup(ISIN)
    assert row["coupon"] == 8.75
    assert row["company"] == "Acme Ltd"


def test_edit_preserve_without_an_existing_row_keeps_the_incoming_value(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    cache = BondMasterCache(db_path)
    cache.mark_edited(ISIN, "coupon")
    cache.save({"isin": ISIN, "coupon": 8.75, "source": "nse"})
    assert cache.lookup(ISIN)["coupon"] == 8.75


def test_mark_edited_ignores_unknown_fields(db_path):
    cache = BondMasterCache(db_path)
    cache.mark_edited(ISIN, "not_a_field", "coupon")
    assert cache.edited_fields(ISIN) == frozenset({"coupon"})


def test_offer_exposes_fetched_at_as_the_as_of_date(tmp_path):
    now = [1_700_000_000.0]
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    cache = BondMasterCache(db_path, clock=lambda: now[0])
    cache.save({"isin": ISIN, "company": "Acme", "coupon": 8.75, "source": "nsdl"})
    offer = cache.offer(ISIN)
    assert offer["as_of"] == ASOF_AT_1700000000
    assert offer["fetched_at"] == ASOF_AT_1700000000
    assert offer["coupon"] == 8.75
    assert cache.as_of(ISIN) == ASOF_AT_1700000000
    assert cache.offer("INE0000000009") is None
    assert cache.as_of("INE0000000009") is None


def test_a_partial_refresh_does_not_null_stored_facts(db_path):
    cache = BondMasterCache(db_path)
    cache.save(
        {
            "isin": ISIN,
            "company": "Acme",
            "coupon": 8.75,
            "rating": "AA+",
            "rating_agency": "CRISIL",
            "issuer_type": "ncd",
            "listing_status": "listed",
            "maturity": "2030-03-31",
            "source": "NSDL",
        }
    )
    before = cache.lookup(ISIN)
    cache.save({"isin": ISIN, "company": "Acme", "coupon": 8.75, "source": "RBI"})
    after = cache.lookup(ISIN)
    assert after["rating"] == "AA+"
    assert after["rating_agency"] == "CRISIL"
    assert after["issuer_type"] == "ncd"
    assert after["listing_status"] == "listed"
    assert after["maturity"] == "2030-03-31"
    assert after["source"] == "RBI"
    assert after["fetched_at"] == before["fetched_at"]
