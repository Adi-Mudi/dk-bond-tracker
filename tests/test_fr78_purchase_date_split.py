import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn, init_db
from src.engine import tenure_window
from src.phase4 import payout_schedule
from src.queries import month_label
from src.validators import add_months


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def add_candidate(client, isin, company="FR78 Co"):
    response = client.post(
        "/watch",
        data={
            "company": company,
            "isin": isin,
            "rating": "AA",
            "coupon_pct": "8.0",
            "expected_yield_pct": "8.5",
            "broker": "Zerodha",
        },
    )
    assert response.status_code == 302


def candidate_id(db_path, isin):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (isin.upper(),)
        ).fetchone()["id"]


def move_payload(purchase_date, start_date, end_date, **overrides):
    data = {
        "purchase_date": purchase_date,
        "start_date": start_date,
        "end_date": end_date,
        "credit_day": "5",
        "qty": "100",
        "amount": "100000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def ledger_months(db_path, bond_id):
    with get_conn(db_path) as conn:
        return [
            row["month"]
            for row in conn.execute(
                "SELECT month FROM payment_ledger WHERE bond_id = ? ORDER BY month",
                (bond_id,),
            ).fetchall()
        ]


def legacy_db_without_purchase_date(path):
    conn = sqlite3.connect(str(path))
    conn.execute(
        "CREATE TABLE bonds ("
        "id INTEGER PRIMARY KEY, company TEXT, isin TEXT UNIQUE, name TEXT, "
        "amount REAL, maturity REAL, start_date TEXT, end_date TEXT, tenure_months INTEGER, "
        "credit_day INTEGER, status TEXT DEFAULT 'On-going', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
    )
    conn.execute(
        "CREATE TABLE payment_ledger ("
        "id INTEGER PRIMARY KEY, bond_id INTEGER NOT NULL REFERENCES bonds(id), "
        "month TEXT, amount REAL, paid INTEGER DEFAULT 0, UNIQUE (bond_id, month))"
    )
    conn.execute(
        "CREATE TABLE financial_goals (id INTEGER PRIMARY KEY, name TEXT, target_amount REAL, "
        "target_end_date TEXT, note TEXT)"
    )
    conn.execute(
        "CREATE TABLE notifications (id INTEGER PRIMARY KEY, created_at TEXT DEFAULT CURRENT_TIMESTAMP, "
        "severity TEXT, message TEXT, read INTEGER DEFAULT 0)"
    )
    conn.execute("CREATE TABLE alert_prefs (id INTEGER PRIMARY KEY, key TEXT UNIQUE, value TEXT)")
    conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
        "VALUES ('Legacy Co', 'INE780000001', 'Legacy Co', 100000.0, '2026-01-01', '2026-12-01', 11, 5)"
    )
    conn.commit()
    conn.close()


def test_fr78_schema_fresh_db_has_purchase_date(tmp_path):
    db = tmp_path / "bonds.db"
    init_db(db)
    with get_conn(db) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(bonds)").fetchall()]
    assert "purchase_date" in columns


def test_fr78_schema_legacy_db_gains_purchase_date_and_rows_stay_null(tmp_path):
    legacy = tmp_path / "legacy_bonds.db"
    legacy_db_without_purchase_date(legacy)
    init_db(legacy)
    with get_conn(legacy) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(bonds)").fetchall()]
        assert "purchase_date" in columns
        row = conn.execute(
            "SELECT purchase_date FROM bonds WHERE isin = 'INE780000001'"
        ).fetchone()
    assert row["purchase_date"] is None


def test_fr78_ac1_distinct_purchase_and_start_dates_stored(client, db_path):
    add_candidate(client, "INE780000010")
    bond_id = candidate_id(db_path, "INE780000010")
    response = client.post(
        f"/watch/{bond_id}/move",
        data=move_payload("2026-11-03", "2026-11-05", "2027-11-05"),
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT purchase_date, start_date, watch_state FROM bonds WHERE id = ?",
            (bond_id,),
        ).fetchone()
    assert row["watch_state"] == "holding"
    assert row["purchase_date"] == "2026-11-03"
    assert row["start_date"] == "2026-11-05"
    assert row["purchase_date"] != row["start_date"]


@pytest.mark.parametrize("bad_value", ["", "not-a-date"])
def test_fr78_ac1_bad_purchase_date_rejected_with_zero_writes(client, db_path, bad_value):
    add_candidate(client, "INE780000011")
    bond_id = candidate_id(db_path, "INE780000011")
    response = client.post(
        f"/watch/{bond_id}/move",
        data=move_payload(bad_value, "2026-11-05", "2027-11-05"),
    )
    assert response.status_code == 400
    assert "purchase_date" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT purchase_date, watch_state FROM bonds WHERE id = ?", (bond_id,)
        ).fetchone()
        ledger = conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"]
    assert row["watch_state"] == "watching"
    assert row["purchase_date"] is None
    assert ledger == 0


def test_fr78_ac2_payout_months_derive_from_start_date_not_purchase_date(client, db_path):
    base = date.today().replace(day=1)
    start = add_months(base, -2)
    end = add_months(start, 12)
    purchase_a = add_months(start, -3)
    purchase_b = add_months(start, -1)

    add_candidate(client, "INE780000021", company="FR78 A")
    add_candidate(client, "INE780000022", company="FR78 B")
    id_a = candidate_id(db_path, "INE780000021")
    id_b = candidate_id(db_path, "INE780000022")
    first = client.post(
        f"/watch/{id_a}/move",
        data=move_payload(purchase_a.isoformat(), start.isoformat(), end.isoformat()),
    )
    second = client.post(
        f"/watch/{id_b}/move",
        data=move_payload(purchase_b.isoformat(), start.isoformat(), end.isoformat()),
    )
    assert first.status_code == 302 and second.status_code == 302

    current_key = f"{base.year:04d}-{base.month:02d}"
    expected = [key for key in tenure_window(start, 12) if key <= current_key]
    with get_conn(db_path) as conn:
        purchases = {
            row["id"]: row["purchase_date"]
            for row in conn.execute(
                "SELECT id, purchase_date FROM bonds WHERE id IN (?, ?)", (id_a, id_b)
            ).fetchall()
        }
        schedule_a = payout_schedule(conn, id_a, "monthly")
        schedule_b = payout_schedule(conn, id_b, "monthly")

    assert purchases[id_a] != purchases[id_b]
    assert ledger_months(db_path, id_a) == expected
    assert ledger_months(db_path, id_b) == expected
    assert expected[0] == f"{start.year:04d}-{start.month:02d}"
    assert f"{purchase_a.year:04d}-{purchase_a.month:02d}" not in expected
    assert f"{purchase_b.year:04d}-{purchase_b.month:02d}" not in expected

    assert schedule_a["start_month"] == f"{start.year:04d}-{start.month:02d}"
    assert [item["month"] for item in schedule_a["instances"]] == [
        item["month"] for item in schedule_b["instances"]
    ]

    grid = client.get("/grid")
    assert grid.status_code == 200
    grid_html = grid.get_data(as_text=True)
    assert month_label(f"{start.year:04d}-{start.month:02d}") in grid_html
    assert month_label(f"{purchase_a.year:04d}-{purchase_a.month:02d}") not in grid_html
    assert client.get("/print").status_code == 200


def test_fr78_ac3_move_panel_has_two_labeled_date_fields(client, db_path):
    add_candidate(client, "INE780000031")
    bond_id = candidate_id(db_path, "INE780000031")
    html = client.get("/watch").get_data(as_text=True)
    panel = re.search(
        r'<tr class="move-row" id="move-panel-' + str(bond_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert panel, "move panel must render as a hidden row"
    panel_html = panel.group(1)
    assert re.search(
        r'<input type="date" id="move-purchase-\d+" name="purchase_date" required>', panel_html
    )
    assert re.search(
        r'<input type="date" id="move-start-\d+" name="start_date" required>', panel_html
    )
    assert ">Purchase date</label>" in panel_html
    assert ">Start date (interest accrual / dated date)</label>" in panel_html
    assert "Purchase date (start date)" not in html


def test_fr78_ac3_merged_label_absent_from_source_tree():
    src = Path(__file__).resolve().parents[1] / "src"
    offenders = []
    for path in sorted(src.rglob("*")):
        if not path.is_file() or "__pycache__" in path.parts:
            continue
        if (src / "design") in path.parents:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if "Purchase date (start date)" in text:
            offenders.append(str(path))
    assert offenders == []
