from datetime import date

import pytest

from src.app import create_app
from src.db import get_conn
from src.goals import add_goal, list_goals, months_until, update_goal
from src.validators import AppError


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "tc70.db")
    app.config["TESTING"] = True
    with app.app_context():
        pass
    return app.test_client(), tmp_path / "tc70.db"


def test_add_goal_with_target_amount_and_end_date(client):
    http, db_path = client
    response = http.post(
        "/goals",
        data={
            "name": "10-year wealth plan",
            "target_amount": "1207560",
            "target_end_date": "2036-10-01",
            "saved_amount": "120756",
            "note": "first corpus",
        },
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT name, target_amount, target_end_date, saved_amount FROM financial_goals"
        ).fetchone()
    assert row["name"] == "10-year wealth plan"
    assert row["target_amount"] == 1207560.0
    assert row["target_end_date"] == "2036-10-01"
    assert row["saved_amount"] == 120756.0


def test_ten_year_goal_shows_months_remaining(client):
    http, db_path = client
    http.post(
        "/goals",
        data={
            "name": "10-year wealth plan",
            "target_amount": "1207560",
            "target_end_date": "2036-10-01",
        },
    )
    body = http.get("/goals").data.decode()
    expected = months_until(date(2036, 10, 1), date.today())
    assert months_until(date(2036, 10, 1), date(2026, 11, 1)) == 119
    assert months_until(date(2036, 10, 1), date(2026, 11, 2)) == 118
    assert f'id="months-remaining-1">{expected}<' in body
    assert "10-year wealth plan" in body
    assert "2036-10-01" in body


def test_progress_percent_derived_from_saved_vs_target(client):
    http, db_path = client
    http.post(
        "/goals",
        data={
            "name": "halfway goal",
            "target_amount": "200000",
            "target_end_date": "2030-01-01",
            "saved_amount": "50000",
        },
    )
    body = http.get("/goals").data.decode()
    assert 'id="progress-1">25.0%<' in body


def test_zero_target_progress_guarded(client):
    http, db_path = client
    http.post(
        "/goals",
        data={"name": "zero target", "target_amount": "0", "target_end_date": "2030-01-01"},
    )
    body = http.get("/goals").data.decode()
    assert response_ok(body)
    with get_conn(db_path) as conn:
        goals = list_goals(conn, date.today())
    assert goals[0]["progress_pct"] is None


def response_ok(body):
    return "zero target" in body and "ERR-unexpected" not in body


def test_months_until_full_month_boundary():
    assert months_until(date(2027, 10, 30), date(2026, 10, 30)) == 12
    assert months_until(date(2027, 10, 29), date(2026, 10, 30)) == 11
    assert months_until(date(2026, 10, 30), date(2026, 10, 30)) == 0
    assert months_until(date(2026, 9, 30), date(2026, 10, 30)) == -1


def test_edit_cannot_change_locked_target_amount_or_end_date(client):
    http, db_path = client
    http.post(
        "/goals",
        data={"name": "locked", "target_amount": "1000", "target_end_date": "2030-01-01"},
    )
    response = http.post(
        "/goals/1/edit",
        data={"name": "locked v2", "target_amount": "5000", "target_end_date": "2036-10-01"},
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT name, target_amount, target_end_date FROM financial_goals WHERE id = 1"
        ).fetchone()
    assert row["name"] == "locked v2"
    assert row["target_amount"] == 1000.0
    assert row["target_end_date"] == "2030-01-01"


def test_negative_target_rejected_with_named_error(client):
    http, _ = client
    response = http.post(
        "/goals",
        data={"name": "bad", "target_amount": "-5", "target_end_date": "2030-01-01"},
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data


def test_non_numeric_target_rejected_with_named_error(client):
    http, _ = client
    response = http.post(
        "/goals",
        data={"name": "bad", "target_amount": "abc", "target_end_date": "2030-01-01"},
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data


def test_unparseable_end_date_rejected_with_named_error(client):
    http, _ = client
    response = http.post(
        "/goals",
        data={"name": "bad date", "target_amount": "100", "target_end_date": "not-a-date"},
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data


def test_add_goal_blank_end_date_stores_null(db_path=None):
    from src.db import init_db
    import tempfile
    from pathlib import Path

    path = Path(tempfile.mkdtemp()) / "tc70_unit.db"
    init_db(path)
    with get_conn(path) as conn:
        goal_id = add_goal(conn, "open goal", "100", "", "note", "")
        goals = list_goals(conn, date.today())
    assert goals[0]["id"] == goal_id
    assert goals[0]["target_end_date"] is None
    assert goals[0]["is_legacy"] is True


def test_update_missing_goal_raises_not_found(db_path=None):
    import tempfile
    from pathlib import Path
    from src.db import init_db

    path = Path(tempfile.mkdtemp()) / "tc70_missing.db"
    init_db(path)
    with get_conn(path) as conn:
        with pytest.raises(AppError) as exc_info:
            update_goal(conn, 999, "x", "1", "2030-01-01")
    assert exc_info.value.code == "ERR-goals-op"
    assert "not found" in exc_info.value.message
