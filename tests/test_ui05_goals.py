import json
from datetime import date

import pytest

from conftest import add_bond, add_payment
from src.app import create_app
from src.db import get_conn
from src.goals import list_goals


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def create_goal(client, name="House down-payment", monthly="50000", saved="0"):
    return client.post(
        "/goals",
        data={
            "name": name,
            "monthly_amount": monthly,
            "start_date": "2026-01-01",
            "target_end_date": "2026-12-01",
            "saved_amount": saved,
        },
        follow_redirects=False,
    )


def goal_row(db_path, goal_id=1):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT * FROM financial_goals WHERE id = ?", (goal_id,)
        ).fetchone()


def link_bond(db_path, goal_id, amount=50000.0, paid_month="2026-01", paid_amount=2000.0):
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "Linked Co", "INE5000A1001", "2026-01-01", 12, amount=amount, credit_day=5
        )
        conn.execute("UPDATE bonds SET goal_id = ? WHERE id = ?", (goal_id, bond_id))
        if paid_amount:
            add_payment(conn, bond_id, paid_month, paid_amount)
    return bond_id


def goals_columns(db_path):
    with get_conn(db_path) as conn:
        return {row[1] for row in conn.execute("PRAGMA table_info(financial_goals)")}


def test_ui05_target_auto_calculated_and_locked_after_create(client, db_path):
    response = create_goal(client)
    assert response.status_code == 302
    row = goal_row(db_path)
    assert row["monthly_amount"] == 50000.0
    assert row["start_date"] == "2026-01-01"
    assert row["target_amount"] == 600000.0

    html = client.get("/goals").get_data(as_text=True)
    assert 'id="locked-1"' in html
    assert "600000.00" in html
    assert 'id="goal-create-toggle"' in html
    assert 'id="add-goal-form" hidden' in html
    assert 'id="goal-target-preview"' in html
    assert 'id="edit-goal-1"' not in html
    assert 'id="delete-goal-1"' not in html
    assert 'action="/goals/1/edit"' not in html
    assert 'action="/goals/1/delete"' not in html


def test_ui05_monthly_plan_requires_both_dates(client, db_path):
    response = client.post(
        "/goals",
        data={"name": "No dates", "monthly_amount": "1000", "target_end_date": ""},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data
    assert b"start date and end date are required" in response.data


def test_ui05_checkin_records_intent_log(client, db_path):
    create_goal(client)
    response = client.post(
        "/goals/1/checkin", data={"month": "2026-01", "invested": "on"}, follow_redirects=False
    )
    assert response.status_code == 302
    assert json.loads(goal_row(db_path)["checkins"]) == ["2026-01"]
    html = client.get("/goals").get_data(as_text=True)
    assert "checkin-month on" in html
    assert 'id="checkin-1-2026-01"' in html
    assert "INTENT LOG (not the progress authority)" in html


def test_ui05_checkin_toggles_off(client, db_path):
    create_goal(client)
    client.post("/goals/1/checkin", data={"month": "2026-02", "invested": "on"})
    client.post("/goals/1/checkin", data={"month": "2026-02", "invested": ""})
    assert json.loads(goal_row(db_path)["checkins"]) == []


def test_ui05_checkin_rejects_bad_month(client, db_path):
    create_goal(client)
    response = client.post(
        "/goals/1/checkin", data={"month": "2026-13", "invested": "on"}, follow_redirects=False
    )
    assert response.status_code == 400
    assert b"ERR-goals-op" in response.data


def test_ui05_consolidated_header_sums_across_goals(client, db_path):
    create_goal(client, name="House", monthly="10000", saved="5000")
    create_goal(client, name="Gold", monthly="20000", saved="0")
    link_bond(db_path, 1, amount=50000.0, paid_amount=2000.0)
    html = client.get("/goals").get_data(as_text=True)
    assert 'id="consolidated-monthly" data-amount="30000.00"' in html
    assert 'id="consolidated-saved" data-amount="5000.00"' in html
    assert 'id="consolidated-invested" data-amount="50000.00"' in html
    assert 'id="consolidated-returns" data-amount="2000.00"' in html


def test_ui05_derived_invested_and_returns_from_linked_bonds(client, db_path):
    create_goal(client)
    link_bond(db_path, 1, amount=75000.0, paid_amount=4000.0)
    html = client.get("/goals").get_data(as_text=True)
    assert 'id="goal-invested-value-1" data-amount="75000.00"' in html
    assert 'id="goal-returns-value-1" data-amount="4000.00"' in html
    assert 'id="goal-bonds-1"' in html
    assert "Linked Co" in html
    assert 'id="goal-saved-value-1" data-amount="0.00"' in html

    with get_conn(db_path) as conn:
        goal = list_goals(conn, date.today())[0]
    assert goal["invested_via_bonds"] == 75000.0
    assert goal["returns_received"] == 4000.0
    assert goal["linked_count"] == 1
    assert goal["progress_pct"] == round(79000.0 / 600000.0 * 100.0, 1)

    columns = goals_columns(db_path)
    assert "invested_via_bonds" not in columns
    assert "returns_received" not in columns
    assert "progress_pct" not in columns


def test_ui05_progress_uses_derived_authority_not_checkins(client, db_path):
    create_goal(client, saved="0")
    client.post("/goals/1/checkin", data={"month": "2026-01", "invested": "on"})
    with get_conn(db_path) as conn:
        goal = list_goals(conn, date.today())[0]
    assert goal["checkin_count"] == 1
    assert goal["progress_pct"] == 0.0


def test_ui05_portfolio_goal_tab_is_read_only(client, db_path):
    create_goal(client, name="House down-payment")
    bond_id = link_bond(db_path, 1, amount=50000.0, paid_amount=0.0)
    detail = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert detail["goal_id"] == 1
    assert detail["goal_name"] == "House down-payment"

    html = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert 'id="detail-goal-note">House down-payment' in html
    assert 'id="detail-goal-badge"' in html
    assert "permanent" in html
    assert 'action="/goals' not in html
    assert "/unlink" not in html.lower()
    assert 'id="goal-set' not in html
    assert 'id="goal-change' not in html
    assert 'id="goal-remove' not in html


def test_ui05_goals_page_has_no_unlink_or_edit_controls(client, db_path):
    create_goal(client)
    link_bond(db_path, 1, amount=50000.0, paid_amount=0.0)
    html = client.get("/goals").get_data(as_text=True)
    assert "/unlink" not in html.lower()
    assert 'action="/goals/1/unlink' not in html
    assert 'action="/goals/1/edit"' not in html
    assert 'action="/goals/1/delete"' not in html
    assert 'action="/goals/1/checkin"' in html
    assert "no edit control afterwards" in html
    assert "permanent" in html


def test_ui05_portfolio_detail_page_goal_tab_read_only_when_unlinked(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(
            conn, "Plain Co", "INE5000A1002", "2026-01-01", 12, amount=1000.0, credit_day=5
        )
    html = client.get(f"/portfolio/{bond_id}").get_data(as_text=True)
    assert "No goal linked to this bond" in html
    assert "Move-to-Portfolio" in html
    assert 'action="/goals' not in html
    detail = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert detail["goal_id"] is None
    assert detail["goal_name"] is None


MOVE_PAYLOAD = {
    "purchase_date": "2026-08-01",
    "start_date": "2026-08-01",
    "end_date": "2028-08-01",
    "credit_day": "5",
    "qty": "100",
    "amount": "100000",
    "broker": "Zerodha",
}


def make_candidate(client, db_path, isin="INE5000A2001"):
    client.post(
        "/watch",
        data={
            "company": "Move Co",
            "isin": isin,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
            "broker": "Zerodha",
        },
        follow_redirects=False,
    )
    with get_conn(db_path) as conn:
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin,)).fetchone()["id"]


def moved_row(db_path, candidate):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT watch_state, goal_id FROM bonds WHERE id = ?", (candidate,)
        ).fetchone()


def test_ui05_move_form_goal_picker_hidden_without_goals(client, db_path):
    make_candidate(client, db_path)
    html = client.get("/watch").get_data(as_text=True)
    assert 'data-mtab="goal"' not in html
    assert 'name="goal_id"' not in html


def test_ui05_move_form_goal_picker_present_with_goals(client, db_path):
    create_goal(client, name="House down-payment")
    make_candidate(client, db_path)
    html = client.get("/watch").get_data(as_text=True)
    assert 'data-mtab="goal"' in html
    assert 'name="goal_id"' in html
    assert "House down-payment" in html
    assert "the link is permanent" in html


def test_ui05_move_writes_goal_link(client, db_path):
    create_goal(client, name="House down-payment")
    candidate = make_candidate(client, db_path)
    response = client.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id="1"),
        follow_redirects=False,
    )
    assert response.status_code == 302
    row = moved_row(db_path, candidate)
    assert row["watch_state"] == "holding"
    assert row["goal_id"] == 1
    html = client.get("/goals").get_data(as_text=True)
    assert 'id="goal-bonds-1"' in html
    assert 'id="goal-invested-value-1" data-amount="100000.00"' in html


def test_ui05_move_with_blank_goal_leaves_link_null(client, db_path):
    create_goal(client, name="House down-payment")
    candidate = make_candidate(client, db_path)
    response = client.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id=""),
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert moved_row(db_path, candidate)["goal_id"] is None


def test_ui05_move_with_absent_goal_field_leaves_link_null(client, db_path):
    create_goal(client, name="House down-payment")
    candidate = make_candidate(client, db_path)
    response = client.post(
        f"/watch/{candidate}/move", data=MOVE_PAYLOAD, follow_redirects=False
    )
    assert response.status_code == 302
    assert moved_row(db_path, candidate)["goal_id"] is None


def test_ui05_move_with_unknown_goal_is_named_error_not_500(client, db_path):
    create_goal(client, name="House down-payment")
    candidate = make_candidate(client, db_path)
    response = client.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id="9999"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"ERR-move-watching" in response.data
    assert b"financial goal not found" in response.data
    row = moved_row(db_path, candidate)
    assert row["watch_state"] == "watching"
    assert row["goal_id"] is None


def test_ui05_checkin_negative_state_renders_red_cross(client, db_path):
    create_goal(client)
    html = client.get("/goals").get_data(as_text=True)
    assert "checkin-month off" in html
    assert 'class="checkin-mark">&#10007;</span>' in html
    assert "&#8226;" not in html
    assert ".checkin-month.off .checkin-mark" in html
    assert "var(--danger-fg)" in html


def test_ui05_checkin_invested_state_renders_green_tick(client, db_path):
    create_goal(client)
    client.post("/goals/1/checkin", data={"month": "2026-01", "invested": "on"})
    html = client.get("/goals").get_data(as_text=True)
    assert "checkin-month on" in html
    assert "&#10003;" in html
