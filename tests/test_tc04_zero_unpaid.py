from datetime import date

from conftest import add_bond, add_payment, bond_status
from src.db import get_conn
from src.queries import bond_month_totals, portfolio_totals
from src.status import recompute_all


def test_tc04_zero_amount_counts_unpaid_in_status(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000004", "2025-01-01", 3)
        add_payment(conn, bond_id, "2025-01", 100.0)
        add_payment(conn, bond_id, "2025-02", 0.0, paid=0)
        add_payment(conn, bond_id, "2025-03", 100.0)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "Danger"


def test_tc04_zero_amount_excluded_from_till_return(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000044", "2025-01-01", 3, maturity=300.0)
        add_payment(conn, bond_id, "2025-01", 100.0)
        add_payment(conn, bond_id, "2025-02", 0.0, paid=0)
        add_payment(conn, bond_id, "2025-03", 200.0)
        totals = bond_month_totals(conn, bond_id)
        assert totals["k"] == 300.0
        assert totals["l"] == 0.0
        portfolio = portfolio_totals(conn)
        assert portfolio["till_return"] == 300.0
        assert portfolio["total_investment"] == 100000.0
        assert portfolio["balance"] == 300.0 - 300.0


def test_tc04_zero_flagged_paid_true_also_unpaid(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Beta", "INE0000000045", "2025-01-01", 2, maturity=0.0)
        add_payment(conn, bond_id, "2025-01", 0.0, paid=1)
        add_payment(conn, bond_id, "2025-02", 50.0)
        recompute_all(conn, date(2025, 2, 10))
        assert bond_status(conn, bond_id) == "Danger"
        assert bond_month_totals(conn, bond_id)["k"] == 50.0
