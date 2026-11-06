import re
from datetime import date

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.queries import grid_month_columns


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def span_keys(start_key, end_key):
    year, mon = map(int, start_key.split("-"))
    end_year, end_mon = map(int, end_key.split("-"))
    total = (end_year - year) * 12 + (end_mon - mon)
    return [
        f"{year + (mon - 1 + offset) // 12:04d}-{(mon - 1 + offset) % 12 + 1:02d}"
        for offset in range(total + 1)
    ]


def table_snapshot(db_path):
    with get_conn(db_path) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        ]
        columns = {
            table: [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
            for table in tables
        }
    return tables, columns


def header_months(html):
    return re.findall(r'<th class="month-col[^"]*" data-month="(\d{4}-\d{2})"', html)


def test_tc14_window_derives_continuous_columns_through_simulated_current():
    columns = grid_month_columns(["2025-09"], ["2026-12"], "2027-08")
    assert columns == span_keys("2025-09", "2027-08")
    assert columns[0] == "2025-09"
    assert columns[-1] == "2027-08"
    assert "2027-02" in columns
    assert "2026-12" in columns


def test_tc14_window_without_data_returns_no_columns():
    assert grid_month_columns([], [], "2026-10") == []


def test_tc14_window_ends_at_data_max_end_when_current_is_earlier():
    columns = grid_month_columns(["2025-09"], ["2032-07"], "2026-10")
    assert columns[-1] == "2032-07"
    assert "2026-10" in columns
    assert columns == span_keys("2025-09", "2032-07")


def test_tc14_route_headers_extend_to_simulated_current_and_schema_unchanged(
    db_path, monkeypatch
):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2027, 8, 15)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        add_bond(conn, "WindowCo", "INE0000000141", "2025-09-01", 15)
    before_tables, before_columns = table_snapshot(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/grid")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    months = header_months(html)
    assert months == span_keys("2025-09", "2027-08")
    assert 'data-month="2027-08">Aug-2027<' in html
    assert 'data-month="2027-02">Feb-2027<' in html
    after_tables, after_columns = table_snapshot(db_path)
    assert after_tables == before_tables
    assert after_columns == before_columns


def test_tc14_schema_has_no_per_month_columns(db_path):
    _, columns = table_snapshot(db_path)
    for table, names in columns.items():
        for name in names:
            assert not re.match(r"^\d{4}-\d{2}$", name), f"{table}.{name}"
            assert name[:3].lower() not in (
                "jan",
                "feb",
                "mar",
                "apr",
                "may",
                "jun",
                "jul",
                "aug",
                "sep",
                "oct",
                "nov",
                "dec",
            ), f"{table}.{name}"
