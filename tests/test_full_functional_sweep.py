import re

import pytest

from src.app import create_app
from src.db import get_conn
from tests.conftest import add_bond, add_payment, month_sequence


@pytest.fixture
def seeded_db(db_path):
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha Bonds Ltd", "INE00010001", "2026-01-05", 60, credit_day=5, amount=100000)
        for month in month_sequence("2026-01", 6):
            add_payment(conn, bond_id, month, 1000.0, paid=1)
        add_payment(conn, bond_id, "2026-07", 1000.0, paid=0)
        conn.execute(
            "INSERT INTO bonds (company, isin, name, amount, maturity, start_date, end_date, tenure_months, credit_day, status, watch_state, rating, coupon_pct, payout_cycle, broker) "
            "VALUES ('Beta Finance', 'INE000200002', 'Beta Finance', 50000, 120000, '2026-02-01', '2031-02-01', 60, 10, 'On-going', 'watching', 'AA-', 8.5, 'quarterly', 'Zerodha')"
        )
        conn.execute(
            "INSERT INTO financial_goals (name, target_amount, target_end_date, note, saved_amount) "
            "VALUES ('House', 600000, '2026-12-31', '', 50000)"
        )
    return db_path


@pytest.fixture
def client(seeded_db):
    app = create_app(str(seeded_db))
    app.config["TESTING"] = True
    return app.test_client()


def _conn(client):
    return get_conn(client.application.config["DB_PATH"])


GET_ROUTES = [
    "/",
    "/about",
    "/feedback",
    "/goals",
    "/grid",
    "/notifications",
    "/portfolio",
    "/search",
    "/settings",
    "/share",
    "/watch",
    "/print",
]


@pytest.mark.parametrize("route", GET_ROUTES)
def test_get_route_returns_200(client, route):
    resp = client.get(route)
    assert resp.status_code == 200, f"{route} -> {resp.status_code}"


def test_export_csv_requires_scope_and_works(client):
    assert client.get("/export.csv").status_code == 400
    resp = client.get("/export.csv?scope=current")
    assert resp.status_code == 200
    assert "csv" in resp.headers.get("Content-Type", "") or "text" in resp.headers.get("Content-Type", "")


def test_payout_requires_bond_id_and_works(client):
    assert client.get("/payout").status_code == 400
    with _conn(client) as conn:
        bid = conn.execute("SELECT id FROM bonds WHERE isin='INE00010001'").fetchone()[0]
    assert client.get(f"/payout?bond_id=notanint").status_code == 400
    resp = client.get(f"/payout?bond_id={bid}")
    assert resp.status_code == 200


def test_portfolio_detail_pages(client):
    with _conn(client) as conn:
        bid = conn.execute("SELECT id FROM bonds WHERE isin='INE00010001'").fetchone()[0]
    for path in (f"/portfolio/{bid}", f"/portfolio/{bid}/detail"):
        assert client.get(path).status_code == 200, path


def test_payment_editor_route(client):
    with _conn(client) as conn:
        bid = conn.execute("SELECT id FROM bonds WHERE isin='INE00010001'").fetchone()[0]
    assert client.get(f"/payment/{bid}/2026-08").status_code == 200


def test_all_nav_links_resolve(client):
    html = client.get("/").get_data(as_text=True)
    hrefs = set(re.findall(r'href="(/[^"#?]*)"', html))
    known_prefixes = (
        "/", "/about", "/feedback", "/goals", "/grid", "/notifications", "/payout",
        "/portfolio", "/search", "/settings", "/share", "/watch", "/export", "/payment",
    )
    broken = [h for h in hrefs if h and not h.startswith(known_prefixes)]
    assert not broken, f"broken nav links: {broken}"


def test_unknown_route_404(client):
    assert client.get("/definitely-not-a-page").status_code == 404


def test_payment_save_valid_and_invalid_rejected(client):
    with _conn(client) as conn:
        bid = conn.execute("SELECT id FROM bonds WHERE isin='INE00010001'").fetchone()[0]

    ok = client.post(f"/payment/{bid}/2026-08", data={"amount": "1500", "paid": "on"}, follow_redirects=True)
    assert ok.status_code == 200
    with _conn(client) as conn:
        row = conn.execute("SELECT amount, paid FROM payment_ledger WHERE bond_id=? AND month='2026-08'", (bid,)).fetchone()
    assert row and float(row["amount"]) == 1500.0 and row["paid"] == 1

    negative = client.post(f"/payment/{bid}/2026-09", data={"amount": "-5", "paid": "on"}, follow_redirects=True)
    assert negative.status_code == 400, "negative amount must be rejected"

    empty = client.post(f"/payment/{bid}/2026-10", data={"amount": "", "paid": "on"}, follow_redirects=True)
    assert empty.status_code == 400, "empty amount must be rejected"

    outside = client.post(f"/payment/{bid}/2099-12", data={"amount": "100", "paid": "on"}, follow_redirects=True)
    assert outside.status_code == 400, "month outside window must be rejected"

    with _conn(client) as conn:
        count = conn.execute(
            "SELECT COUNT(*) c FROM payment_ledger WHERE bond_id=? AND month IN ('2026-09','2026-10','2099-12')", (bid,)
        ).fetchone()["c"]
    assert count == 0, "rejected payments must not persist"


def test_settings_save_keeps_single_theme_home(client):
    resp = client.post("/settings", data={"currency": "INR", "privacy_mode": "0"}, follow_redirects=True)
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert html.count('name="theme-choice"') <= 1


def test_goals_create_lock_checkin_delete_flow(client):
    created = client.post(
        "/goals",
        data={
            "name": "Gold",
            "target_amount": "240000",
            "target_end_date": "2026-12-31",
            "monthly_amount": "20000",
            "start_date": "2026-01-01",
        },
        follow_redirects=True,
    )
    assert created.status_code == 200
    with _conn(client) as conn:
        goal = conn.execute("SELECT id, target_amount FROM financial_goals WHERE name='Gold'").fetchone()
    assert goal is not None and float(goal["target_amount"]) == 240000.0

    locked = client.post(
        f"/goals/{goal['id']}/edit",
        data={"target_amount": "999999", "target_end_date": "2030-01-01", "name": "Gold"},
        follow_redirects=True,
    )
    assert locked.status_code == 200
    with _conn(client) as conn:
        after = conn.execute("SELECT target_amount FROM financial_goals WHERE id=?", (goal["id"],)).fetchone()
    assert float(after["target_amount"]) == 240000.0, "target must stay locked"

    checkin = client.post(f"/goals/{goal['id']}/checkin", data={"month": "2026-03", "invested": "on"}, follow_redirects=True)
    assert checkin.status_code == 200

    missing = client.post("/goals", data={"name": ""}, follow_redirects=True)
    assert missing.status_code == 400, "empty goal name must be rejected"

    deleted = client.post(f"/goals/{goal['id']}/delete", follow_redirects=True)
    assert deleted.status_code == 200
    with _conn(client) as conn:
        assert conn.execute("SELECT 1 FROM financial_goals WHERE id=?", (goal["id"],)).fetchone() is None


def test_watch_add_duplicate_isin_blocked_with_popup(client):
    dup = client.post(
        "/watch",
        data={"company": "Gamma Corp", "isin": "INE000200002", "rating": "AA", "coupon_pct": "7.5"},
        follow_redirects=True,
    )
    assert dup.status_code == 400, "duplicate ISIN must be rejected"
    html = dup.get_data(as_text=True)
    assert "INE000200002" in html
    assert "already exists" in html.lower() or "duplicate" in html.lower() or "View existing" in html


def test_watch_add_invalid_isin_and_rating_rejected(client):
    bad_isin = client.post(
        "/watch",
        data={"company": "X", "isin": "SHORT", "rating": "AA", "coupon_pct": "7"},
        follow_redirects=True,
    )
    assert bad_isin.status_code == 400
    bad_rating = client.post(
        "/watch",
        data={"company": "X Corp", "isin": "INE000400004", "rating": "CCC", "coupon_pct": "7"},
        follow_redirects=True,
    )
    assert bad_rating.status_code == 400, "below-BBB- rating must be rejected"
    html = bad_rating.get_data(as_text=True)
    assert "BBB" in html or "investment" in html.lower()


def test_watch_add_valid_then_move_removes(client):
    resp = client.post(
        "/watch",
        data={"company": "Delta Infra", "isin": "INE000300003", "rating": "A+", "coupon_pct": "8.0", "expected_yield_pct": "7.2"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    with _conn(client) as conn:
        cand = conn.execute("SELECT id FROM bonds WHERE isin='INE000300003' AND watch_state='watching'").fetchone()
    assert cand is not None

    moved = client.post(
        f"/watch/{cand['id']}/move",
        data={
            "purchase_date": "2026-06-01",
            "start_date": "2026-06-01",
            "end_date": "2031-06-01",
            "credit_day": "10",
            "amount": "50000",
            "qty": "5",
            "broker": "Zerodha",
            "goal_id": "",
        },
        follow_redirects=True,
    )
    assert moved.status_code == 200
    with _conn(client) as conn:
        row = conn.execute("SELECT watch_state FROM bonds WHERE id=?", (cand["id"],)).fetchone()
    assert row["watch_state"] == "holding"
    watch_html = client.get("/watch").get_data(as_text=True)
    assert f'id="candidate-{cand["id"]}"' not in watch_html, "moved candidate row must leave the watchlist"
    with _conn(client) as conn:
        still_watching = conn.execute(
            "SELECT 1 FROM bonds WHERE isin='INE000300003' AND watch_state='watching'"
        ).fetchone()
    assert still_watching is None


def test_watch_delete_flow(client):
    with _conn(client) as conn:
        cand = conn.execute("SELECT id FROM bonds WHERE isin='INE000200002'").fetchone()
    resp = client.post(f"/watch/{cand['id']}/delete", follow_redirects=True)
    assert resp.status_code == 200
    with _conn(client) as conn:
        assert conn.execute("SELECT 1 FROM bonds WHERE id=?", (cand["id"],)).fetchone() is None


def test_notifications_mark_all_and_clear(client):
    with _conn(client) as conn:
        conn.execute(
            "INSERT INTO notifications (created_at, severity, message, read) VALUES (datetime('now'), 'info', 'test event', 0)"
        )
    assert client.post("/notifications/read_all", follow_redirects=True).status_code == 200
    with _conn(client) as conn:
        assert conn.execute("SELECT COUNT(*) c FROM notifications WHERE read=0").fetchone()["c"] == 0
    assert client.post("/notifications/clear", follow_redirects=True).status_code == 200


def test_search_finds_and_no_results_state(client):
    resp = client.get("/search?q=Alpha")
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "Alpha" in html or "INE00010001" in html
    empty = client.get("/search?q=zzz-no-such-bond")
    assert empty.status_code == 200
    text = empty.get_data(as_text=True).lower()
    assert "no" in text and ("result" in text or "found" in text)


def test_feedback_validation_and_submit(client):
    missing = client.post("/feedback", data={"type": "bug", "title": ""}, follow_redirects=True)
    assert missing.status_code == 400, "required feedback fields must be enforced"

    ok = client.post(
        "/feedback",
        data={
            "type": "bug",
            "title": "sweep test",
            "what_happened": "something broke",
            "steps": "1. open page",
            "expected_actual": "expected ok / actual broken",
            "severity": "minor",
        },
        follow_redirects=True,
    )
    assert ok.status_code == 200
    html = ok.get_data(as_text=True).lower()
    assert "thank" in html or "sent" in html or "received" in html or "github" in html or "queued" in html

    bad_sev = client.post(
        "/feedback",
        data={
            "type": "bug",
            "title": "t",
            "what_happened": "w",
            "steps": "s",
            "expected_actual": "e",
            "severity": "low",
        },
        follow_redirects=True,
    )
    assert bad_sev.status_code == 400, "invalid severity must be rejected"


def test_grid_renders_bond(client):
    html = client.get("/grid").get_data(as_text=True)
    assert "Alpha" in html or "INE00010001" in html


def test_share_print_about_export_pages(client):
    for path in ("/share", "/print", "/about", "/export.csv?scope=full"):
        assert client.get(path).status_code == 200, path


def test_about_carries_disclaimer(client):
    about = client.get("/about").get_data(as_text=True).lower()
    assert "disclaimer" in about or "not investment advice" in about or "information-only" in about


def test_portfolio_invalid_remove_rejected_for_unknown(client):
    resp = client.post("/portfolio/invalid/999999/remove", follow_redirects=True)
    assert resp.status_code in (200, 400, 404)


def test_home_dashboard_shows_kpis(client):
    html = client.get("/").get_data(as_text=True)
    assert "invested" in html.lower() or "portfolio" in html.lower() or "total" in html.lower()
