import pytest

from conftest import add_bond, bond_count
from src.db import get_conn
from src.validators import AppError, active_position_lock


def test_tc61_isin_variant_with_different_name_is_blocked(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Muthoottu", "IN1234567890", "2025-01-01", 12, status="On-going")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "MMF Investments", "in1234567890")
        assert exc_info.value.code == "ERR-active-position"
        assert exc_info.value.message == (
            "Cannot add position: Muthoottu has an active position (On-going)"
        )
        assert bond_count(conn) == 1


def test_tc61_isin_match_is_trim_and_case_insensitive(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Muthoottu", "IN1234567890", "2025-01-01", 12, status="On-going")
        for candidate in ("IN1234567890", " in1234567890 ", "In1234567890"):
            with pytest.raises(AppError):
                active_position_lock(conn, "MMF Investments", candidate)


def test_tc61_isin_match_blocks_even_danger_status(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Muthoottu", "IN1234567890", "2025-01-01", 12, status="Danger")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "Someone Else", "IN1234567890")
        assert exc_info.value.message == (
            "Cannot add position: Muthoottu has an active position (Danger)"
        )


def test_tc61_completed_isin_does_not_block(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Muthoottu", "IN1234567890", "2025-01-01", 12, status="Completed")
        assert active_position_lock(conn, "MMF Investments", "in1234567890") is None
