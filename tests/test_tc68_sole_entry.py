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
    "isin": "INE0000000681",
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


def test_tc68_post_to_watch_route_creates_nothing(client, db_path):
    response = client.post("/watch", data=ADD_LIKE_FORM)
    assert response.status_code == 405
    assert current_bond_count(db_path) == 0


def test_tc68_only_add_path_is_the_watch_list_form(client, db_path):
    get_form = client.get("/add")
    assert get_form.status_code == 200
    assert 'id="add-company"' in get_form.get_data(as_text=True)
    response = client.post("/add", data=ADD_LIKE_FORM)
    assert response.status_code == 302
    assert response.headers["Location"] == "/watch"
    follow = client.get(response.headers["Location"])
    assert follow.status_code == 200
    html = follow.get_data(as_text=True)
    assert "Sneaky Co" in html
    assert "Position added: Sneaky Co" in html
    assert current_bond_count(db_path) == 1
    grid = client.get("/grid").get_data(as_text=True)
    assert "Sneaky Co" in grid
    dashboard = client.get("/").get_data(as_text=True)
    assert "Sneaky Co" in dashboard


def test_tc68_tc59_new_company_rendered_on_every_surface(client, db_path):
    response = client.post("/add", data=ADD_LIKE_FORM)
    assert response.status_code == 302
    assert current_bond_count(db_path) == 1
    grid = client.get("/grid").get_data(as_text=True)
    dashboard = client.get("/").get_data(as_text=True)
    watch = client.get("/watch").get_data(as_text=True)
    for page in (grid, dashboard, watch):
        assert "Sneaky Co" in page
