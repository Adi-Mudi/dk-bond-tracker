import re
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from conftest import add_bond, add_danger_seed, add_ongoing_seed, add_payment, pay_range
from src.app import create_app
from src.db import get_conn, init_db
from src.status import month_key
from src.validators import add_months, AppError

SIM_TODAY = date(2026, 11, 15)


def make_sim_date(frozen):
    class SimDate(date):
        @classmethod
        def today(cls):
            return frozen

    return SimDate


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def chart_rows(html):
    return re.findall(
        r'<div class="chart-row" data-status="([^"]+)">\s*<div class="chart-label">([^<]+)</div>',
        html,
    )


def returns_table_rows(html):
    table = html.split('id="returns-table"', 1)[1]
    body = table.split("<tbody>", 1)[1].split("</tbody>", 1)[0]
    rows = []
    for raw in re.findall(r"<tr[^>]*>(.*?)</tr>", body, flags=re.S):
        cells = [re.sub(r"<[^>]+>", "", cell).strip() for cell in re.findall(r"<td[^>]*>(.*?)</td>", raw, flags=re.S)]
        rows.append(cells)
    return rows


def seed_matured(conn, company, isin, today):
    start = add_months(today.replace(day=1), -2)
    bond_id = add_bond(conn, company, isin, start.isoformat(), 1)
    pay_range(conn, bond_id, month_key(start), 1)
    return bond_id


def test_tc139_131_dashboard_rows_emit_d43_priority_order(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        add_danger_seed(conn, "DangerCo", "INE0000001391")
        add_ongoing_seed(conn, "OngoingCo", "INE0000001392")
        seed_matured(conn, "DoneCo", "INE0000001393", today)
    html = client.get("/").get_data(as_text=True)
    rows = chart_rows(html)
    assert [status for status, _company in rows] == ["danger", "ongoing", "matured"]
    assert [company for _status, company in rows] == ["DangerCo", "OngoingCo", "DoneCo"]
    assert '<span class="chip chip-danger" id="bar-chip-1">Danger</span>' in html
    assert '<span class="chip chip-ongoing" id="bar-chip-2">On-going</span>' in html
    assert '<span class="chip chip-matured" id="bar-chip-3">Matured</span>' in html


def test_tc139_132_dashboard_tabs_and_filter_chips_markup(client, db_path):
    with get_conn(db_path) as conn:
        add_ongoing_seed(conn, "OngoingCo", "INE0000001394")
    html = client.get("/").get_data(as_text=True)
    assert 'id="dashboard-tabs"' in html
    assert 'class="tab active" data-dtab="overview"' in html
    assert 'class="tab" data-dtab="returns"' in html
    assert 'id="dpanel-overview"' in html
    assert 'id="dpanel-returns"' in html
    for chip_id, label in (
        ("filter-all", "All"),
        ("filter-danger", "Danger"),
        ("filter-ongoing", "On-going"),
        ("filter-matured", "Matured"),
    ):
        assert f'id="{chip_id}"' in html
        assert f">{label}</button>" in html
    assert 'class="btn btn-sm filter-chip active" data-filter="all"' in html
    assert "Sorted by priority" in html
    app_js = client.get("/static/app.js").get_data(as_text=True)
    assert "activateDashboardTab" in app_js
    assert "data-dtab" in app_js
    assert "row.hidden = filter" in app_js


def test_tc139_132_filter_preserves_shared_priority_order(client, db_path):
    today = date.today()
    with get_conn(db_path) as conn:
        seed_matured(conn, "DoneCo", "INE0000001395", today)
        add_ongoing_seed(conn, "BetaOngoing", "INE0000001396")
        add_danger_seed(conn, "DangerCo", "INE0000001397")
        add_ongoing_seed(conn, "AlphaOngoing", "INE0000001398")
    html = client.get("/").get_data(as_text=True)
    rows = chart_rows(html)
    assert [company for _status, company in rows] == [
        "DangerCo",
        "AlphaOngoing",
        "BetaOngoing",
        "DoneCo",
    ]
    danger_subset = [company for status, company in rows if status == "danger"]
    ongoing_subset = [company for status, company in rows if status == "ongoing"]
    matured_subset = [company for status, company in rows if status == "matured"]
    assert danger_subset == ["DangerCo"]
    assert ongoing_subset == ["AlphaOngoing", "BetaOngoing"]
    assert matured_subset == ["DoneCo"]
    app_js = client.get("/static/app.js").get_data(as_text=True)
    assert "appendChild" not in app_js
    assert "row.hidden = filter" in app_js


def test_tc139_134_email_presets_and_setup_guide_markup(client, db_path):
    html = client.get("/settings").get_data(as_text=True)
    assert 'id="s-provider"' in html
    assert ">Gmail</option>" in html
    assert ">Outlook / Microsoft 365</option>" in html
    assert ">Custom</option>" in html
    assert 'id="s-host" name="smtp_host"' in html
    assert 'id="s-port" name="smtp_port"' in html
    assert 'id="s-security" name="smtp_security"' in html
    assert 'id="email-setup-guide"' in html
    for guide_item in (
        "Gmail: enable 2-Verification on your Google account.",
        "Create an App Password at myaccount.google.com",
        "Paste the 16-char app password into the SMTP password field — NOT your login password.",
        "Outlook / Microsoft 365 personal accounts use the same app-password concept.",
    ):
        assert guide_item in html
    for trouble_item in (
        "Wrong port — use 587 with TLS/STARTTLS, or 465 with SSL.",
        "TLS required — most providers refuse plain connections.",
        "Check the spam folder — test emails often land there.",
    ):
        assert trouble_item in html
    assert 'id="s-send-test"' in html
    assert 'id="email-test-banner" class="test-banner" hidden' in html
    app_js = client.get("/static/app.js").get_data(as_text=True)
    assert "smtp.gmail.com" in app_js
    assert "smtp.office365.com" in app_js
    assert "gmail: { host: 'smtp.gmail.com', port: '587', security: 'TLS' }" in app_js
    assert "outlook: { host: 'smtp.office365.com', port: '587', security: 'STARTTLS' }" in app_js
    assert "custom: { host: '', port: '', security: '' }" in app_js


def test_tc139_134_email_test_route_success_and_failure(client, db_path, monkeypatch):
    calls = []

    def fake_send(event, conn=None):
        calls.append(event)
        return {"status": "sent"}

    monkeypatch.setattr("src.views.settings.send_alert_email", fake_send)
    response = client.post(
        "/settings/email/test",
        data={"smtp_host": "smtp.gmail.com", "smtp_port": "587", "smtp_security": "TLS"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "success"
    assert payload["message"] == "Test email sent. Check the inbox (and the spam folder)."
    assert len(calls) == 1
    assert "password" not in response.get_data(as_text=True).lower()
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM alert_prefs WHERE key = 'email_test_last_status'"
        ).fetchone()
    assert row is not None and row["value"] == "success"

    failure = client.post("/settings/email/test", data={"smtp_host": ""})
    assert failure.status_code == 200
    failure_payload = failure.get_json()
    assert failure_payload["status"] == "failure"
    assert failure_payload["message"] == (
        "Sending failed. Authentication failed = usually needs an App Password. "
        "Also check SMTP host, port and security setting."
    )
    assert len(calls) == 1
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT value FROM alert_prefs WHERE key = 'email_test_last_status'"
        ).fetchone()
    assert row["value"] == "failure"


def test_tc139_134_email_test_route_never_500s_on_send_error(client, db_path, monkeypatch):
    def failing_send(event, conn=None):
        raise AppError("ERR-smtp-unconfigured", "SMTP_USER is not set")

    monkeypatch.setattr("src.views.settings.send_alert_email", failing_send)
    response = client.post(
        "/settings/email/test",
        data={"smtp_host": "smtp.office365.com", "smtp_port": "587", "smtp_security": "STARTTLS"},
    )
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["status"] == "failure"
    assert payload["detail"] == "ERR-smtp-unconfigured"
    assert "SMTP_USER" not in payload["message"]


def test_tc139_135_returns_history_math_and_received_equality(client, db_path, monkeypatch):
    monkeypatch.setattr("src.views.dashboard.date", make_sim_date(SIM_TODAY))
    monkeypatch.setattr("src.queries.date", make_sim_date(SIM_TODAY))
    with get_conn(db_path) as conn:
        bond_a = add_bond(conn, "AlphaCo", "INE0000001399", "2026-08-01", 6, credit_day=5)
        bond_b = add_bond(conn, "BetaCo", "INE00000013A1", "2026-09-01", 5, credit_day=5)
        add_payment(conn, bond_a, "2026-08", 1000.0)
        add_payment(conn, bond_a, "2026-09", 1500.0)
        add_payment(conn, bond_a, "2026-10", 2000.0)
        add_payment(conn, bond_a, "2026-11", 500.0)
        add_payment(conn, bond_b, "2026-09", 800.0)
        add_payment(conn, bond_b, "2026-10", 700.0)
    html = client.get("/").get_data(as_text=True)
    assert "Nov-2026" in html
    assert "Dec-2026" not in html
    assert "2026-12" not in html
    rows = returns_table_rows(html)
    assert [row[0].replace(" Current", "") for row in rows] == [
        "Nov-2026",
        "Oct-2026",
        "Sep-2026",
        "Aug-2026",
    ]
    assert rows[0][0].endswith("Current")
    assert 'class="current-month-row"' in html
    assert [row[1] for row in rows] == [
        "&#8377;500.00",
        "&#8377;2700.00",
        "&#8377;2300.00",
        "&#8377;1000.00",
    ]
    assert [row[2] for row in rows] == ["1 &#183; 1", "2 &#183; 0", "2 &#183; 0", "1 &#183; 0"]
    assert [row[3] for row in rows] == [
        "&#8377;6500.00",
        "&#8377;6000.00",
        "&#8377;3300.00",
        "&#8377;1000.00",
    ]
    received_match = re.search(r'id="received-total" data-amount="([0-9.]+)"', html)
    assert received_match is not None
    assert received_match.group(1) == "6500.00"
    assert rows[0][3] == "&#8377;6500.00"
    assert "(of 2 active)" in html


def test_tc139_135_goals_kpi_link_navigates_view_and_tab(client, db_path, monkeypatch):
    monkeypatch.setattr("src.views.dashboard.date", make_sim_date(SIM_TODAY))
    monkeypatch.setattr("src.views.goals.date", make_sim_date(SIM_TODAY))
    monkeypatch.setattr("src.queries.date", make_sim_date(SIM_TODAY))
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "KpiCo", "INE00000013A2", "2026-10-01", 6, credit_day=5)
        add_payment(conn, bond_id, "2026-10", 400.0)
        add_payment(conn, bond_id, "2026-11", 600.0)
    goals_html = client.get("/goals").get_data(as_text=True)
    assert 'id="goals-kpi-strip"' in goals_html
    assert ">Earned this month<" in goals_html
    assert ">Total received<" in goals_html
    assert 'id="earned-this-month" data-amount="600.00"' in goals_html
    assert 'id="total-received-kpi" data-amount="1000.00"' in goals_html
    assert goals_html.count('href="/#returns"') == 2
    assert "View full returns history on Dashboard" in goals_html
    dashboard_html = client.get("/").get_data(as_text=True)
    assert 'id="dpanel-returns"' in dashboard_html
    assert 'id="returns"' in dashboard_html
    app_js = client.get("/static/app.js").get_data(as_text=True)
    assert "window.location.hash === '#returns'" in app_js
    assert "activateDashboardTab('returns')" in app_js
    assert "window.location.replace('/#returns')" in app_js


def test_tc139_136_credit_day_31_accepted_on_current_schema(client, db_path):
    with get_conn(db_path) as conn:
        schema = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'bonds'"
        ).fetchone()["sql"]
    assert re.search(r"credit_day\s*<=\s*31", schema)
    with get_conn(db_path) as conn:
        before = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
    create_ok = client.post(
        "/watch",
        data={
            "company": "ThirtyOneCo",
            "isin": "INE9000A0131",
            "rating": "AA",
            "coupon_pct": "9.5",
            "expected_yield_pct": "10.5",
        },
    )
    assert create_ok.status_code == 302
    create_bad = client.post(
        "/watch",
        data={
            "company": "BadDayCo",
            "isin": "INE9000A0132",
            "rating": "AA",
            "coupon_pct": "9.5",
            "expected_yield_pct": "10.5",
        },
    )
    assert create_bad.status_code == 302
    with get_conn(db_path) as conn:
        ok_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0131'"
        ).fetchone()["id"]
        bad_id = conn.execute(
            "SELECT id FROM bonds WHERE isin = 'INE9000A0132'"
        ).fetchone()["id"]
    ok = client.post(
        f"/watch/{ok_id}/move",
        data={
            "purchase_date": "2026-11-01",
            "start_date": "2026-11-01",
            "end_date": "2027-04-01",
            "credit_day": "31",
            "qty": "10",
            "amount": "25000",
            "broker": "Zerodha",
        },
    )
    assert ok.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT credit_day FROM bonds WHERE isin = 'INE9000A0131'"
        ).fetchone()
    assert row is not None and row["credit_day"] == 31
    for bad in ("0", "32"):
        response = client.post(
            f"/watch/{bad_id}/move",
            data={
                "purchase_date": "2026-11-01",
                "start_date": "2026-11-01",
                "end_date": "2027-04-01",
                "credit_day": bad,
                "qty": "10",
                "amount": "25000",
                "broker": "Zerodha",
            },
        )
        assert response.status_code == 400
    with get_conn(db_path) as conn:
        after = conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"]
        bad_row = conn.execute(
            "SELECT credit_day, watch_state FROM bonds WHERE id = ?", (bad_id,)
        ).fetchone()
    assert after == before + 2
    assert bad_row["credit_day"] is None
    assert bad_row["watch_state"] == "watching"


def test_tc139_136_legacy_check_migrates_in_place(tmp_path):
    legacy_path = tmp_path / "legacy_bonds.db"
    conn = sqlite3.connect(str(legacy_path))
    conn.execute(
        "CREATE TABLE bonds ("
        "id INTEGER PRIMARY KEY, company TEXT, isin TEXT UNIQUE, name TEXT, "
        "amount REAL, maturity REAL, start_date TEXT, end_date TEXT, tenure_months INTEGER, "
        "credit_day INTEGER CHECK (credit_day >= 1 AND credit_day <= 28), "
        "status TEXT DEFAULT 'On-going', created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
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
    conn.execute("CREATE TABLE share_config (id INTEGER PRIMARY KEY, section TEXT, included INTEGER DEFAULT 0)")
    conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
        "VALUES ('LegacyA', 'INE00000013A5', 'LegacyA', 100000.0, '2026-01-01', '2026-12-01', 11, 5)"
    )
    conn.execute(
        "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
        "VALUES ('LegacyB', 'INE00000013A6', 'LegacyB', 200000.0, '2026-02-01', '2027-01-01', 11, 28)"
    )
    conn.commit()
    conn.close()
    init_db(legacy_path)
    migrated = sqlite3.connect(str(legacy_path))
    migrated.row_factory = sqlite3.Row
    schema = migrated.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'bonds'"
    ).fetchone()["sql"]
    assert re.search(r"credit_day\s*<=\s*31", schema)
    assert not re.search(r"credit_day\s*<=\s*28\b", schema)
    rows = migrated.execute("SELECT company, credit_day FROM bonds ORDER BY id").fetchall()
    assert [row["company"] for row in rows] == ["LegacyA", "LegacyB"]
    assert [row["credit_day"] for row in rows] == [5, 28]
    migrated.execute(
        "INSERT INTO bonds (company, isin, name, amount, start_date, end_date, tenure_months, credit_day) "
        "VALUES ('MigratedC', 'INE00000013A7', 'MigratedC', 300000.0, '2026-03-01', '2027-02-01', 11, 31)"
    )
    migrated.commit()
    row = migrated.execute(
        "SELECT credit_day FROM bonds WHERE isin = 'INE00000013A7'"
    ).fetchone()
    assert row["credit_day"] == 31
    migrated.close()
    assert Path(legacy_path).exists()
