from datetime import date

from conftest import add_bond, add_payment, bond_status, month_sequence, pay_range
from src.db import get_conn
from src.status import recompute_all


def test_tc01_five_bond_status_matrix(db_path):
    with get_conn(db_path) as conn:
        bond_a = add_bond(conn, "Alpha", "INE000000000A", "2025-01-01", 12)
        pay_range(conn, bond_a, "2025-01", 12, skip={"2025-03"})
        bond_b = add_bond(conn, "Beta", "INE000000000B", "2025-01-01", 6)
        pay_range(conn, bond_b, "2025-01", 6)
        bond_c = add_bond(conn, "Gamma", "INE000000000C", "2025-01-01", 6)
        for month in month_sequence("2025-01", 6):
            if month == "2025-03":
                add_payment(conn, bond_c, month, 0.0, paid=0)
            else:
                add_payment(conn, bond_c, month, 500.0)
        bond_d = add_bond(conn, "Delta", "INE000000000D", "2026-07-01", 12)
        bond_e = add_bond(conn, "Epsilon", "INE000000000E", "2031-02-01", 12)
        add_payment(conn, bond_e, "2031-02", 700.0)
        recompute_all(conn, date(2026, 6, 15))
        statuses = {
            row["id"]: row["status"] for row in conn.execute("SELECT id, status FROM bonds")
        }
        assert len(statuses) == 5
        assert statuses[bond_a] == "Danger"
        assert statuses[bond_b] == "Completed"
        assert statuses[bond_c] == "Danger"
        assert statuses[bond_d] == "On-going"
        assert statuses[bond_e] == "On-going"
        recompute_all(conn, date(2031, 5, 15))
        assert bond_status(conn, bond_e) == "Danger"
        assert bond_status(conn, bond_b) == "Completed"
        assert bond_status(conn, bond_c) == "Danger"


def test_tc01_zero_amount_row_is_unpaid_in_matrix(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Gamma", "INE000000000G", "2025-01-01", 3)
        add_payment(conn, bond_id, "2025-01", 100.0)
        add_payment(conn, bond_id, "2025-02", 0.0, paid=0)
        add_payment(conn, bond_id, "2025-03", 100.0)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "Danger"
