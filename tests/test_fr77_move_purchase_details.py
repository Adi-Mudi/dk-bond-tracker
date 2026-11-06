import re
from datetime import date

import pytest

from conftest import add_ongoing_seed, bond_count
from src.app import create_app
from src.db import get_conn
from src.status import month_key
from src.validators import AppError, add_months, validate_positive_int


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def make_candidate(client, db_path, company="Alpha Ltd", isin="INE9000A0200", **overrides):
    data = {
        "company": company,
        "isin": isin,
        "rating": "AA",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
        "broker": "Zerodha",
    }
    data.update(overrides)
    response = client.post("/watch", data=data)
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        return conn.execute("SELECT id FROM bonds WHERE isin = ?", (isin.upper(),)).fetchone()["id"]


def valid_move(**overrides):
    data = {
        "start_date": "2026-08-01",
        "end_date": "2028-08-01",
        "credit_day": "5",
        "qty": "100",
        "amount": "100000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def ledger_count(db_path):
    with get_conn(db_path) as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM payment_ledger").fetchone()["n"]


def row_state(db_path, bond_id):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT watch_state FROM bonds WHERE id = ?", (bond_id,)
        ).fetchone()["watch_state"]


def ledger_months(db_path, bond_id):
    with get_conn(db_path) as conn:
        rows = conn.execute(
            "SELECT month, amount, paid FROM payment_ledger WHERE bond_id = ? ORDER BY month",
            (bond_id,),
        ).fetchall()
    return [(row["month"], row["amount"], row["paid"]) for row in rows]


def expected_seed_months(start):
    months = []
    offset = 0
    current = month_key(date.today())
    while True:
        key = month_key(add_months(start, offset))
        if key > current:
            break
        months.append(key)
        offset += 1
    return months


@pytest.mark.parametrize(
    "field,bad_value,named",
    [
        ("start_date", "", "start_date"),
        ("start_date", "not-a-date", "start_date"),
        ("end_date", "", "end_date"),
        ("credit_day", "", "credit day must be an integer in 1-31"),
        ("credit_day", "abc", "credit day must be an integer in 1-31"),
        ("qty", "", "qty must be a positive integer"),
        ("qty", "0", "qty must be a positive integer"),
        ("qty", "2.5", "qty must be a positive integer"),
        ("amount", "", "amount is required"),
        ("amount", "-5", "amount must not be negative"),
        ("amount", "abc", "amount must be a number"),
        ("broker", "   ", "broker is required"),
    ],
)
def test_fr77_ac1_each_required_field_rejected_with_zero_writes(
    client, db_path, field, bad_value, named
):
    candidate_id = make_candidate(client, db_path)
    before_bonds = None
    with get_conn(db_path) as conn:
        before_bonds = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    response = client.post(
        f"/watch/{candidate_id}/move", data=valid_move(**{field: bad_value})
    )
    assert response.status_code == 400
    assert named in response.get_data(as_text=True)
    assert row_state(db_path, candidate_id) == "watching"
    with get_conn(db_path) as conn:
        after_bonds = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    assert after_bonds == before_bonds
    assert ledger_count(db_path) == 0


def test_fr77_ac2_happy_path_stores_all_fields_and_seeds_ledger(client, db_path):
    candidate_id = make_candidate(client, db_path, company="Alpha Ltd", isin="INE9000A0201")
    base = date.today().replace(day=1)
    start = add_months(base, -3)
    end = add_months(start, 24)
    payload = valid_move(
        start_date=start.isoformat(),
        end_date=end.isoformat(),
        credit_day="5",
        qty="100",
        amount="100000",
        broker="Kotak Securities",
    )
    response = client.post(f"/watch/{candidate_id}/move", data=payload)
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT * FROM bonds WHERE id = ?", (candidate_id,)).fetchone()
    assert row["watch_state"] == "holding"
    assert row["start_date"] == start.isoformat()
    assert row["end_date"] == end.isoformat()
    assert row["tenure_months"] == 24
    assert row["credit_day"] == 5
    assert row["amount"] == 100000.0
    assert row["qty"] == 100
    assert row["broker"] == "Kotak Securities"

    expected = expected_seed_months(start)
    assert len(expected) == 4
    seeded = ledger_months(db_path, candidate_id)
    assert [month for month, _amount, _paid in seeded] == expected
    assert all(amount == 0 and paid == 0 for _month, amount, paid in seeded)

    watch_html = client.get("/watch").get_data(as_text=True)
    assert f'id="move-panel-{candidate_id}"' not in watch_html
    portfolio_html = client.get("/portfolio").get_data(as_text=True)
    assert "Alpha Ltd" in portfolio_html


def test_fr77_ac3_active_position_lock_rejects_move_with_zero_writes(client, db_path):
    candidate_id = make_candidate(
        client, db_path, company="Beta Finance Ltd", isin="INE9000A0202"
    )
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "Beta Finance Ltd", "IN1234567890")
    with get_conn(db_path) as conn:
        before_bonds = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    before_ledger = ledger_count(db_path)
    response = client.post(
        f"/watch/{candidate_id}/move", data=valid_move(broker="Zerodha")
    )
    assert response.status_code == 409
    html = response.get_data(as_text=True)
    assert "ERR-active-position" in html
    assert "has an active position" in html
    assert row_state(db_path, candidate_id) == "watching"
    with get_conn(db_path) as conn:
        after_bonds = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    assert after_bonds == before_bonds
    assert ledger_count(db_path) == before_ledger


@pytest.mark.parametrize(
    "start,end",
    [("2026-11-01", "2026-11-01"), ("2026-11-01", "2026-10-15")],
)
def test_fr77_ac4_end_not_after_start_rejected_with_zero_writes(
    client, db_path, start, end
):
    candidate_id = make_candidate(client, db_path)
    response = client.post(
        f"/watch/{candidate_id}/move",
        data=valid_move(start_date=start, end_date=end),
    )
    assert response.status_code == 400
    assert "end_date" in response.get_data(as_text=True)
    assert row_state(db_path, candidate_id) == "watching"
    assert ledger_count(db_path) == 0


def test_fr77_ac4_same_month_zero_tenure_rejected_with_zero_writes(client, db_path):
    candidate_id = make_candidate(client, db_path)
    response = client.post(
        f"/watch/{candidate_id}/move",
        data=valid_move(start_date="2026-11-14", end_date="2026-11-30"),
    )
    assert response.status_code == 400
    assert "tenure must span at least one whole month" in response.get_data(as_text=True)
    assert row_state(db_path, candidate_id) == "watching"
    assert ledger_count(db_path) == 0


def test_fr77_repeat_move_on_holding_rejected_without_new_ledger_rows(client, db_path):
    candidate_id = make_candidate(client, db_path)
    base = date.today().replace(day=1)
    start = add_months(base, -2)
    payload = valid_move(
        start_date=start.isoformat(), end_date=add_months(start, 24).isoformat()
    )
    first = client.post(f"/watch/{candidate_id}/move", data=payload)
    assert first.status_code == 302
    before_ledger = ledger_count(db_path)
    second = client.post(f"/watch/{candidate_id}/move", data=payload)
    assert second.status_code == 400
    assert "already in Portfolio" in second.get_data(as_text=True)
    assert ledger_count(db_path) == before_ledger
    assert row_state(db_path, candidate_id) == "holding"


def test_fr77_panel_requires_and_prefills_purchase_fields(client, db_path):
    candidate_id = make_candidate(client, db_path, broker="Kotak Securities")
    with get_conn(db_path) as conn:
        conn.execute("UPDATE bonds SET qty = ? WHERE id = ?", (150, candidate_id))
    html = client.get("/watch").get_data(as_text=True)
    panel = re.search(
        r'<tr class="move-row" id="move-panel-' + str(candidate_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert panel, "move panel must render as a hidden row"
    panel_html = panel.group(1)
    assert 'name="qty"' in panel_html
    assert 'name="amount"' in panel_html
    assert 'value="150' in panel_html
    assert 'value="Kotak Securities"' in panel_html
    assert panel_html.count("required") >= 5


@pytest.mark.parametrize("value,expected", [("1", 1), ("100", 100), (5, 5)])
def test_validate_positive_int_accepts(value, expected):
    assert validate_positive_int(value, "qty", "ERR-x") == expected


@pytest.mark.parametrize("value", ["", "0", "-1", "2.5", "abc", None, True, 0, -3])
def test_validate_positive_int_rejects(value):
    with pytest.raises(AppError) as exc_info:
        validate_positive_int(value, "qty", "ERR-x")
    assert exc_info.value.code == "ERR-x"
    assert "qty" in exc_info.value.message


def test_fr77_bond_count_helper_matches_candidate_only_fixture(client, db_path):
    make_candidate(client, db_path)
    with get_conn(db_path) as conn:
        assert bond_count(conn) == 1
