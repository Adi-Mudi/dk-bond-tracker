import re
from datetime import date
from pathlib import Path

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn
from src.queries import grid_month_columns

SRC = Path(__file__).resolve().parents[1] / "src"


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


@pytest.mark.parametrize(
    "current_key",
    ["2027-02", "2027-08"],
)
def test_tc18_window_derivation_reaches_beyond_old_hardcoded_edge(current_key):
    columns = grid_month_columns(["2025-09"], ["2026-12"], current_key)
    assert columns == span_keys("2025-09", current_key)
    assert columns[-1] == current_key
    assert "2027-02" in columns


def test_tc18_bond_starting_feb2031_renders_full_row(db_path, monkeypatch):
    class SimDate(date):
        @classmethod
        def today(cls):
            return date(2031, 3, 10)

    monkeypatch.setattr("src.views.dashboard.date", SimDate)
    with get_conn(db_path) as conn:
        add_bond(conn, "FarCo", "INE0000000181", "2031-02-01", 6)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/grid")
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    months = header_months(html)
    assert months == span_keys("2031-02", "2031-07")
    assert 'data-month="2031-02">Feb-2031<' in html
    row_cells = re.findall(r'<td class="cell cell-\w+" data-bond="1" data-month="(\d{4}-\d{2})"', html)
    assert row_cells == span_keys("2031-02", "2031-07")
    assert 'cell cell-due" data-bond="1" data-month="2031-02"' in html
    assert "FarCo" in html
    assert 'data-status="Danger"' in html


def test_tc18_status_scan_for_feb2031_bond_uses_same_rules(db_path):
    from src.status import compute_row_status

    months = {"2031-02": False, "2031-03": True, "2031-04": True}
    status = compute_row_status(months, 3, date(2031, 4, 10))
    assert status == "Danger"
    paid = {"2031-02": True, "2031-03": True, "2031-04": True}
    assert compute_row_status(paid, 3, date(2031, 4, 10)) == "Completed"


def test_tc18_derivation_sources_contain_no_hardcoded_window():
    texts = [
        path.read_text(encoding="utf-8")
        for path in sorted((SRC / "queries").glob("*.py"))
    ] + [(SRC / "app.py").read_text(encoding="utf-8")]
    for text in texts:
        assert "2027" not in text
        assert "2031" not in text
        assert "Feb-2027" not in text
        assert "Jan-2031" not in text
        assert "Sep-2025" not in text
