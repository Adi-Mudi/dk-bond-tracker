import re
from datetime import date

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn


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


def header_months(html):
    return re.findall(r'<th class="month-col[^"]*" data-month="(\d{4}-\d{2})"', html)


def schema_snapshot(db_path):
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


def test_tc36_headers_run_continuous_through_simulated_aug2027(db_path, monkeypatch):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2027, 8, 15)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        add_bond(conn, "BorderCo", "INE0000000361", "2025-09-01", 40)
    before = schema_snapshot(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/grid")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    months = header_months(html)
    assert months[0] == "2025-09"
    assert 'data-month="2025-09">Sep-2025<' in html
    assert months == span_keys("2025-09", "2028-12")
    assert months.index("2027-08") == len(span_keys("2025-09", "2027-08")) - 1
    assert 'data-month="2027-08">Aug-2027<' in html
    assert len(months) == len(set(months))
    after = schema_snapshot(db_path)
    assert after == before


def test_tc36_future_columns_render_neutral(db_path, monkeypatch):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2027, 8, 15)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "NeutralCo", "INE0000000362", "2027-06-01", 10, credit_day=5)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/grid").get_data(as_text=True)
    assert 'cell cell-future' in html
    assert 'cell cell-due" data-bond="1"' in html or f'cell cell-due" data-bond="{bond_id}"' in html
    assert f'cell cell-future" data-bond="{bond_id}" data-month="2027-09"' in html
    assert f'cell cell-due" data-bond="{bond_id}" data-month="2027-07"' in html


def test_tc36_grid_table_borders_defined(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    html = app.test_client().get("/grid").get_data(as_text=True)
    assert "grid-table" in html
    assert "border-bottom: 2px solid var(--border)" in html
    assert "border-bottom: 1px solid var(--border)" in html


def test_tc36_schema_unchanged_after_render(db_path, monkeypatch):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2027, 8, 15)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        add_bond(conn, "SchemaCo", "INE0000000363", "2026-01-01", 24)
    before = schema_snapshot(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    client = app.test_client()
    assert client.get("/grid").status_code == 200
    assert client.get("/").status_code == 200
    after = schema_snapshot(db_path)
    assert after == before
    for table, names in after[1].items():
        for name in names:
            assert not re.match(r"^\d{4}-\d{2}$", name), f"{table}.{name}"
