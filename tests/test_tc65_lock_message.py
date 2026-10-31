import pytest

from conftest import add_bond
from src.db import get_conn
from src.validators import AppError, active_position_lock

MESSAGE_SHAPE = "Cannot add position: {company} has an active position ({status})"


def test_tc65_message_shape_exact_ongoing(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="On-going")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, " BETA FINANCE LTD ", "IN9999999999")
        message = exc_info.value.message
        assert message == MESSAGE_SHAPE.format(company="Beta Finance Ltd", status="On-going")
        assert message.startswith("Cannot add position:")
        assert message.endswith(")")


def test_tc65_danger_blocker_named_as_danger(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="Danger")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "MMF Investments", "IN1234567890")
        assert exc_info.value.message == MESSAGE_SHAPE.format(
            company="Beta Finance Ltd", status="Danger"
        )


def test_tc65_error_is_not_swallowed(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="On-going")
        caught = None
        try:
            active_position_lock(conn, "Beta Finance Ltd", "IN1234567890")
        except AppError as exc:
            caught = exc
        assert caught is not None
        assert caught.code == "ERR-active-position"
        assert caught.message == MESSAGE_SHAPE.format(company="Beta Finance Ltd", status="On-going")
        assert "ERR-active-position" in str(caught)


def test_tc65_empty_portfolio_passes(db_path):
    with get_conn(db_path) as conn:
        assert active_position_lock(conn, "Anyone", "IN0000000000") is None


def test_tc65_lock_releases_only_on_completed(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Beta Finance Ltd", "IN1234567890", "2025-01-01", 12, status="Danger")
        with pytest.raises(AppError):
            active_position_lock(conn, "Beta Finance Ltd", "IN1234567890")
        conn.execute(
            "UPDATE bonds SET status = ? WHERE id = ?",
            ("Completed", bond_id),
        )
        assert active_position_lock(conn, "Beta Finance Ltd", "IN1234567890") is None
