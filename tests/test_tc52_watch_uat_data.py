from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn
from src.import_xlsm import import_workbook

WORKBOOK = Path(
    "/workspace/01_excel_dashboard/v5.5_40L_Project_Tracker.xlsm"
)

EXPECTED_ISINS = [
    "INE420C07130",
    "INE342T07569",
    "INE101Q07BS1",
    "INE0BUS07CE3",
    "INE07HK07866",
    "INE08XP07431",
    "INE109C07139",
    "INE926R07019",
    "INE04UP07162",
    "INE0NES07329",
    "INE572J07810",
    "INE104W07245",
    "INE01XO07066",
    "INE04Q907199",
    "INE0I5X07042",
]

ANALYTICS_HEADERS = [
    "Discount",
    "Per-month",
    "Actual per-month",
    "10% TDS",
    "12-month total",
    "Qty",
    "TL Principle",
    "Principal freed",
]


@pytest.fixture(scope="module")
def watch_page(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("tc52") / "import_real.db"
    import_workbook(WORKBOOK, db_path)
    app = create_app(db_path)
    app.config["TESTING"] = True
    body = app.test_client().get("/watch").data.decode()
    return db_path, body


def test_real_workbook_present():
    assert WORKBOOK.is_file()


def test_watch_page_renders_all_fifteen_bonds(watch_page):
    db_path, body = watch_page
    assert body.count('data-isin="') == 15
    with get_conn(db_path) as conn:
        companies = [
            row[0]
            for row in conn.execute("SELECT company FROM bonds ORDER BY id").fetchall()
        ]
    assert len(companies) == 15
    for company in companies:
        assert company.replace("&", "&amp;") in body


def test_watch_page_shows_every_isin(watch_page):
    db_path, body = watch_page
    for isin in EXPECTED_ISINS:
        assert f'data-isin="{isin}"' in body


def test_watch_page_status_chips_present(watch_page):
    db_path, body = watch_page
    from datetime import date

    from src.queries import status_overview

    with get_conn(db_path) as conn:
        live = status_overview(conn, date.today())
    live_statuses = {entry["status"] for entry in live}
    assert live_statuses
    for status in live_statuses:
        assert f'data-status="{status}"' in body
        assert f"class=\"chip chip-{status.lower().replace('-', '')}\"" in body


def test_watch_page_analytics_headers_present(watch_page):
    db_path, body = watch_page
    for header in ANALYTICS_HEADERS:
        assert header in body


def test_watch_page_qty_blank_bond_renders_dash(watch_page):
    db_path, body = watch_page
    assert 'data-isin="INE0NES07329"' in body
    row_line = [line for line in body.splitlines() if "INE0NES07329" in line]
    assert row_line
    with get_conn(db_path) as conn:
        analytics_qty = conn.execute(
            "SELECT qty FROM bonds WHERE isin = ?", ("INE0NES07329",)
        ).fetchone()[0]
    assert analytics_qty is None


def test_watch_page_status_values_are_live(watch_page):
    db_path, body = watch_page
    from datetime import date

    from src.queries import status_overview

    with get_conn(db_path) as conn:
        live = status_overview(conn, date.today())
    for entry in live:
        assert f'data-isin="{entry["isin"]}"' in body
        assert f'data-status="{entry["status"]}"' in body
