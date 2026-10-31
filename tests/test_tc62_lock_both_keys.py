import pytest

from conftest import add_bond, add_danger_seed, add_matured_seed, add_ongoing_seed, bond_count
from src.db import get_conn
from src.validators import AppError, active_position_lock


def test_tc62_both_keys_matching_single_hard_block(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1234567890")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, " BETA FINANCE LTD ", "in1234567890")
        assert exc_info.value.code == "ERR-active-position"
        assert exc_info.value.message == (
            "Cannot add position: Beta Finance Ltd has an active position (On-going)"
        )
        assert bond_count(conn) == 1


def test_tc62_two_active_positions_name_and_isin_each_block(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1111111111")
        add_danger_seed(conn, "Other Corp", "IN2222222222")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "  BETA FINANCE LTD  ", "in2222222222")
        assert exc_info.value.message == (
            "Cannot add position: Beta Finance Ltd has an active position (On-going)"
        )
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "Third Party", "IN1111111111")
        assert exc_info.value.message == (
            "Cannot add position: Beta Finance Ltd has an active position (On-going)"
        )


def test_tc62_no_match_passes_once(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="On-going")
        assert active_position_lock(conn, "Someone Else", "IN9999999999") is None
        assert bond_count(conn) == 1
