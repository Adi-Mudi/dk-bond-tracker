import pytest

from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), db_path


MOVE_PAYLOAD = {
    "purchase_date": "2026-08-01",
    "start_date": "2026-08-01",
    "end_date": "2028-08-01",
    "credit_day": "5",
    "qty": "100",
    "amount": "100000",
    "broker": "Zerodha",
}


def create_goal(http, name):
    return http.post(
        "/goals",
        data={
            "name": name,
            "monthly_amount": "50000",
            "start_date": "2026-01-01",
            "target_end_date": "2026-12-01",
            "saved_amount": "0",
        },
        follow_redirects=False,
    )


def make_candidate(http, db_path, isin="INE5000A2001", company="Goal Visible Co"):
    http.post(
        "/watch",
        data={
            "company": company,
            "isin": isin,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
        follow_redirects=False,
    )
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (isin,)
        ).fetchone()["id"]


def moved_row(db_path, candidate):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT watch_state, goal_id FROM bonds WHERE id = ?", (candidate,)
        ).fetchone()


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_299_a_empty_db_goal_select_renders_with_none_option(client, db_path):
    http, db = client
    make_candidate(http, db)
    html = http.get("/watch").get_data(as_text=True)
    assert 'name="goal_id"' in html
    assert 'id="move-goal-1"' in html
    assert "&#8212; none &#8212;" in html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_299_b_with_goals_select_lists_names_in_order_none_first(client, db_path):
    http, db = client
    create_goal(http, "Education fund")
    create_goal(http, "Retirement corpus")
    make_candidate(http, db)
    html = http.get("/watch").get_data(as_text=True)
    assert 'name="goal_id"' in html
    none_at = html.index("&#8212; none &#8212;")
    first_at = html.index("Education fund")
    second_at = html.index("Retirement corpus")
    assert none_at < first_at < second_at


def test_299_c_empty_db_save_with_none_stores_goal_null(client, db_path):
    http, db = client
    candidate = make_candidate(http, db)
    response = http.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id=""),
        follow_redirects=False,
    )
    assert response.status_code == 302
    row = moved_row(db, candidate)
    assert row["watch_state"] == "holding"
    assert row["goal_id"] is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_299_d_save_with_valid_goal_persists_and_invalid_goal_errors(client, db_path):
    http, db = client
    create_goal(http, "Education fund")
    candidate = make_candidate(http, db)
    response = http.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id="1"),
        follow_redirects=False,
    )
    assert response.status_code == 302
    assert moved_row(db, candidate)["goal_id"] == 1
    other = make_candidate(http, db, isin="INE5000A2002", company="Second Visible Co")
    response = http.post(
        f"/watch/{other}/move",
        data=dict(MOVE_PAYLOAD, goal_id="9999"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"ERR-move-watching" in response.data
    assert b"financial goal not found" in response.data
    assert moved_row(db, other)["goal_id"] is None


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_299_e_empty_state_caption_and_create_goal_hint_link(client, db_path):
    http, db = client
    make_candidate(http, db)
    html = http.get("/watch").get_data(as_text=True)
    assert "optional; the link is permanent once saved" in html
    assert "create a goal first" in html
    assert 'href="/goals"' in html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_299_state_matrix_goals_added_later_appear_on_second_render(client, db_path):
    http, db = client
    make_candidate(http, db)
    empty_html = http.get("/watch").get_data(as_text=True)
    assert 'name="goal_id"' in empty_html
    assert "Education fund" not in empty_html
    create_goal(http, "Education fund")
    later_html = http.get("/watch").get_data(as_text=True)
    assert 'name="goal_id"' in later_html
    assert "Education fund" in later_html
    assert "&#8212; none &#8212;" in later_html


@pytest.mark.skip(reason="Retired per issue #337: old frontend removal")
def test_299_state_matrix_goal_link_permanent_once_saved(client, db_path):
    http, db = client
    create_goal(http, "Education fund")
    candidate = make_candidate(http, db)
    response = http.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id="1"),
        follow_redirects=False,
    )
    assert response.status_code == 302
    response = http.post(
        f"/watch/{candidate}/move",
        data=dict(MOVE_PAYLOAD, goal_id=""),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"already in Portfolio" in response.data
    assert moved_row(db, candidate)["goal_id"] == 1
