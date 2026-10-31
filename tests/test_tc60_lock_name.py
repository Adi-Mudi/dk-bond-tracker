import pytest

from conftest import add_bond, bond_count
from src.db import get_conn
from src.validators import AppError, active_position_lock


def test_tc60_name_variant_with_different_isin_is_blocked(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="On-going")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "  MUTHOOTTU  ", "IN9999999999")
        assert exc_info.value.code == "ERR-active-position"
        assert exc_info.value.message == (
            "Cannot add position: Beta Finance Ltd has an active position (On-going)"
        )
        assert bond_count(conn) == 1


def test_tc60_name_match_is_trim_and_case_insensitive(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="Danger")
        for candidate in ("muthoottu", "MUTHOOTTU", " MuThOoTtU "):
            with pytest.raises(AppError) as exc_info:
                active_position_lock(conn, candidate, "IN9999999999")
            assert exc_info.value.message == (
                "Cannot add position: Beta Finance Ltd has an active position (Danger)"
            )


def test_tc60_completed_position_does_not_block_name(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="Completed")
        assert active_position_lock(conn, "  MUTHOOTTU  ", "IN9999999999") is None
