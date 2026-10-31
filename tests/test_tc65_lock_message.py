from datetime import date, timedelta

import pytest

from conftest import add_bond, add_danger_seed, add_payment, add_ongoing_seed
from src.db import get_conn
from src.status import month_key
from src.validators import AppError, active_position_lock, add_months

MESSAGE_SHAPE = "Cannot add position: {company} has an active position ({status})"


def test_tc65_message_shape_exact_ongoing(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1234567890")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, " BETA FINANCE LTD ", "IN9999999999")
        message = exc_info.value.message
        assert message == MESSAGE_SHAPE.format(company="Beta Finance Ltd", status="On-going")
        assert message.startswith("Cannot add position:")
        assert message.endswith(")")


def test_tc65_danger_blocker_named_as_danger(db_path):
    with get_conn(db_path) as conn:
        add_danger_seed(conn, "Beta Finance Ltd", "IN1234567890")
        with pytest.raises(AppError) as exc_info:
            active_position_lock(conn, "MMF Investments", "IN1234567890")
        assert exc_info.value.message == MESSAGE_SHAPE.format(
            company="Beta Finance Ltd", status="Danger"
        )


def test_tc65_error_is_not_swallowed(db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1234567890")
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
        start = date.today() - timedelta(days=40)
        bond_id = add_bond(
            conn, "Beta Finance Ltd", "IN1234567890", start.isoformat(), 2, credit_day=1, status="Danger"
        )
        with pytest.raises(AppError):
            active_position_lock(conn, "Beta Finance Ltd", "IN1234567890")
        for offset in range(2):
            add_payment(conn, bond_id, month_key(add_months(start, offset)), 1000.0)
        assert active_position_lock(conn, "Beta Finance Ltd", "IN1234567890") is None
