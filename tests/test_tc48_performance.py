import time
from datetime import date

import pytest

from src.app import create_app
from src.db import get_conn, init_db
from src.validators import add_months

pytestmark = pytest.mark.remote

BOND_COUNT = 150
MONTHS = 96
THRESHOLD_SECONDS = 2.0


def month_sequence(start_month, count):
    year, mon = map(int, start_month.split("-"))
    out = []
    for offset in range(count):
        month = mon + offset
        out.append(f"{year + (month - 1) // 12:04d}-{(month - 1) % 12 + 1:02d}")
    return out


def seed_scale_database(db_path):
    init_db(db_path)
    today = date.today()
    start = add_months(today.replace(day=1), -10)
    end = add_months(start, MONTHS)
    start_key = f"{start.year:04d}-{start.month:02d}"
    months = month_sequence(start_key, MONTHS)
    bonds = [
        (
            f"Scale Bond {index:03d}",
            f"INESCALE{index:06d}",
            f"Scale Bond {index:03d}",
            100000.0 + index,
            120000.0 + index,
            start.isoformat(),
            end.isoformat(),
            MONTHS,
            5,
            "On-going",
        )
        for index in range(BOND_COUNT)
    ]
    ledger = []
    for bond_id in range(1, BOND_COUNT + 1):
        for month in months:
            ledger.append((bond_id, month, 1000.0, 1))
    with get_conn(db_path) as conn:
        conn.executemany(
            "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, "
            "tenure_months, credit_day, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            bonds,
        )
        conn.executemany(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            ledger,
        )
    return months


def schema_snapshot(db_path):
    with get_conn(db_path) as conn:
        tables = {}
        for table in ("bonds", "payment_ledger"):
            tables[table] = [
                (row["name"], row["type"], row["notnull"], row["pk"])
                for row in conn.execute(f"PRAGMA table_info({table})")
            ]
        counts = {
            "bonds": conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"],
            "ledger": conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"],
        }
    return tables, counts


@pytest.fixture
def scale_client(tmp_path):
    db_path = tmp_path / "scale.db"
    seed_scale_database(db_path)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client(), db_path


def timed_get(client, path):
    started = time.perf_counter()
    response = client.get(path)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    return elapsed


def test_tc48_dashboard_under_two_seconds_at_150x96(scale_client):
    client, _db_path = scale_client
    elapsed = timed_get(client, "/")
    assert elapsed < THRESHOLD_SECONDS, f"dashboard took {elapsed:.3f}s"


def test_tc48_grid_under_two_seconds_at_150x96(scale_client):
    client, _db_path = scale_client
    elapsed = timed_get(client, "/grid")
    assert elapsed < THRESHOLD_SECONDS, f"grid took {elapsed:.3f}s"


def test_tc48_schema_unchanged_by_scaled_render(scale_client):
    client, db_path = scale_client
    before_tables, before_counts = schema_snapshot(db_path)
    assert timed_get(client, "/") < THRESHOLD_SECONDS
    assert timed_get(client, "/grid") < THRESHOLD_SECONDS
    after_tables, after_counts = schema_snapshot(db_path)
    assert after_tables == before_tables
    assert after_counts == {"bonds": BOND_COUNT, "ledger": BOND_COUNT * MONTHS}


def test_tc48_dashboard_body_covers_seeded_scale(scale_client):
    client, _db_path = scale_client
    body = client.get("/").get_data(as_text=True)
    assert f"bonds: {BOND_COUNT}" in body
    assert "Scale Bond 000" in body
    assert f"Scale Bond {BOND_COUNT - 1:03d}" in body
