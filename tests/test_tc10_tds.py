import pytest

from src.db import get_conn
from src.phase4 import tds_deduction, tds_report


def insert_watch_bond(conn, company, isin, interest, tenure, payment_type=None):
    conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
        "tenure_months, credit_day, payment_type, interest_payout) "
        "VALUES (?, ?, ?, 10000, 12000, '2025-01-05', '2026-01-05', ?, 5, ?, ?)",
        (company, isin, company, tenure, payment_type, interest),
    )
    return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def test_tc10_tds_math_on_10000_payout():
    result = tds_deduction(10000)
    assert result["rate"] == 0.10
    assert result["tds"] == pytest.approx(1000.0)
    assert result["net"] == pytest.approx(9000.0)
    assert result["net"] == pytest.approx(result["payout"] - result["tds"])


def test_tc10_tds_zero_payout_is_valid_computation():
    result = tds_deduction(0)
    assert result["tds"] == 0.0
    assert result["net"] == 0.0


def test_tc10_tds_custom_rate_within_bounds():
    result = tds_deduction(2000, 0.05)
    assert result["tds"] == pytest.approx(100.0)
    assert result["net"] == pytest.approx(1900.0)


def test_tc10_report_per_month_tds_and_net(db_path):
    with get_conn(db_path) as conn:
        insert_watch_bond(conn, "MonthlyCo", "INETC10001", 18000.0, 12, "1 Monthly")
        report = tds_report(conn)
    row = report["rows"][0]
    assert row["computable"] is True
    assert row["per_month"] == pytest.approx(1500.0)
    assert row["tds"] == pytest.approx(150.0)
    assert row["net"] == pytest.approx(1350.0)
    assert row["net"] == pytest.approx(row["per_month"] - row["tds"])
    assert row["annual_gross"] == pytest.approx(18000.0)
    assert row["annual_tds"] == pytest.approx(1800.0)
    assert row["annual_net"] == pytest.approx(16200.0)


def test_tc10_report_quarterly_per_month_matches_workbook_o_pattern(db_path):
    with get_conn(db_path) as conn:
        insert_watch_bond(conn, "QuarterlyCo", "INETC10002", 9000.0, 12, "4 Quartely")
        report = tds_report(conn)
    row = report["rows"][0]
    assert row["cycle"] == "quarterly"
    assert row["per_month"] == pytest.approx(2250.0)
    assert row["tds"] == pytest.approx(225.0)
    assert row["net"] == pytest.approx(2025.0)


def test_tc10_report_totals_and_non_computable_rows(db_path):
    with get_conn(db_path) as conn:
        insert_watch_bond(conn, "A", "INETC10003", 12000.0, 12, "1 Monthly")
        insert_watch_bond(conn, "B", "INETC10004", 24000.0, 12, "1 Monthly")
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day) VALUES ('Manual', 'INETC10005', 'Manual', 5000, "
            "'2025-01-05', '2026-01-05', 12, 5)"
        )
        report = tds_report(conn)
    totals = report["totals"]
    assert totals["computable"] == 2
    assert totals["not_computable"] == 1
    assert totals["annual_gross"] == pytest.approx(36000.0)
    assert totals["annual_tds"] == pytest.approx(3600.0)
    assert totals["annual_net"] == pytest.approx(32400.0)
    by_isin = {row["isin"]: row for row in report["rows"]}
    assert by_isin["INETC10005"]["computable"] is False
