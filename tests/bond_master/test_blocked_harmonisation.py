from pathlib import Path

from src.bond_master import bse, nsdl, nse, rbi
from src.bond_master.base import FAILURE_BLOCKED

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ISIN = "INE205A07DV2"


def _blocked_page(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _transport(payload):
    return lambda url, timeout: payload


def _adapters(html):
    return {
        "NSDL": nsdl.NsdlAdapter(transport=_transport(html)),
        "RBI": rbi.RbiAdapter(transport=_transport(html)),
        "NSE": nse.NseAdapter(transport=_transport(html)),
        "BSE": bse.BseAdapter(transport=_transport(html)),
    }


def test_every_source_maps_a_waf_page_at_http_200_to_blocked():
    for name, adapter in _adapters(_blocked_page("nse_blocked_page.html")).items():
        assert adapter.fetch(ISIN).failure_code == FAILURE_BLOCKED, name


def test_the_nse_and_bse_blocked_fixtures_both_read_blocked():
    assert nse.NseAdapter(
        transport=_transport(_blocked_page("nse_blocked_page.html"))
    ).fetch(ISIN).failure_code == FAILURE_BLOCKED
    assert bse.BseAdapter(
        transport=_transport(_blocked_page("bse_blocked_page.html"))
    ).fetch(ISIN).failure_code == FAILURE_BLOCKED
