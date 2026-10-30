from pathlib import Path

import pytest

from conftest import add_bond
from src.db import get_conn
from src.import_xlsm import (
    WATCH_LIST_SHEET_TITLE,
    extract_watch_list,
    import_workbook,
    locate_sheet,
    open_workbook,
)
from src.phase4 import bond_discount_detail, discount_report
from src.validators import AppError

WORKBOOK = Path(
    "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)


def insert_raw(conn, company, isin, amount, maturity=None, face=None, watch_inv=None):
    conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
        "tenure_months, credit_day, face_value, watch_investment) "
        "VALUES (?, ?, ?, ?, ?, '2025-01-05', '2026-01-05', 12, 5, ?, ?)",
        (company, isin, company, amount, maturity, face, watch_inv),
    )
    return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def test_tc16_null_discount_renders_not_recorded(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_raw(conn, "NullCo", "INETC16001", 50000.0)
        detail = bond_discount_detail(conn, bond_id)
    assert detail["discount"] is None
    assert detail["display"] == "not recorded"
    assert detail["source"] == "not-recorded"


def test_tc16_stored_zero_discount_renders_as_real_zero(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_raw(conn, "ZeroCo", "INETC16002", 1000.0, face=1000.0, watch_inv=1000.0)
        detail = bond_discount_detail(conn, bond_id)
    assert detail["discount"] == 0.0
    assert detail["display"] == "0.00"
    assert detail["source"] == "watch-lgh"


def test_tc16_unknown_bond_raises_named_error(db_path):
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            bond_discount_detail(conn, 99999)
    assert exc_info.value.code == "ERR-bond-discount"
    assert "99999" in exc_info.value.message


def test_tc16_watch_lgh_pattern_face_minus_investment(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_raw(
            conn, "PaisaloLike", "INETC16003", 99626.52, face=100000.0, watch_inv=99626.52
        )
        detail = bond_discount_detail(conn, bond_id)
    assert detail["discount"] == pytest.approx(373.48, abs=1e-6)
    assert detail["source"] == "watch-lgh"


def test_tc16_maturity_minus_amount_fallback_where_columns_missing(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_raw(conn, "FallbackCo", "INETC16004", 100000.0, maturity=101500.5)
        detail = bond_discount_detail(conn, bond_id)
    assert detail["discount"] == pytest.approx(1500.5, abs=1e-9)
    assert detail["source"] == "maturity-minus-amount"


def test_tc16_report_totals_and_not_recorded_counts(db_path):
    with get_conn(db_path) as conn:
        insert_raw(conn, "A", "INETC16005", 99626.52, face=100000.0, watch_inv=99626.52)
        insert_raw(conn, "B", "INETC16006", 50000.0)
        report = discount_report(conn)
    totals = report["totals"]
    assert totals["bond_count"] == 2
    assert totals["recorded"] == 1
    assert totals["not_recorded"] == 1
    assert totals["discount"] == pytest.approx(373.48, abs=1e-6)
    by_isin = {row["isin"]: row for row in report["rows"]}
    assert by_isin["INETC16006"]["discount"] is None
    assert by_isin["INETC16006"]["recorded"] is False


def test_tc16_negative_discount_is_real_recorded_value(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_raw(conn, "PremiumCo", "INETC16007", 10031.75, face=10000.0, watch_inv=10031.75)
        detail = bond_discount_detail(conn, bond_id)
    assert detail["discount"] == pytest.approx(-31.75, abs=1e-9)
    assert detail["display"] == "-31.75"


@pytest.mark.remote
def test_tc16_real_workbook_discount_matches_watch_l_column(tmp_path):
    db_path = tmp_path / "tc16_real.db"
    summary = import_workbook(WORKBOOK, db_path)
    assert summary["bonds"] == 15
    workbook = open_workbook(WORKBOOK)
    try:
        sheet = locate_sheet(workbook.values, WATCH_LIST_SHEET_TITLE)
        watch = extract_watch_list(workbook.values[sheet])
    finally:
        workbook.values.close()
        workbook.formulas.close()
    expected = {
        str(record["isin"]).strip().upper(): float(record["discount_amount"])
        for record in watch
        if record.get("discount_amount") is not None
    }
    assert len(expected) == 15
    with get_conn(db_path) as conn:
        report = discount_report(conn)
    assert report["totals"]["recorded"] == 15
    for row in report["rows"]:
        isin = str(row["isin"]).strip().upper()
        assert isin in expected
        assert row["discount"] == pytest.approx(expected[isin], abs=1e-6)
        assert row["source"] == "watch-lgh"
    assert report["totals"]["discount"] == pytest.approx(sum(expected.values()), abs=1e-6)
