import io
import zipfile
from pathlib import Path

import pytest

from src.bond_master.base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OK,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
)
from src.bond_master.cdsl import (
    CORPDB_URL,
    POPUP_URL,
    PREF_XLSX_URL,
    SEC_XLSX_URL,
    CdslAdapter,
    parse_xlsx,
    PREF_KNOWN_COLUMNS,
)

FIXTURES = Path(__file__).parent / "fixtures"
PREF_FIXTURE = FIXTURES / "cdsl_preference_shares.xlsx"
SEC_FIXTURE = FIXTURES / "cdsl_securitised_debt.xlsx"
POPUP_FIXTURE = FIXTURES / "cdsl_popup_isin.html"
CORPDB_FIXTURE = FIXTURES / "cdsl_corpbond_database.html"

ISIN = "INE020B08831"
POPUP_URL_ISIN = POPUP_URL + ISIN
CORPDB_URL_ISIN = CORPDB_URL + ISIN


def make_adapter(pages):
    calls = []

    def transport(url, timeout):
        calls.append(url)
        payload = pages.get(url)
        if isinstance(payload, Exception):
            raise payload
        if payload is None:
            raise AssertionError(f"unexpected URL: {url}")
        return payload

    return CdslAdapter(transport=transport), calls


def load_pref():
    return PREF_FIXTURE.read_bytes()


def load_sec():
    return SEC_FIXTURE.read_bytes()


def load_popup():
    return POPUP_FIXTURE.read_text(encoding="utf-8")


def load_corpdb():
    return CORPDB_FIXTURE.read_text(encoding="utf-8")


def make_xlsx(headers, rows):
    """Minimal shared-string XLSX for schema-drift tests."""
    used = []

    def sid(value):
        if value not in used:
            used.append(value)
        return used.index(value)

    header_cells = "".join(
        f'<c r="{chr(65 + i)}1" t="s"><v>{sid(h)}</v></c>' for i, h in enumerate(headers)
    )
    body = [f'<row r="1">{header_cells}</row>']
    for r, row in enumerate(rows, start=2):
        cells = "".join(
            f'<c r="{chr(65 + i)}{r}" t="s"><v>{sid(v)}</v></c>'
            for i, v in enumerate(row)
            if v is not None
        )
        body.append(f'<row r="{r}">{cells}</row>')
    sst = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        f'<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        f'count="{len(used)}" uniqueCount="{len(used)}">'
        + "".join(f"<si><t>{v}</t></si>" for v in used)
        + "</sst>"
    )
    sheet = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetData>{"".join(body)}</sheetData></worksheet>'
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("xl/sharedStrings.xml", sst)
        zf.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def test_pref_parses_real_fixture():
    adapter, calls = make_adapter({PREF_XLSX_URL: load_pref()})
    result = adapter.fetch_preference_shares()
    assert result["failure_code"] == FAILURE_OK
    assert calls == [PREF_XLSX_URL]
    records = result["records"]
    assert len(records) >= 60
    first = records[0]
    assert first["isin"] == "INE06RH04019"
    assert first["company"] == "BALIRAJA SAKHAR KARKHANA LIMITED"
    assert first["issue_date"] == "2017-01-31"
    assert first["maturity"] == "2037-01-30"
    assert first["face_value"] == 10.0
    assert first["issue_amount"] == 250000000.0
    assert first["listing_status"] == "unlisted"
    assert first["security_type"] == "Preference Shares"
    assert first["source"] == "CDSL"
    assert first["as_of"]
    assert result["drift"] == []


def test_pref_dates_and_listing_normalized():
    adapter, _ = make_adapter({PREF_XLSX_URL: load_pref()})
    records = adapter.fetch_preference_shares()["records"]
    for record in records:
        assert record["listing_status"] in ("listed", "unlisted", "unknown")
        if record["issue_date"]:
            assert len(record["issue_date"]) == 10 and record["issue_date"][4] == "-"
        if record["maturity"]:
            assert len(record["maturity"]) == 10 and record["maturity"][4] == "-"


def test_sec_parses_real_fixture_with_coupon():
    adapter, calls = make_adapter({SEC_XLSX_URL: load_sec()})
    result = adapter.fetch_securitised()
    assert result["failure_code"] == FAILURE_OK
    assert calls == [SEC_XLSX_URL]
    records = result["records"]
    assert len(records) >= 60
    first = records[0]
    assert first["isin"] == "INE0VIC15015"
    assert first["security_type"] == "Pass Through Certificates"
    assert first["coupon"] == 9.9
    assert first["issue_date"] == "2024-04-22"
    assert first["maturity"] == "2028-01-25"
    assert first["listing_status"] is None
    assert first["source"] == "CDSL"
    assert first["as_of"]
    assert result["drift"] == []


def test_html_body_is_blocked():
    adapter, _ = make_adapter({PREF_XLSX_URL: "<html>Access Denied</html>"})
    result = adapter.fetch_preference_shares()
    assert result["failure_code"] == FAILURE_BLOCKED


def test_non_zip_body_is_malformed():
    adapter, _ = make_adapter({SEC_XLSX_URL: b"not a zip file"})
    result = adapter.fetch_securitised()
    assert result["failure_code"] == FAILURE_MALFORMED


def test_timeout_is_timeout():
    adapter, _ = make_adapter({PREF_XLSX_URL: TimeoutError("t")})
    assert adapter.fetch_preference_shares()["failure_code"] == FAILURE_TIMEOUT


def test_connection_error_is_unreachable():
    adapter, _ = make_adapter({SEC_XLSX_URL: ConnectionError("x")})
    assert adapter.fetch_securitised()["failure_code"] == FAILURE_UNREACHABLE


def test_missing_required_column_is_malformed():
    payload = make_xlsx(["Issuer Name", "Face Value"], [["A Ltd", "100"]])
    with pytest.raises(Exception) as exc:
        parse_xlsx(payload, PREF_KNOWN_COLUMNS)
    assert getattr(exc.value, "failure_code", None) == FAILURE_MALFORMED


def test_unknown_header_logged_as_drift():
    payload = make_xlsx(
        ["ISIN", "Issuer Name", "BRAND_NEW_COL"],
        [["INE06RH04019", "A Ltd", "x"]],
    )
    drift = []
    rows = parse_xlsx(payload, PREF_KNOWN_COLUMNS, drift=drift)
    assert len(rows) == 1
    assert "BRAND_NEW_COL" in drift


def test_popup_parses_real_fixture():
    adapter, calls = make_adapter({
        POPUP_URL_ISIN: load_popup(),
        CORPDB_URL_ISIN: load_corpdb(),
    })
    result = adapter.fetch_isin_detail(ISIN)
    assert result["failure_code"] == FAILURE_OK
    assert calls == [POPUP_URL_ISIN, CORPDB_URL_ISIN]
    record = result["record"]
    assert record["isin"] == ISIN
    assert record["description"].startswith("REC LTD")
    assert record["short_name"] == "RECL 8.82 120423"
    assert record["isin_status"] == "Permanently Inactive"
    assert record["listing_status"] == "listed"
    assert record["paid_up_value"] == 1000000.0
    assert "REC LIMITED" in record["address"]
    assert "BEETAL" in record["rta"]


def test_corpdb_fields_parsed_from_spans_and_rating_table():
    adapter, _ = make_adapter({
        POPUP_URL_ISIN: load_popup(),
        CORPDB_URL_ISIN: load_corpdb(),
    })
    record = adapter.fetch_isin_detail(ISIN)["record"]
    assert record["company"] == "RURAL ELECTRIFICATION CORPORATION LIMITED"
    assert record["face_value"] == 1000000.0
    assert record["coupon"] == 8.82
    assert record["coupon_basis"] == "Fixed"
    assert record["coupon_type"] == "Simple"
    assert record["redemption_date"] == "2023-04-12"
    assert record["issue_size"] == 43000000000.0
    assert record["issue_price"] == 1000000.0
    assert len(record["ratings"]) >= 3
    assert record["rating"] == "AAA"
    assert record["rating_agency"] == "CARE Ratings Limited"
    assert record["rating_date"] == "2023-05-16"
    assert record["outlook"] == "Stable"
    latest = next(r for r in record["ratings"] if r["agency"] == "CARE Ratings Limited")
    assert latest["action"] is None
    assert latest["watch"] is None
    assert latest["status"] == "Verified by Agency"
    assert record["source"] == "CDSL"
    assert record["as_of"]


def test_invalid_isin_rejected_before_fetch():
    adapter, calls = make_adapter({})
    result = adapter.fetch_isin_detail("NOTANISIN")
    assert result["failure_code"] == FAILURE_INVALID_ISIN
    assert result["record"] is None
    assert calls == []


def test_popup_without_isin_is_not_found():
    adapter, _ = make_adapter({
        POPUP_URL_ISIN: "<html><body>Object moved</body></html>",
    })
    result = adapter.fetch_isin_detail(ISIN)
    assert result["failure_code"] == FAILURE_NOT_FOUND
    assert result["record"] is None


def test_cloudflare_challenge_is_blocked():
    adapter, _ = make_adapter({
        POPUP_URL_ISIN: "<html><body>Just a moment... cf-chl</body></html>",
    })
    result = adapter.fetch_isin_detail(ISIN)
    assert result["failure_code"] == FAILURE_BLOCKED


def test_corpdb_failure_returns_no_record():
    adapter, _ = make_adapter({
        POPUP_URL_ISIN: load_popup(),
        CORPDB_URL_ISIN: TimeoutError("t"),
    })
    result = adapter.fetch_isin_detail(ISIN)
    assert result["failure_code"] == FAILURE_TIMEOUT
    assert result["record"] is None
