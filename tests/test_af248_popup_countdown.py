"""TC-AF-14 (popup) + TC-AF-15 (countdown) acceptance tests - wave P9-2, issue #248."""
import re
from pathlib import Path

from src.app import create_app
from src.bond_master.cache import BondMasterCache
from src.views.watch import POSITION_FIELDS

# === TC-AF-14 (W1) ===
AF14_ISIN = "INE205A07DV2"
AF14_COMPANY = "Acme Infrastructure Ltd"
AF14_COUPON = "8.75"
AF14_MATURITY = "2030-03-31"
AF14_RATING = "AA+"
AF14_NSDL_MASTER = "nsdl_corporate_bond_master.json"
AF14_ROOT = Path(__file__).resolve().parents[1]
AF14_FIXTURES = Path(__file__).resolve().parent / "bond_master" / "fixtures"
AF14_TEMPLATE = (AF14_ROOT / "src" / "templates" / "watch.html").read_text(encoding="utf-8")
AF14_APPLY_FIELDS = (
    "company",
    "rating",
    "rating_agency",
    "coupon_pct",
    "face_value",
    "issuer_type",
    "payout_cycle",
    "secured",
)


def _af14_transport():
    payload = (AF14_FIXTURES / AF14_NSDL_MASTER).read_text(encoding="utf-8")

    def transport(url, timeout):
        return payload

    return transport


def _af14_client(db_path, body=None):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    app.config["BOND_MASTER_TRANSPORT"] = (
        _af14_transport() if body is None else (lambda url, timeout: body)
    )
    app.extensions["bond_master_cache"] = BondMasterCache(db_path, cooldown_seconds=0)
    return app.test_client()


def _af14_found_html(db_path):
    return _af14_client(db_path).get(f"/watch?isin={AF14_ISIN}").get_data(as_text=True)


def _af14_popup(html):
    start = html.index('id="fetch-details"')
    end = html.index("table-wrap watch-scroll", start)
    return html[start:end]


def test_tc_af_14_popup_carries_facts_source_badge_and_asof(db_path):
    popup = _af14_popup(_af14_found_html(db_path))
    assert 'id="fetch-details-apply"' in popup
    assert 'id="fetch-details-dismiss"' in popup
    assert 'id="fetch-details-asof"' in popup and "As of" in popup
    for fact in ("company", "coupon", "maturity", "rating"):
        assert f'data-fetch-detail="{fact}"' in popup, fact
    assert AF14_COMPANY in popup
    assert AF14_COUPON in popup
    assert AF14_MATURITY in popup
    assert AF14_RATING in popup
    assert 'data-fetch-source="company">NSDL<' in popup
    assert 'data-fetch-source="coupon">NSDL<' in popup
    assert 'data-fetch-source="maturity">NSDL<' in popup
    assert 'data-fetch-source="rating">NSDL<' in popup


def test_tc_af_14_popup_is_keyed_to_the_fetched_isin(db_path):
    html = _af14_found_html(db_path)
    popup = _af14_popup(html)
    assert f'data-fetch-isin="{AF14_ISIN}"' in popup


def test_tc_af_14_apply_writes_only_instrument_fact_fields(db_path):
    html = _af14_found_html(db_path)
    popup = _af14_popup(html)
    applied = re.findall(r'data-apply-field="([a-z_]+)"', popup)
    assert applied
    assert set(applied) <= set(AF14_APPLY_FIELDS)
    assert "qty" not in applied
    assert set(applied).isdisjoint(POSITION_FIELDS)
    assert re.search(r'data-apply-field="coupon_pct" data-apply-value="8\.75"', popup)
    assert re.search(r'data-apply-field="company" data-apply-value="Acme Infrastructure Ltd"', popup)


def test_tc_af_14_position_facts_stay_empty_in_the_popup_path(db_path):
    html = _af14_found_html(db_path)
    assert 'name="watch_investment" step="any" min="0" placeholder="0.00" value=""' in html
    assert 'name="qty" step="1" min="1" placeholder="1" value=""' in html
    for name in ("amount", "start_date", "end_date", "credit_day"):
        assert f'name="{name}"' not in html, name


def test_tc_af_14_popup_is_absent_when_the_fetch_returns_no_facts(db_path):
    html = _af14_client(db_path, body='{"records": []}').get(
        f"/watch?isin={AF14_ISIN}"
    ).get_data(as_text=True)
    assert 'id="fetch-details"' not in html
    assert 'data-fetch-state="notfound" hidden' not in html


def test_tc_af_14_template_declares_apply_and_dismiss_wiring():
    assert 'id="fetch-details-apply"' in AF14_TEMPLATE
    assert 'id="fetch-details-dismiss"' in AF14_TEMPLATE
    assert "function applyFetchedFacts()" in AF14_TEMPLATE
    assert "function clearFetchedFacts()" in AF14_TEMPLATE
    assert 'applyButton.addEventListener("click"' in AF14_TEMPLATE
    assert 'dismissButton.addEventListener("click"' in AF14_TEMPLATE
    assert 'popup.querySelectorAll("[data-apply-field]")' in AF14_TEMPLATE


def test_tc_af_13_client_half_payload_is_isin_plus_dirty_only():
    assert '"isin=" + encodeURIComponent(isinValue())' in AF14_TEMPLATE
    assert '"dirty=" + encodeURIComponent(Object.keys(dirty).join(","))' in AF14_TEMPLATE
    assert "Object.keys(dirty).forEach" in AF14_TEMPLATE
    assert 'query += encodeURIComponent(element.name)' not in AF14_TEMPLATE


def test_tc_af_13_client_half_isin_change_invalidates_facts_before_response():
    assert "function invalidateOnIsinChange()" in AF14_TEMPLATE
    assert 'isin.addEventListener("input", invalidateOnIsinChange)' in AF14_TEMPLATE
    assert "closePopup();" in AF14_TEMPLATE
    assert "clearFetchedFacts();" in AF14_TEMPLATE
    assert 'showState("idle")' in AF14_TEMPLATE
    assert 'data-fetch-isin="{{ fetch.isin }}"' in AF14_TEMPLATE


# === end TC-AF-14 (W1) ===
