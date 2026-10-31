from datetime import date

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.queries import active_bonds_in_month
from src.validators import AppError


def seed_corrupt_bond(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("CorruptCo", "INE0000000861", "CorruptCo", 1000.0, "garbage-date", "2027-12-01", 15, 5, "On-going"),
        )


def test_tc86_corrupt_start_date_raises_named_active_bonds_error(db_path):
    seed_corrupt_bond(db_path)
    with get_conn(db_path) as conn:
        with pytest.raises(AppError) as exc_info:
            active_bonds_in_month(conn, date(2026, 10, 6))
        assert exc_info.value.code == "ERR-active-bonds"
        assert "1" in exc_info.value.message
        assert "garbage-date" in exc_info.value.message


def test_tc86_zero_tenure_raises_named_active_bonds_error(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "ZeroTenure", "INE0000000862", "2026-01-01", 6)
        conn.execute("UPDATE bonds SET tenure_months = 0 WHERE id = ?", (bond_id,))
        with pytest.raises(AppError) as exc_info:
            active_bonds_in_month(conn, date(2026, 10, 6))
        assert exc_info.value.code == "ERR-active-bonds"
        assert str(bond_id) in exc_info.value.message
        assert "tenure_months" in exc_info.value.message


def test_tc86_healthy_bonds_still_listed(db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "HealthyCo", "INE0000000863", "2026-09-01", 12)
        active = active_bonds_in_month(conn, date(2026, 10, 6))
        assert active == [{"id": 1, "company": "HealthyCo"}]


def test_tc86_dashboard_corrupt_bond_keeps_dashboard_at_200(db_path):
    seed_corrupt_bond(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="error-banner"' not in html
