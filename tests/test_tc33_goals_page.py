from datetime import date

import pytest

from src.app import create_app
from src.db import get_conn
from src.goals import add_goal, list_goals
from src.validators import AppError


@pytest.fixture
def client(tmp_path):
    db_path = tmp_path / "tc33.db"
    app = create_app(db_path)
    app.config["TESTING"] = True
    return app.test_client(), db_path


def seed_legacy_goals(db_path):
    with get_conn(db_path) as conn:
        add_goal(conn, "6", "39588", "", "legacy home plan", "")
        add_goal(conn, "8", "10063", "", "legacy home plan", "")
        add_goal(conn, "9", "0", "", "legacy home plan", "")


def test_page_renders_legacy_and_new_goals(client):
    http, db_path = client
    seed_legacy_goals(db_path)
    response = http.post(
        "/goals",
        data={
            "name": "New car fund",
            "target_amount": "300000",
            "target_end_date": "2028-04-01",
            "note": "user created",
        },
    )
    assert response.status_code == 302
    body = http.get("/goals").data.decode()
    assert "6" in body and "39588.00" in body
    assert "8" in body and "10063.00" in body
    assert "9" in body
    assert "New car fund" in body
    assert "300000.00" in body
    assert "2028-04-01" in body
    assert "legacy schedule" in body
    assert body.count('class="legacy-badge"') == 3


def test_zero_amount_legacy_goal_is_preserved(client):
    http, db_path = client
    seed_legacy_goals(db_path)
    with get_conn(db_path) as conn:
        goals = list_goals(conn, date.today())
    zero_goals = [goal for goal in goals if float(goal["target_amount"]) == 0.0]
    assert len(zero_goals) == 1
    body = http.get("/goals").data.decode()
    assert "ERR-unexpected" not in body


def test_add_goal_blank_name_is_named_error(client):
    http, _ = client
    response = http.post(
        "/goals", data={"name": "   ", "target_amount": "10", "target_end_date": ""}
    )
    assert response.status_code == 400
    body = response.data.decode()
    assert "ERR-goals-op" in body
    assert "name is required" in body


def test_add_goal_bad_amount_is_named_error(client):
    http, _ = client
    response = http.post(
        "/goals", data={"name": "x", "target_amount": "ten", "target_end_date": ""}
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data


def test_add_goal_bad_date_is_named_error(client):
    http, _ = client
    response = http.post(
        "/goals", data={"name": "x", "target_amount": "10", "target_end_date": "31-12-2099"}
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data
    assert b"target_end_date must be a date" in response.data


def test_edit_missing_goal_is_named_not_found(client):
    http, _ = client
    response = http.post(
        "/goals/424242/edit",
        data={"name": "ghost", "target_amount": "10", "target_end_date": ""},
    )
    assert response.status_code == 400
    body = response.data.decode()
    assert "ERR-goals-op" in body
    assert "goal not found" in body


def test_delete_missing_goal_is_named_not_found(client):
    http, _ = client
    response = http.post("/goals/424242/delete")
    assert response.status_code == 400
    body = response.data.decode()
    assert "ERR-goals-op" in body
    assert "goal not found" in body


def test_delete_removes_single_goal(client):
    http, db_path = client
    seed_legacy_goals(db_path)
    response = http.post("/goals/1/delete")
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM financial_goals").fetchone()["n"]
        remaining = {
            row["target_amount"]
            for row in conn.execute("SELECT target_amount FROM financial_goals").fetchall()
        }
    assert count == 2
    assert 39588.0 not in remaining
    assert 10063.0 in remaining and 0.0 in remaining


def test_edit_missing_goal_raises_in_layer(db_path=None):
    import tempfile
    from pathlib import Path
    from src.db import init_db

    path = Path(tempfile.mkdtemp()) / "tc33_unit.db"
    init_db(path)
    with get_conn(path) as conn:
        with pytest.raises(AppError) as exc_info:
            from src.goals import update_goal

            update_goal(conn, 777, "x", "1", "")
    assert exc_info.value.code == "ERR-goals-op"
