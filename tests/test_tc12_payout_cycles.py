import pytest

from src.db import get_conn
from src.phase4 import payout_schedule
from src.validators import AppError


def insert_bond(conn, company, isin, start_date, tenure, interest=None, payment_type=None):
    conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
        "tenure_months, credit_day, payment_type, interest_payout) "
        "VALUES (?, ?, ?, 10000, 12000, ?, ?, ?, 5, ?, ?)",
        (company, isin, company, start_date, f"end-{isin}", tenure, payment_type, interest),
    )
    return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def months_of(schedule):
    return [item["month"] for item in schedule["instances"]]


def test_tc12_quarterly_schedule_from_sep2025_over_24_months(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "QCo", "INETC12001", "2025-09-05", 24, 12000.0, "4 Quartely")
        schedule = payout_schedule(conn, bond_id, "quarterly")
    assert months_of(schedule) == [
        "2025-09",
        "2025-12",
        "2026-03",
        "2026-06",
        "2026-09",
        "2026-12",
        "2027-03",
        "2027-06",
    ]
    assert schedule["instance_count"] == 8
    assert all(item["amount"] == pytest.approx(1500.0) for item in schedule["instances"])
    assert all(item["partial"] is False for item in schedule["instances"])
    assert schedule["total_amount"] == pytest.approx(12000.0)


def test_tc12_yearly_schedule_one_due_date_per_year(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "YCo", "INETC12002", "2025-09-05", 36, 36000.0, "Yearly")
        schedule = payout_schedule(conn, bond_id, "yearly")
    assert months_of(schedule) == ["2025-09", "2026-09", "2027-09"]
    assert all(item["amount"] == pytest.approx(12000.0) for item in schedule["instances"])
    assert all(item["months_covered"] == 12 for item in schedule["instances"])
    assert schedule["total_amount"] == pytest.approx(36000.0)


def test_tc12_monthly_schedule_every_month(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "MCo", "INETC12003", "2025-09-05", 3, 3000.0, "1 Monthly")
        schedule = payout_schedule(conn, bond_id, "monthly")
    assert months_of(schedule) == ["2025-09", "2025-10", "2025-11"]
    assert all(item["amount"] == pytest.approx(1000.0) for item in schedule["instances"])


def test_tc12_quarterly_tenure_not_divisible_last_partial_pays_remainder(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "Q10", "INETC12004", "2025-09-05", 10, 10000.0, "4 Quartely")
        schedule = payout_schedule(conn, bond_id, "quarterly")
    assert months_of(schedule) == ["2025-09", "2025-12", "2026-03", "2026-06"]
    assert schedule["instance_count"] == 4
    covered = [item["months_covered"] for item in schedule["instances"]]
    assert covered == [3, 3, 3, 1]
    amounts = [item["amount"] for item in schedule["instances"]]
    assert amounts[0] == pytest.approx(3000.0)
    assert amounts[-1] == pytest.approx(1000.0)
    assert schedule["instances"][-1]["partial"] is True
    assert schedule["instances"][0]["partial"] is False
    assert schedule["total_amount"] == pytest.approx(10000.0)
    assert schedule["total_tds"] == pytest.approx(1000.0)
    assert schedule["total_net"] == pytest.approx(9000.0)


def test_tc12_instance_tds_and_net_follow_af35(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "QCo2", "INETC12005", "2025-09-05", 12, 12000.0, "4 Quartely")
        schedule = payout_schedule(conn, bond_id, "quarterly")
    first = schedule["instances"][0]
    assert first["tds"] == pytest.approx(300.0)
    assert first["net"] == pytest.approx(2700.0)
    assert first["net"] == pytest.approx(first["amount"] - first["tds"])


def test_tc12_unknown_cycle_raises_named_error(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "QCo3", "INETC12006", "2025-09-05", 12, 12000.0, "4 Quartely")
        with pytest.raises(AppError) as exc_info:
            payout_schedule(conn, bond_id, "fortnightly")
    assert exc_info.value.code == "ERR-due-dates"


def test_tc12_cycle_normalized_case_and_whitespace(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "MCo2", "INETC12007", "2025-09-05", 3, 3000.0, "1 Monthly")
        schedule = payout_schedule(conn, bond_id, " MONTHLY ")
    assert schedule["cycle"] == "monthly"
    assert months_of(schedule) == ["2025-09", "2025-10", "2025-11"]


def test_tc12_unknown_bond_raises_named_error(db_path):
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            payout_schedule(conn, 424242, "monthly")
    assert exc_info.value.code == "ERR-due-dates"
    assert "424242" in exc_info.value.message


def test_tc12_unparseable_start_month_raises_named_error(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day) VALUES ('Bad', 'INETC12008', 'Bad', 100, "
            "'not-a-date', 'also-bad', 12, 5)"
        )
        bond_id = conn.execute("SELECT id FROM bonds WHERE isin = 'INETC12008'").fetchone()["id"]
        with pytest.raises(AppError) as exc_info:
            payout_schedule(conn, bond_id, "monthly")
    assert exc_info.value.code == "ERR-due-dates"


def test_tc12_non_positive_tenure_raises_named_error(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day) VALUES ('Zero', 'INETC12009', 'Zero', 100, "
            "'2025-01-05', '2025-01-05', 0, 5)"
        )
        bond_id = conn.execute("SELECT id FROM bonds WHERE isin = 'INETC12009'").fetchone()["id"]
        with pytest.raises(AppError) as exc_info:
            payout_schedule(conn, bond_id, "monthly")
    assert exc_info.value.code == "ERR-due-dates"


def test_tc12_schedule_without_interest_shows_dates_only(db_path):
    with get_conn(db_path) as conn:
        bond_id = insert_bond(conn, "NoInt", "INETC12010", "2025-09-05", 6, None, "1 Monthly")
        schedule = payout_schedule(conn, bond_id, "monthly")
    assert months_of(schedule) == [
        "2025-09",
        "2025-10",
        "2025-11",
        "2025-12",
        "2026-01",
        "2026-02",
    ]
    assert all(item["amount"] is None for item in schedule["instances"])
    assert schedule["total_amount"] is None
