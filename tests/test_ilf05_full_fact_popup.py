import pytest
pytest.skip("Retired per issue #337: old frontend removal", allow_module_level=True)
"""TC-ILF-05 full-fact popup tests - batch B3, issue #283."""
import re

from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.views.watch import ONLINE_FACT_FIELDS, SNAPSHOT_FACT_FIELDS
from tests.test_af246_isin_autofetch_form import cache_seed
from tests.test_af248_popup_countdown import (
    AF14_ISIN,
    _af14_popup,
    _af14_transport,
)

ILF05_ONLINE_FACTS = (
    "company",
    "coupon",
    "maturity",
    "rating",
    "rating_agency",
    "issuer_type",
    "payout_cycle",
    "secured",
)


def _ilf05_client(db_path, transport):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = transport
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client()


def _popup_fact_names(popup):
    return re.findall(r'data-fetch-detail="([^"]+)"', popup)


def _popup_sources(popup):
    return dict(re.findall(r'data-fetch-source="([^"]+)"[^>]*>([^<]*)<', popup))


def test_tc_ilf_05_online_popup_shows_eight_facts_with_per_field_sources(db_path):
    html = _ilf05_client(db_path, _af14_transport()).get(f"/watch?isin={AF14_ISIN}").get_data(as_text=True)
    popup = _af14_popup(html)
    assert tuple(_popup_fact_names(popup)) == ILF05_ONLINE_FACTS
    assert len(_popup_fact_names(popup)) == 8
    sources = _popup_sources(popup)
    for fact in ILF05_ONLINE_FACTS:
        assert sources.get(fact), f"missing per-field source for {fact}"
    assert "face_value" not in _popup_fact_names(popup)
    assert "listing_status" not in _popup_fact_names(popup)


def test_tc_ilf_05_online_popup_facts_match_contract(db_path):
    assert tuple(ONLINE_FACT_FIELDS) == ILF05_ONLINE_FACTS
    assert tuple(SNAPSHOT_FACT_FIELDS) == ("company", "coupon", "maturity")


def test_tc_ilf_05_persisted_hit_popup_shows_full_facts_with_sources(db_path):
    cache_seed(db_path)

    def offline_transport(url, timeout):
        raise OSError("network unreachable")

    html = _ilf05_client(db_path, offline_transport).get(f"/watch?isin={AF14_ISIN}").get_data(as_text=True)
    popup = _af14_popup(html)
    assert sorted(_popup_fact_names(popup)) == sorted(f for f in ILF05_ONLINE_FACTS if f != "coupon")
    sources = _popup_sources(popup)
    assert all(sources.get(fact) == "NSDL" for fact in _popup_fact_names(popup))


def test_tc_ilf_05_snapshot_only_popup_shows_three_snapshot_facts(db_path):
    snapshot_isin = "IN0019790024"

    def offline_transport(url, timeout):
        raise OSError("network unreachable")

    html = _ilf05_client(db_path, offline_transport).get(f"/watch?isin={snapshot_isin}").get_data(as_text=True)
    popup = _af14_popup(html)
    assert sorted(_popup_fact_names(popup)) == ["company", "coupon", "maturity"]
    assert set(_popup_sources(popup).values()) == {"india-isin-data (CC0)"}


def test_tc_ilf_05_unpublished_fields_stay_editable(db_path):
    html = _ilf05_client(db_path, _af14_transport()).get(f"/watch?isin={AF14_ISIN}").get_data(as_text=True)
    for name in ("face_value", "listing_status", "payout_cycle", "secured"):
        match = re.search(rf'<[^>]*name="{name}"[^>]*>', html)
        assert match, f"form field {name} missing"
        assert "readonly" not in match.group(0)
        assert "disabled" not in match.group(0)
