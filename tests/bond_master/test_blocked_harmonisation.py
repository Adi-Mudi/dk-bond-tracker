from pathlib import Path

from src.bond_master import nsdl
from src.bond_master.base import FAILURE_BLOCKED

FIXTURES = Path(__file__).resolve().parent / "fixtures"
ISIN = "INE205A07DV2"


def _blocked_page(name):
    return (FIXTURES / name).read_text(encoding="utf-8")


def _transport(payload):
    return lambda url, timeout: payload


def test_the_nsdl_adapter_maps_a_waf_page_at_http_200_to_blocked():
    adapter = nsdl.NsdlAdapter(
        transport=_transport(_blocked_page("blocked_page.html")),
        retry_delay=0,
        sleep=lambda seconds: None,
    )
    assert adapter.fetch(ISIN).failure_code == FAILURE_BLOCKED
