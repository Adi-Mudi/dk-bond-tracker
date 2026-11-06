from datetime import date

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.validators import AppError


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_corrupt_bond(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("CorruptCo", "INE0000000251", "CorruptCo", 1000.0, "garbage-date", "2027-12-01", 15, 5, "On-going"),
        )


def test_tc25_dashboard_query_failure_surfaces_named_error_page(db_path, monkeypatch):
    def broken_summary_counts(conn, today=None):
        raise AppError("ERR-query-counts", "status computation failed: fixture fault")

    monkeypatch.setattr("src.views.dashboard.summary_counts", broken_summary_counts)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/")
    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert 'id="error-banner"' in html
    assert 'id="error-code"' in html
    assert "operation: ERR-query-counts" in html
    assert "fixture fault" in html


def test_tc25_corrupt_bond_data_renders_invalid_chip_on_grid(db_path):
    seed_corrupt_bond(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/grid")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="error-banner"' not in html
    assert "chip-invalid" in html
    assert ">Invalid<" in html


def test_tc25_corrupt_bond_data_keeps_dashboard_at_200(db_path):
    seed_corrupt_bond(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="error-banner"' not in html


def test_tc25_healthy_data_never_renders_error_page(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "HealthyCo", "INE0000000252", "2026-01-01", 12)
    for path in ("/", "/grid", "/watch"):
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'id="error-banner"' not in response.get_data(as_text=True), path
