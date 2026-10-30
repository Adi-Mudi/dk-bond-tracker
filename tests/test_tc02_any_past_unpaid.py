from datetime import date

from conftest import add_bond, bond_status, pay_range
from src.db import get_conn
from src.status import compute_row_status, recompute_all


def test_tc02_old_miss_with_paid_previous_month_is_danger(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000002", "2025-09-01", 12)
        pay_range(conn, bond_id, "2025-09", 12, skip={"2025-11"})
        recompute_all(conn, date(2026, 3, 15))
        assert bond_status(conn, bond_id) == "Danger"


def test_tc02_pure_helper_any_past_unpaid_is_danger():
    months = {month: month != "2025-11" for month in
              ["2025-09", "2025-10", "2025-11", "2025-12", "2026-01", "2026-02"]}
    assert compute_row_status(months, 12, date(2026, 3, 15)) == "Danger"


def test_tc02_previous_month_paid_does_not_mask_old_miss():
    months = {
        "2025-09": True,
        "2025-10": True,
        "2025-11": False,
        "2025-12": True,
        "2026-01": True,
        "2026-02": True,
    }
    assert compute_row_status(months, 12, date(2026, 3, 15)) == "Danger"
