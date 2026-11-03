from conftest import add_bond
from src.db import get_conn
from src.ledger import ledger_by_bond, paid_map
from src.validators import safe_float


def test_tc145_safe_float_defaults():
    assert safe_float(None) == 0.0
    assert safe_float("not-a-number") == 0.0
    assert safe_float("2.50") == 2.5
    assert safe_float(-5) == -5.0
    assert safe_float(None, default=7.0) == 7.0


def test_tc145_paid_requires_a_positive_amount(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Ledger Co", "INE0000001451", "2026-01-01", 4, credit_day=5)
        for month, amount, paid in (
            ("2026-01", 100.0, 1),
            ("2026-02", 0.0, 1),
            ("2026-03", None, 1),
            ("2026-04", -5.0, 1),
        ):
            conn.execute(
                "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
                (bond_id, month, amount, paid),
            )
        months = ledger_by_bond(conn, [bond_id])[bond_id]
        assert months["2026-01"]["paid"] is True
        assert months["2026-02"]["paid"] is False
        assert months["2026-03"]["paid"] is False
        assert months["2026-04"]["paid"] is False
        assert paid_map(conn, bond_id, ["2026-01", "2026-02", "2026-05"]) == {
            "2026-01": True,
            "2026-02": False,
            "2026-05": False,
        }


def test_tc145_ledger_by_bond_filters_ids(db_path):
    with get_conn(db_path) as conn:
        first = add_bond(conn, "First Co", "INE0000001452", "2026-01-01", 4, credit_day=5)
        second = add_bond(conn, "Second Co", "INE0000001453", "2026-01-01", 4, credit_day=5)
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, '2026-01', 10, 1)",
            (first,),
        )
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, '2026-01', 20, 1)",
            (second,),
        )
        months = ledger_by_bond(conn, [second])
    assert list(months) == [second]
    assert months[second]["2026-01"]["amount"] == 20.0
