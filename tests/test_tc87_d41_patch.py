import pytest

from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def watch_post(client, **overrides):
    data = {
        "company": "Alpha Ltd",
        "isin": "INE9000A0100",
        "rating": "AA",
        "coupon_pct": "7.5",
        "expected_yield_pct": "8.0",
        "source_note": "n",
        "broker": "",
    }
    data.update(overrides)
    return client.post("/watch", data=data, follow_redirects=False)


def inject_tenure_zero(db_path):
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, status, watch_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'holding')",
            ("BadCo", "INE9000A01999", "BadCo", 1000.0, "2026-11-14", "2026-11-30", 0, 5, "On-going"),
        )
        return cursor.lastrowid


def test_tc87_watch_zero_coupon_and_yield_accepted(client):
    response = watch_post(client, coupon_pct="0.00", expected_yield_pct="0.00")
    assert response.status_code == 302


def test_tc87_watch_zero_variants_accepted(client):
    variants = (
        ("0", "INE9000A0101", "Var Zero One"),
        ("0.0", "INE9000A0102", "Var Zero Two"),
        ("0.00", "INE9000A0103", "Var Zero Three"),
    )
    for value, isin, company in variants:
        response = watch_post(client, coupon_pct=value, expected_yield_pct=value, isin=isin, company=company)
        assert response.status_code == 302, value


def test_tc87_watch_percent_rejections_still_named(client):
    empty = watch_post(client, coupon_pct="")
    assert empty.status_code == 400
    assert "coupon is required" in empty.get_data(as_text=True)
    text = watch_post(client, expected_yield_pct="abc")
    assert text.status_code == 400
    assert "est yield must be a number" in text.get_data(as_text=True)
    negative = watch_post(client, coupon_pct="-1")
    assert negative.status_code == 400
    assert "must not be negative" in negative.get_data(as_text=True)


def test_tc87_move_same_month_rejected_no_row_inserted(client, db_path):
    watch_post(client)
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0100'"
        ).fetchone()["id"]
    response = client.post(
        f"/watch/{candidate_id}/move",
        data={
            "purchase_date": "2026-11-14",
            "start_date": "2026-11-14",
            "end_date": "2026-11-30",
            "credit_day": "5",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert "tenure must span at least one whole month" in html
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT tenure_months, watch_state FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row["tenure_months"] is None
    assert row["watch_state"] == "watching"


def test_tc87_tenure_zero_row_surfaces_stay_200_with_invalid_chip(client, db_path):
    bond_id = inject_tenure_zero(db_path)
    for path in ("/", "/portfolio", "/portfolio?tab=payouts", "/print"):
        response = client.get(path)
        assert response.status_code == 200, path
    holdings = client.get("/portfolio").get_data(as_text=True)
    assert "chip-invalid" in holdings
    assert ">Invalid<" in holdings
    assert "dates need review" in holdings
    assert f"remove-invalid-{bond_id}" in holdings


def test_tc87_remove_button_deletes_invalid_row(client, db_path):
    bond_id = inject_tenure_zero(db_path)
    response = client.post(
        f"/portfolio/invalid/{bond_id}/remove", follow_redirects=False
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT id FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    assert row is None


def test_tc87_remove_refused_while_row_is_valid(client, db_path):
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, status, watch_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'holding')",
            ("GoodCo", "INE9000A01888", "GoodCo", 1000.0, "2026-01-01", "2026-12-31", 11, 5, "On-going"),
        )
        bond_id = cursor.lastrowid
    response = client.post(
        f"/portfolio/invalid/{bond_id}/remove", follow_redirects=False
    )
    assert response.status_code == 400
    assert "ERR-invalid-remove" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT id FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    assert row is not None


def test_tc87_broker_roundtrip_candidate_move_detail(client, db_path):
    response = watch_post(client, broker="HDFC Securities")
    assert response.status_code == 302
    watch_html = client.get("/watch").get_data(as_text=True)
    assert "HDFC Securities" in watch_html
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0100'"
        ).fetchone()["id"]
    response = client.post(
        f"/watch/{candidate_id}/move",
        data={
            "purchase_date": "2026-10-01",
            "start_date": "2026-10-01",
            "end_date": "2027-03-31",
            "credit_day": "5",
            "qty": "50",
            "amount": "50000",
            "broker": "HDFC Securities",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302
    detail = client.get(f"/portfolio/{candidate_id}/detail").get_json()
    assert detail["broker"] == "HDFC Securities"
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT broker, watch_state FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row["broker"] == "HDFC Securities"
    assert row["watch_state"] == "holding"


def test_tc87_direct_add_route_removed(client, db_path):
    response = client.post(
        "/portfolio",
        data={
            "company": "Direct Co",
            "isin": "INE9000A01777",
            "amount": "50000",
            "credit_day": "15",
            "start_date": "2026-10-01",
            "end_date": "2027-03-31",
            "coupon_pct": "7.5",
            "expected_yield_pct": "8.0",
            "broker": "ICICI Direct",
        },
        follow_redirects=False,
    )
    assert response.status_code == 405
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A01777'"
        ).fetchone()
    assert row is None


def test_tc87_move_requires_broker(client, db_path):
    watch_post(client, broker="Kotak Securities")
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0100'"
        ).fetchone()["id"]
    response = client.post(
        f"/watch/{candidate_id}/move",
        data={
            "purchase_date": "2026-10-01",
            "start_date": "2026-10-01",
            "end_date": "2027-03-31",
            "credit_day": "5",
            "qty": "50",
            "amount": "50000",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "broker is required" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT broker, watch_state FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row["broker"] == "Kotak Securities"
    assert row["watch_state"] == "watching"


def test_tc87_labels_present_on_watch_moves(client):
    watch_post(client)
    watch_html = client.get("/watch").get_data(as_text=True)
    assert "Purchase date" in watch_html
    assert "Start date (interest accrual / dated date)" in watch_html
    assert "End date" in watch_html
    assert "Credit day — when the amount is credited each month" in watch_html
    portfolio_html = client.get("/portfolio").get_data(as_text=True)
    assert 'id="add-position"' not in portfolio_html


def test_tc87_watchlist_has_broker_column_before_source_note(client):
    watch_post(client, broker="Axis Direct")
    html = client.get("/watch").get_data(as_text=True)
    broker_index = html.index("<th>Broker</th>")
    source_index = html.index("<th>Source note</th>")
    assert broker_index < source_index
    assert "Axis Direct" in html


def test_tc87_holdings_table_stays_nine_columns(client):
    response = client.get("/portfolio")
    html = response.get_data(as_text=True)
    table = html[html.index('<table id="holdings-table">'):]
    table = table[: table.index("</thead>")]
    assert table.count("</th>") == 9


def test_tc87_invalid_row_detail_drawer_still_returns_json(client, db_path):
    bond_id = inject_tenure_zero(db_path)
    response = client.get(f"/portfolio/{bond_id}/detail")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "Invalid"


def inject_bad_amount(db_path):
    with get_conn(db_path) as conn:
        cursor = conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, "
            "tenure_months, credit_day, status, watch_state) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'holding')",
            (
                "BadAmt Co",
                "INE9000A01555",
                "BadAmt Co",
                "abc",
                "2026-10-01",
                "2027-03-31",
                6,
                5,
                "On-going",
            ),
        )
        return cursor.lastrowid


def test_tc87_f221_non_numeric_amount_surfaces_stay_200_invalid_row(client, db_path):
    bond_id = inject_bad_amount(db_path)
    for path in ("/", "/portfolio", "/portfolio?tab=payouts", "/watch"):
        response = client.get(path)
        assert response.status_code == 200, path
    holdings = client.get("/portfolio").get_data(as_text=True)
    assert "chip-invalid" in holdings
    assert ">Invalid<" in holdings
    assert "dates need review" in holdings
    payouts = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    assert "chip-invalid" in payouts
    detail = client.get(f"/portfolio/{bond_id}/detail").get_json()
    assert detail["status"] == "Invalid"
    assert detail["invested"] == 0.0


def test_tc87_f222_watch_percent_empty_rejected_zero_rows(client, db_path):
    base = {
        "rating": "AA",
        "coupon_pct": "7.5",
        "expected_yield_pct": "8.0",
    }
    empty_coupon = dict(
        base, company="Pct Co One", isin="INE9000A0661", coupon_pct=""
    )
    response = client.post("/watch", data=empty_coupon, follow_redirects=False)
    assert response.status_code == 400
    assert "coupon is required" in response.get_data(as_text=True)
    empty_yield = dict(
        base, company="Pct Co Two", isin="INE9000A0662", expected_yield_pct=""
    )
    response = client.post("/watch", data=empty_yield, follow_redirects=False)
    assert response.status_code == 400
    assert "est yield is required" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    assert count == 0
    zeros = dict(
        base,
        company="Pct Co Zero",
        isin="INE9000A0663",
        coupon_pct="0.00",
        expected_yield_pct="0.00",
    )
    response = client.post("/watch", data=zeros, follow_redirects=False)
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT coupon_pct, expected_yield_pct FROM bonds WHERE isin = 'INE9000A0663'"
        ).fetchone()
    assert row["coupon_pct"] == 0.0
    assert row["expected_yield_pct"] == 0.0


def test_tc87_f223_invalid_remove_rejects_watching_candidate(client, db_path):
    response = watch_post(client)
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0100'"
        ).fetchone()["id"]
    response = client.post(
        f"/portfolio/invalid/{candidate_id}/remove", follow_redirects=False
    )
    assert response.status_code == 400
    assert "ERR-invalid-remove" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT watch_state FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row is not None
    assert row["watch_state"] == "watching"


def test_tc87_f224a_payouts_invalid_row_shows_remove_and_post_works(client, db_path):
    bond_id = inject_tenure_zero(db_path)
    payouts = client.get("/portfolio?tab=payouts").get_data(as_text=True)
    assert f"remove-invalid-payouts-{bond_id}" in payouts
    assert ">Remove<" in payouts
    response = client.post(
        f"/portfolio/invalid/{bond_id}/remove", follow_redirects=False
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute("SELECT id FROM bonds WHERE id = ?", (bond_id,)).fetchone()
    assert row is None


def test_tc87_f225_blank_broker_stores_null_on_watch_path_and_blocks_move(client, db_path):
    response = watch_post(client, broker="   ")
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        candidate_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0100'"
        ).fetchone()["id"]
    response = client.post(
        f"/watch/{candidate_id}/move",
        data={
            "purchase_date": "2026-10-01",
            "start_date": "2026-10-01",
            "end_date": "2027-03-31",
            "credit_day": "5",
            "qty": "50",
            "amount": "50000",
            "broker": "  ",
        },
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "broker is required" in response.get_data(as_text=True)
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT broker, watch_state FROM bonds WHERE id = ?", (candidate_id,)
        ).fetchone()
    assert row["broker"] is None
    assert row["watch_state"] == "watching"


def test_tc87_amount_fault_dashboard_note_and_removable(client, db_path):
    bond_id = inject_bad_amount(db_path)
    dash = client.get("/").get_data(as_text=True)
    assert 'id="invalid-rows-note"' in dash
    assert "need review" in dash
    r = client.post(f"/portfolio/invalid/{bond_id}/remove")
    assert r.status_code == 302
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM bonds WHERE id = ?", (bond_id,)).fetchone()["n"] == 0
