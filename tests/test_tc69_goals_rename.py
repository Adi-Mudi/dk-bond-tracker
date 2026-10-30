import pytest

from src.app import create_app


@pytest.fixture
def client(tmp_path):
    app = create_app(tmp_path / "tc69.db")
    app.config["TESTING"] = True
    return app.test_client()


def test_goals_tab_label_is_financial_goals(client):
    response = client.get("/goals")
    assert response.status_code == 200
    body = response.data.decode()
    assert "Financial Goals" in body
    assert "<h1" in body and "Financial Goals" in body.split("<h1", 1)[1].split(">", 1)[1]


def test_goals_page_has_no_home_plan_string(client):
    response = client.get("/goals")
    body = response.data.decode()
    assert "Home Plan" not in body


def test_nav_tab_is_financial_goals_and_wired_on_every_page(client):
    for path in ("/", "/grid", "/goals", "/watch"):
        body = client.get(path).data.decode()
        assert '<a href="/goals">Financial Goals</a>' in body
        assert "Home Plan" not in body


def test_goals_error_page_keeps_financial_goals_label(client):
    response = client.post("/goals", data={"name": "", "target_amount": "100"})
    assert response.status_code == 400
    body = response.data.decode()
    assert "Financial Goals" in body
    assert "Home Plan" not in body


def test_goals_nav_link_points_to_goals_route(client):
    body = client.get("/").data.decode()
    assert 'href="#">Financial Goals' not in body
