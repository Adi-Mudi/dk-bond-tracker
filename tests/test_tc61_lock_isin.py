import pytest

from conftest import add_danger_seed, add_matured_seed, add_ongoing_seed, bond_count
from src.db import get_conn
from src.lock import check_add_allowed
from src.validators import AppError


def test_tc61_isin_variant_with_different_name_is_blocked(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1234567890")
        with pytest.raises(AppError) as exc_info:
            check_add_allowed("MMF Investments", "in1234567890", conn)
        assert exc_info.value.code == "ERR-active-position"
        assert exc_info.value.message == (
            "Cannot add position: Beta Finance Ltd has an active position (On-going)"
        )
        assert bond_count(conn) == 1


def test_tc61_isin_match_is_trim_and_case_insensitive(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1234567890")
        for candidate in ("IN1234567890", " in1234567890 ", "In1234567890"):
            with pytest.raises(AppError):
                check_add_allowed("MMF Investments", candidate, conn)


def test_tc61_isin_match_blocks_even_danger_status(db_path):
    with get_conn(db_path) as conn:
        add_danger_seed(conn, "Beta Finance Ltd", "IN1234567890")
        with pytest.raises(AppError) as exc_info:
            check_add_allowed("Someone Else", "IN1234567890", conn)
        assert exc_info.value.message == (
            "Cannot add position: Beta Finance Ltd has an active position (Danger)"
        )


def test_tc61_completed_isin_does_not_block(db_path):
    with get_conn(db_path) as conn:
        add_matured_seed(conn, "Beta Finance Ltd", "IN1234567890")
        assert check_add_allowed("MMF Investments", "in1234567890", conn)
