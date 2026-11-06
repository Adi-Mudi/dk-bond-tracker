import pytest

from conftest import add_bond, bond_count
from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


ADD_LIKE_FORM = {
    "company": "Sneaky Co",
    "isin": "INE9000A0681",
    "amount": "1000",
    "start_date": "2026-11-01",
    "end_date": "2027-11-01",
    "credit_day": "5",
}


def current_bond_count(db_path):
    with get_conn(db_path) as conn:
        return bond_count(conn)


def test_tc68_dashboard_exposes_no_add_control(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "PlainCo", "INE0000000682", "2026-01-01", 12)
    html = client.get("/").get_data(as_text=True)
    assert "/add" not in html
    assert 'href="/add"' not in html
    assert 'action="/add"' not in html


def test_tc68_grid_exposes_no_add_control(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "PlainCo", "INE0000000683", "2026-01-01", 12)
    html = client.get("/grid").get_data(as_text=True)
    assert "/add" not in html
    assert 'href="/add"' not in html
    assert 'action="/add"' not in html
    controls = [part for part in html.split("<a ") if part.startswith("href=")]
    for control in controls:
        assert "/add" not in control.split(">")[0]


def test_tc68_hand_crafted_post_to_dashboard_rejected(client, db_path):
    response = client.post("/", data=ADD_LIKE_FORM)
    assert response.status_code == 403
    html = response.get_data(as_text=True)
    assert "operation: ERR-entry-guard" in html
    assert "Add position is only allowed from the Watch List form" in html
    assert current_bond_count(db_path) == 0


def test_tc68_hand_crafted_post_to_grid_rejected(client, db_path):
    response = client.post("/grid", data=ADD_LIKE_FORM)
    assert response.status_code == 403
    html = response.get_data(as_text=True)
    assert "operation: ERR-entry-guard" in html
    assert current_bond_count(db_path) == 0


def test_tc68_post_to_watch_route_creates_candidate_never_holding(client, db_path):
    form = {
        "company": "Sneaky Co",
        "isin": "INE000000068",
        "rating": "AA",
        "coupon_pct": "8.5",
        "expected_yield_pct": "9.1",
        "source_note": "",
    }
    response = client.post("/watch", data=form)
    assert response.status_code == 302
    assert current_bond_count(db_path) == 1
    with get_conn(db_path) as conn:
        states = [
            row["watch_state"]
            for row in conn.execute("SELECT watch_state FROM bonds").fetchall()
        ]
    assert states == ["watching"]


def test_tc68_only_add_path_is_the_watch_list_form(client, db_path):
    assert client.get("/add").status_code == 404
    assert client.post("/add", data=ADD_LIKE_FORM).status_code == 404
    assert client.post("/portfolio", data=ADD_LIKE_FORM).status_code == 405
    watch = client.get("/watch")
    assert watch.status_code == 200
    html = watch.get_data(as_text=True)
    assert 'id="add-candidate-form"' in html
    assert 'id="add-candidate-submit"' in html
    assert current_bond_count(db_path) == 0


def test_tc68_tc59_new_company_rendered_on_every_surface(client, db_path):
    created = client.post(
        "/watch",
        data={
            "company": "Sneaky Co",
            "isin": ADD_LIKE_FORM["isin"],
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
        },
    )
    assert created.status_code == 302
    with get_conn(db_path) as conn:
        new_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (ADD_LIKE_FORM["isin"],)
        ).fetchone()["id"]
    moved = client.post(
        f"/watch/{new_id}/move",
        data={
            "start_date": "2026-11-01",
            "end_date": "2027-11-01",
            "credit_day": "5",
            "qty": "50",
            "amount": "50000",
            "broker": "HDFC Securities",
        },
    )
    assert moved.status_code == 302
    assert current_bond_count(db_path) == 1
    grid = client.get("/grid").get_data(as_text=True)
    dashboard = client.get("/").get_data(as_text=True)
    watch = client.get("/watch").get_data(as_text=True)
    for page in (grid, dashboard, watch):
        assert "Sneaky Co" in page
