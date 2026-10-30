from datetime import date
from pathlib import Path

import pytest

from src.analytics import bond_analytics, compute_watch_analytics
from src.app import create_app
from src.db import get_conn
from src.import_xlsm import (
    WATCH_LIST_SHEET_TITLE,
    extract_watch_list,
    import_workbook,
    locate_sheet,
    open_workbook,
)
from src.validators import add_months

WORKBOOK = Path(
    "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)

PAISALO = {
    "face": 100000.0,
    "principle": 99626.52,
    "interest": 17955.29,
    "tenure": 18,
    "qty": 1.0,
}


def excel_analytics(face, principle, interest, tenure, payment_type="1 Monthly", qty=1.0, tlp=None):
    discount = face - principle
    total_amount = principle + interest + discount
    quarterly = "quart" in payment_type.lower()
    per_month = (interest / tenure) * (3 if quarterly else 1)
    actual_per_month = (interest - discount) / tenure
    tds = per_month - (per_month * 10.0) / 100.0
    twelve_month = per_month * 12
    tlp_value = principle if tlp is None else tlp
    qty_tl = None if qty is None else tlp_value * qty
    return {
        "discount": discount,
        "total_amount": total_amount,
        "per_month": per_month,
        "actual_per_month": actual_per_month,
        "tds": tds,
        "twelve_month": twelve_month,
        "qty": qty,
        "qty_tl": qty_tl,
    }


@pytest.fixture
def db_path(tmp_path):
    path = tmp_path / "tc40.db"
    from src.db import init_db

    init_db(path)
    return path


def seed_watch_bond(db_path, company, isin, face, principle, interest, tenure, payment_type, qty, tlp=None):
    with get_conn(db_path) as conn:
        start = date(2025, 9, 3)
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
            "tenure_months, credit_day, status, face_value, tlp_amount, payment_type, "
            "interest_payout, qty, watch_investment) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                company,
                isin,
                company,
                principle * (qty or 1),
                principle,
                start.isoformat(),
                add_months(start, tenure).isoformat(),
                tenure,
                5,
                "On-going",
                face,
                tlp if tlp is not None else principle,
                payment_type,
                interest,
                qty,
                principle,
            ),
        )
        return cursor.lastrowid


def seed_plain_bond(db_path, company, isin, tenure=12, amount=50000.0):
    with get_conn(db_path) as conn:
        start = date(2025, 9, 3)
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
            "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                company,
                isin,
                company,
                amount,
                amount,
                start.isoformat(),
                add_months(start, tenure).isoformat(),
                tenure,
                5,
                "On-going",
            ),
        )
        return cursor.lastrowid


def test_analytics_match_excel_formulas_for_paisalo(db_path):
    seed_watch_bond(
        db_path, "Paisalo", "INE420C07130", PAISALO["face"], PAISALO["principle"],
        PAISALO["interest"], PAISALO["tenure"], "1 Monthly", PAISALO["qty"],
    )
    with get_conn(db_path) as conn:
        analytics = compute_watch_analytics(conn)
    expected = excel_analytics(
        PAISALO["face"], PAISALO["principle"], PAISALO["interest"], PAISALO["tenure"]
    )
    row = analytics[1]
    assert row["computable"] is True
    assert row["discount"] == pytest.approx(expected["discount"], abs=1e-9)
    assert row["per_month"] == pytest.approx(17955.29 / 18, abs=1e-9)
    assert row["actual_per_month"] == pytest.approx(expected["actual_per_month"], abs=1e-9)
    assert row["tds"] == pytest.approx(expected["tds"], abs=1e-9)
    assert row["twelve_month"] == pytest.approx(expected["twelve_month"], abs=1e-9)
    assert row["qty"] == 1.0
    assert row["qty_tl"] == pytest.approx(99626.52, abs=1e-9)


def test_quarterly_payment_type_triples_per_month(db_path):
    seed_watch_bond(
        db_path, "Arman", "INE109C07139", 10000.0, 10031.75, 2547.89, 27, "4 Quartely", 2.0,
    )
    with get_conn(db_path) as conn:
        analytics = compute_watch_analytics(conn)
    row = analytics[1]
    assert row["quarterly"] is True
    assert row["per_month"] == pytest.approx((2547.89 / 27) * 3, abs=1e-9)
    assert row["discount"] == pytest.approx(10000.0 - 10031.75, abs=1e-9)


def test_missing_watch_inputs_are_not_computable(db_path):
    seed_plain_bond(db_path, "Manual Add", "INE0000000001")
    with get_conn(db_path) as conn:
        analytics = compute_watch_analytics(conn)
    assert analytics[1] == {"computable": False}


def test_watch_page_shows_dash_for_non_computable(db_path):
    seed_plain_bond(db_path, "Manual Add", "INE0000000001")
    app = create_app(db_path)
    app.config["TESTING"] = True
    body = app.test_client().get("/watch").data.decode()
    assert "Manual Add" in body
    assert "analytics-discount" in body
    assert "&#8212;" in body


def test_bond_analytics_zero_tenure_raises_named_error():
    from src.validators import AppError

    with pytest.raises(AppError) as exc_info:
        bond_analytics(
            {
                "isin": "INE0000BAD01",
                "watch_investment": 100.0,
                "face_value": 100.0,
                "interest_payout": 10.0,
                "tenure_months": 0,
            }
        )
    assert exc_info.value.code == "ERR-watch-analytics"


@pytest.fixture(scope="module")
def imported(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("tc40_real") / "import_real.db"
    summary = import_workbook(WORKBOOK, db_path)
    return summary, db_path


def test_real_workbook_present():
    assert WORKBOOK.is_file()


def test_real_import_analytics_match_spike_formulas(imported):
    summary, db_path = imported
    workbook = open_workbook(WORKBOOK)
    try:
        name = locate_sheet(workbook.values, WATCH_LIST_SHEET_TITLE)
        watch_rows = extract_watch_list(workbook.values[name])
    finally:
        workbook.values.close()
        workbook.formulas.close()
    with get_conn(db_path) as conn:
        analytics = compute_watch_analytics(conn)
        isin_by_id = {
            row["id"]: str(row["isin"]).strip().upper()
            for row in conn.execute("SELECT id, isin FROM bonds").fetchall()
        }
    by_isin = {isin: analytics[bond_id] for bond_id, isin in isin_by_id.items()}
    matched = 0
    for record in watch_rows:
        isin = str(record["isin"]).strip().upper()
        row = by_isin[isin]
        assert row["computable"] is True
        face = float(record["face_value"])
        principle = float(record["investment"])
        interest = float(record["interest_payout"])
        tenure = int(record["tenure_months"])
        payment_type = str(record.get("payment_type") or "")
        qty = record.get("qty")
        qty = None if qty is None else float(qty)
        tlp = record.get("tlp_amount")
        tlp = None if tlp is None else float(tlp)
        expected = excel_analytics(face, principle, interest, tenure, payment_type, qty, tlp)
        assert row["discount"] == pytest.approx(expected["discount"], abs=1e-6)
        assert row["per_month"] == pytest.approx(expected["per_month"], abs=1e-6)
        assert row["actual_per_month"] == pytest.approx(expected["actual_per_month"], abs=1e-6)
        assert row["tds"] == pytest.approx(expected["tds"], abs=1e-6)
        assert row["twelve_month"] == pytest.approx(expected["twelve_month"], abs=1e-6)
        if qty is None:
            assert row["qty"] is None
            assert row["qty_tl"] is None
        else:
            assert row["qty"] == pytest.approx(qty, abs=1e-9)
            assert row["qty_tl"] == pytest.approx(expected["qty_tl"], abs=1e-6)
        matched += 1
    assert matched == 15


def test_real_watch_page_shows_computed_discount(imported):
    summary, db_path = imported
    app = create_app(db_path)
    app.config["TESTING"] = True
    body = app.test_client().get("/watch").data.decode()
    assert "373.48" in body
    assert "997.52" in body
    assert "INE420C07130" in body
