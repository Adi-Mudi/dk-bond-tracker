from datetime import date

from conftest import add_bond, add_payment, bond_status, month_sequence, pay_range
from src.db import get_conn
from src.queries import bond_month_totals, portfolio_totals, status_overview
from src.status import recompute_all


def seed_full_matrix(conn):
    bond_a = add_bond(conn, "Alpha", "INE000000005A", "2025-01-01", 12, amount=120000.0, maturity=120000.0)
    pay_range(conn, bond_a, "2025-01", 12, skip={"2025-03"}, amount=1000.0)
    bond_b = add_bond(conn, "Beta", "INE000000005B", "2025-01-01", 6, amount=60000.0, maturity=60000.0)
    pay_range(conn, bond_b, "2025-01", 6, amount=1000.0)
    bond_c = add_bond(conn, "Gamma", "INE000000005C", "2025-01-01", 3, amount=3000.0, maturity=3000.0)
    for month in month_sequence("2025-01", 3):
        if month == "2025-02":
            add_payment(conn, bond_c, month, 0.0, paid=0)
        else:
            add_payment(conn, bond_c, month, 1000.0)
    bond_d = add_bond(conn, "Delta", "INE000000005D", "2026-07-01", 12, amount=10000.0, maturity=10000.0)
    bond_e = add_bond(conn, "Epsilon", "INE000000005E", "2031-02-01", 6, amount=6000.0, maturity=6000.0)
    add_payment(conn, bond_e, "2031-02", 500.0)
    return bond_a, bond_b, bond_c, bond_d, bond_e


def test_tc05_combined_matrix_statuses(db_path):
    with get_conn(db_path) as conn:
        bond_a, bond_b, bond_c, bond_d, bond_e = seed_full_matrix(conn)
        recompute_all(conn, date(2026, 6, 15))
        assert bond_status(conn, bond_a) == "Danger"
        assert bond_status(conn, bond_b) == "Completed"
        assert bond_status(conn, bond_c) == "Danger"
        assert bond_status(conn, bond_d) == "On-going"
        assert bond_status(conn, bond_e) == "On-going"
        recompute_all(conn, date(2031, 5, 15))
        assert bond_status(conn, bond_e) == "Danger"
        assert bond_status(conn, bond_b) == "Completed"


def test_tc05_combined_matrix_totals_and_overview(db_path):
    with get_conn(db_path) as conn:
        bond_a, bond_b, bond_c, bond_d, bond_e = seed_full_matrix(conn)
        recompute_all(conn, date(2026, 6, 15))
        totals_a = bond_month_totals(conn, bond_a)
        assert totals_a["k"] == 11000.0
        assert totals_a["l"] == -109000.0
        portfolio = portfolio_totals(conn)
        assert portfolio["total_investment"] == 199000.0
        assert portfolio["till_return"] == 11000.0 + 6000.0 + 2000.0 + 500.0
        assert portfolio["balance"] == portfolio["till_return"] - 199000.0
        overview = status_overview(conn, date(2026, 6, 15))
        assert len(overview) == 5
        assert [row["status"] for row in overview][:3] == ["Danger", "Danger", "On-going"]
        colors = {"Danger": "red", "On-going": "orange", "Completed": "green"}
        for row in overview:
            assert row["color"] == colors[row["status"]]


def test_tc05_zero_and_missing_rows_never_counted(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Zeta", "INE000000005Z", "2025-01-01", 4, maturity=0.0)
        add_payment(conn, bond_id, "2025-01", 0.0, paid=1)
        add_payment(conn, bond_id, "2025-03", 250.0)
        recompute_all(conn, date(2025, 4, 10))
        assert bond_status(conn, bond_id) == "Danger"
        totals = bond_month_totals(conn, bond_id)
        assert totals["k"] == 250.0
