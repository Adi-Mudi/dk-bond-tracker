from datetime import date, timedelta

import pytest

from conftest import add_bond, add_payment
from src.db import get_conn
from src.lock import check_add_allowed
from src.validators import AppError, add_months

_TODAY = date.today()
_START = _TODAY - timedelta(days=40)
_COMPLETED_ISIN = "INE0000000641"
_REBUY_ISIN = "INE0000000642"


def pay_through(conn, bond_id, start, months):
    for offset in range(months):
        month = add_months(start, offset)
        add_payment(conn, bond_id, f"{month.year:04d}-{month.month:02d}", 1000.0)


def test_tc64_completed_company_can_be_rebought_then_relocks(db_path):
    with get_conn(db_path) as conn:
        first_id = add_bond(conn, "RebuyCo", _COMPLETED_ISIN, _START, 3)
        pay_through(conn, first_id, _START, 3)
        assert check_add_allowed("RebuyCo", _COMPLETED_ISIN, conn) is True
        second_id = add_bond(conn, "RebuyCo", _REBUY_ISIN, _TODAY - timedelta(days=5), 12)
        with pytest.raises(AppError) as excinfo:
            check_add_allowed("RebuyCo", _REBUY_ISIN, conn)
        assert excinfo.value.code == "ERR-active-position"
        assert "active position" in excinfo.value.message
        ids = [
            row["id"]
            for row in conn.execute(
                "SELECT id FROM bonds WHERE company = ? ORDER BY id", ("RebuyCo",)
            ).fetchall()
        ]
        assert ids == [first_id, second_id]
