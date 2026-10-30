from datetime import date

from conftest import add_bond, add_payment, bond_status
from src.db import get_conn
from src.status import compute_row_status, recompute_all


def test_tc03_completed_overrides_unpaid_history(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000003", "2025-01-01", 3)
        add_payment(conn, bond_id, "2024-12", 0.0, paid=0)
        add_payment(conn, bond_id, "2025-01", 1000.0)
        add_payment(conn, bond_id, "2025-02", 1000.0)
        add_payment(conn, bond_id, "2025-03", 1000.0)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "Completed"


def test_tc03_pure_helper_completed_beats_danger():
    months = {"2025-01": True, "2025-02": False, "2025-03": True, "2025-04": True}
    assert compute_row_status(months, 3, date(2025, 4, 10)) == "Completed"


def test_tc03_guard_first_with_extra_paid_month():
    months = {
        "2025-01": False,
        "2025-02": True,
        "2025-03": True,
        "2025-04": True,
        "2025-05": True,
    }
    assert compute_row_status(months, 4, date(2025, 5, 10)) == "Completed"


def test_tc03_completed_stays_completed_on_recompute(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Beta", "INE000000003B", "2025-01-01", 3)
        add_payment(conn, bond_id, "2025-01", 100.0)
        add_payment(conn, bond_id, "2025-02", 100.0)
        add_payment(conn, bond_id, "2025-03", 100.0)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "Completed"
        changed = recompute_all(conn, date(2025, 6, 10))
        assert changed == []
        assert bond_status(conn, bond_id) == "Completed"
