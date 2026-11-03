from datetime import date

from conftest import add_bond, bond_status, pay_range
from src.db import get_conn
from src.queries import save_payment
from src.status import recompute_all


def test_tc15_void_flips_ongoing_to_danger(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha", "INE0000000015", "2025-01-01", 12)
        pay_range(conn, bond_id, "2025-01", 4)
        recompute_all(conn, date(2025, 4, 10))
        assert bond_status(conn, bond_id) == "On-going"
        save_payment(conn, bond_id, "2025-02", 0, 0)
        changed = recompute_all(conn, date(2025, 4, 10))
        assert changed == [
            {"bond_id": bond_id, "company": "Alpha", "from": "On-going", "to": "Danger"}
        ]
        assert bond_status(conn, bond_id) == "Danger"


def test_tc15_zeroed_old_row_also_yields_danger(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Beta", "INE000000015B", "2025-01-01", 12)
        pay_range(conn, bond_id, "2025-01", 5)
        recompute_all(conn, date(2025, 5, 10))
        save_payment(conn, bond_id, "2025-02", 0, 0)
        conn.execute(
            "UPDATE payment_ledger SET amount = 0, paid = 0 "
            "WHERE bond_id = ? AND month = ?",
            (bond_id, "2025-03"),
        )
        recompute_all(conn, date(2025, 5, 10))
        assert bond_status(conn, bond_id) == "Danger"


def test_tc15_full_tenure_reaches_completed_after_earlier_gaps(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Gamma", "INE000000015C", "2025-01-01", 4)
        pay_range(conn, bond_id, "2025-01", 3)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "On-going"
        save_payment(conn, bond_id, "2025-02", 0, 0)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "Danger"
        save_payment(conn, bond_id, "2025-02", 1000.0, 1)
        save_payment(conn, bond_id, "2025-04", 1000.0, 1)
        changed = recompute_all(conn, date(2025, 4, 10))
        assert changed == [
            {"bond_id": bond_id, "company": "Gamma", "from": "Danger", "to": "Completed"}
        ]
        assert bond_status(conn, bond_id) == "Completed"


def test_tc15_recompute_reports_only_changed_bonds(db_path):
    with get_conn(db_path) as conn:
        bond_a = add_bond(conn, "Alpha", "INE000000155A", "2025-01-01", 3)
        pay_range(conn, bond_a, "2025-01", 3)
        bond_b = add_bond(conn, "Beta", "INE000000155B", "2025-01-01", 6)
        pay_range(conn, bond_b, "2025-01", 2, skip={"2025-02"})
        changed = recompute_all(conn, date(2025, 3, 10))
        assert [item["bond_id"] for item in changed] == [bond_a, bond_b]
        assert changed[0]["to"] == "Completed"
        assert changed[1]["to"] == "Danger"
        assert bond_status(conn, bond_a) == "Completed"
        assert bond_status(conn, bond_b) == "Danger"
        again = recompute_all(conn, date(2025, 3, 10))
        assert again == []


def test_tc15_status_is_live_after_each_ledger_change(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Delta", "INE000000155D", "2025-01-01", 6)
        pay_range(conn, bond_id, "2025-01", 2)
        recompute_all(conn, date(2025, 2, 10))
        assert bond_status(conn, bond_id) == "On-going"
        save_payment(conn, bond_id, "2025-03", 1000.0, 1)
        save_payment(conn, bond_id, "2025-01", 0, 0)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "Danger"
        save_payment(conn, bond_id, "2025-01", 1000.0, 1)
        recompute_all(conn, date(2025, 3, 10))
        assert bond_status(conn, bond_id) == "On-going"
