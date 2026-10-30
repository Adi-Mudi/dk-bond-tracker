from datetime import date

from conftest import add_bond, pay_range
from src.db import get_conn
from src.queries import insert_payment, status_overview
from src.status import recompute_all


def seed_overview_bonds(conn):
    bond_danger = add_bond(conn, "Zeta", "INE0000000021D", "2025-01-01", 12, status="On-going")
    pay_range(conn, bond_danger, "2025-01", 4, skip={"2025-02"})
    bond_ongoing = add_bond(conn, "Alpha", "INE0000000021O", "2025-03-01", 12, status="On-going")
    pay_range(conn, bond_ongoing, "2025-03", 1)
    bond_completed = add_bond(conn, "Mid", "INE0000000021C", "2025-01-01", 3, status="On-going")
    pay_range(conn, bond_completed, "2025-01", 3)
    return bond_danger, bond_ongoing, bond_completed


def test_tc21_overview_orders_danger_ongoing_completed(db_path):
    with get_conn(db_path) as conn:
        seed_overview_bonds(conn)
        overview = status_overview(conn, date(2025, 4, 3))
        assert [row["status"] for row in overview] == ["Danger", "On-going", "Completed"]


def test_tc21_overview_colors_red_orange_green(db_path):
    with get_conn(db_path) as conn:
        seed_overview_bonds(conn)
        overview = status_overview(conn, date(2025, 4, 3))
        assert [row["color"] for row in overview] == ["red", "orange", "green"]


def test_tc21_overview_includes_every_bond(db_path):
    with get_conn(db_path) as conn:
        seed_overview_bonds(conn)
        add_bond(conn, "Future", "INE0000000021F", "2031-02-01", 60)
        overview = status_overview(conn, date(2025, 4, 3))
        assert len(overview) == 4
        isins = {row["isin"] for row in overview}
        assert "INE0000000021F" in isins


def test_tc21_overview_uses_live_status_not_stored_column(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Stale", "INE0000000021S", "2025-01-01", 6, status="On-going")
        pay_range(conn, bond_id, "2025-01", 1, skip={"2025-01"})
        overview = status_overview(conn, date(2025, 3, 10))
        assert overview[0]["status"] == "Danger"
        stored = conn.execute("SELECT status FROM bonds WHERE id = ?", (bond_id,)).fetchone()[0]
        assert stored == "On-going"


def test_tc21_secondary_order_is_company_name(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "nBeta", "INE0000000211", "2025-01-01", 12)
        add_bond(conn, "nAlpha", "INE0000000212", "2025-01-01", 12)
        overview = status_overview(conn, date(2025, 1, 10))
        assert [row["company"] for row in overview] == ["nAlpha", "nBeta"]


def test_tc21_recompute_then_overview_consistent(db_path):
    with get_conn(db_path) as conn:
        bond_danger, _, bond_completed = seed_overview_bonds(conn)
        changed = recompute_all(conn, date(2025, 4, 3))
        assert [item["bond_id"] for item in changed] == [bond_danger, bond_completed]
        overview = status_overview(conn, date(2025, 4, 3))
        assert overview[0]["status"] == "Danger"
        assert overview[0]["id"] == bond_danger


def test_tc21_payment_insert_keeps_ledger_schema_and_single_row(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "LedgerClaim", "INE0000000021L", "2025-01-01", 6)
        columns_before = [row[1] for row in conn.execute("PRAGMA table_info(payment_ledger)")]
        count_before = conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"]
        insert_payment(conn, bond_id, "2025-01", 1000.0)
        columns_after = [row[1] for row in conn.execute("PRAGMA table_info(payment_ledger)")]
        count_after = conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"]
        assert columns_after == columns_before
        assert count_after - count_before == 1
        row = conn.execute(
            "SELECT amount, paid FROM payment_ledger WHERE bond_id = ? AND month = ?",
            (bond_id, "2025-01"),
        ).fetchone()
        assert row is not None
        assert float(row["amount"]) == 1000.0
        assert int(row["paid"]) == 1
