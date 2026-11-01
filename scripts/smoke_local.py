import sys
import tempfile
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.app import create_app
from src.db import init_db
from src.validators import add_months

results = []


def check(name, ok, detail=""):
    results.append((name, "PASS" if ok else "FAIL", detail))
    print(f"{'PASS' if ok else 'FAIL'} | {name}" + (f" | {detail}" if detail else ""))


with tempfile.TemporaryDirectory() as tmp:
    db = Path(tmp) / "smoke.db"
    init_db(db)
    app = create_app(str(db))
    c = app.test_client()

    for route in ["/", "/grid", "/add", "/goals", "/watch", "/notifications",
                  "/share", "/print", "/portfolio", "/settings"]:
        r = c.get(route)
        check(f"GET {route}", r.status_code == 200, f"status={r.status_code}")

    home = c.get("/").get_data(as_text=True)
    check("empty-state: no sample rows on dashboard",
          "SATIN" not in home and "Muthoottu" not in home and "Paisalo" not in home)

    r = c.post("/watch", data={
        "company": "SMOKE TEST LTD",
        "isin": "INE000000001",
        "rating": "AA",
        "coupon_pct": "9.50",
        "expected_yield_pct": "10.10",
        "broker": "SmokeBroker",
        "source_note": "smoke cycle",
    })
    check("POST /watch add candidate", r.status_code in (302, 200), f"status={r.status_code}")
    watch_html = c.get("/watch").get_data(as_text=True)
    check("watchlist shows candidate", "SMOKE TEST LTD" in watch_html)
    check("watchlist shows broker", "SmokeBroker" in watch_html)

    import sqlite3
    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        cid = conn.execute("SELECT id FROM bonds WHERE isin='INE000000001'").fetchone()["id"]

    start = date.today().replace(day=1)
    end = add_months(start, 6)
    r = c.post(f"/watch/{cid}/move", data={
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "credit_day": "5",
        "broker": "SmokeBroker",
    })
    check("POST /watch/move to portfolio", r.status_code in (302, 200), f"status={r.status_code}")
    port_html = c.get("/portfolio").get_data(as_text=True)
    check("portfolio shows holding", "SMOKE TEST LTD" in port_html)

    with sqlite3.connect(db) as conn:
        conn.row_factory = sqlite3.Row
        bid = conn.execute("SELECT id FROM bonds WHERE isin='INE000000001'").fetchone()["id"]
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='payment_ledger'").fetchone():
            months = [row["month"] for row in conn.execute(
                "SELECT DISTINCT month FROM payment_ledger WHERE bond_id=?", (bid,))]
        else:
            months = []

    if months:
        m = months[0]
    else:
        from src.status import month_key
        m = month_key(date.today())
    r = c.post(f"/payment/{bid}/{m}", data={"amount": "1000.00", "paid": "on"})
    check(f"POST /payment {m}", r.status_code in (302, 200), f"status={r.status_code}")

    r = c.get(f"/portfolio/{bid}/detail")
    check("GET /portfolio/<id>/detail JSON", r.status_code == 200, f"status={r.status_code}")

    r = c.get("/export.csv?scope=full")
    check("GET /export.csv?scope=full", r.status_code == 200, f"status={r.status_code}")
    r = c.get("/export.csv")
    check("GET /export.csv bare -> 400 validation", r.status_code == 400, f"status={r.status_code}")
    r = c.get(f"/payout?bond_id={bid}&cycle=monthly")
    check(f"GET /payout?bond_id={bid}&cycle=monthly", r.status_code == 200, f"status={r.status_code}")
    r = c.get(f"/payout?bond_id={bid}")
    check(f"GET /payout?bond_id={bid} (no cycle, fallback)", r.status_code == 200, f"status={r.status_code}")
    r = c.get("/payout")
    check("GET /payout bare -> 400 validation", r.status_code == 400, f"status={r.status_code}")

    r = c.post("/settings", data={
        "smtp_host": "smtp.gmail.com", "smtp_port": "587",
        "smtp_from": "me@example.com", "smtp_to": "me@example.com",
    })
    check("POST /settings email config", r.status_code in (302, 200), f"status={r.status_code}")

    r = c.post("/settings/email/test")
    check("POST /settings/email/test never 500", r.status_code != 500, f"status={r.status_code}")

    r = c.post("/goals", data={
        "name": "Smoke Goal", "target_amount": "50000",
        "target_end_date": "2029-12-01", "saved_amount": "0", "note": "smoke",
    })
    check("POST /goals add", r.status_code in (302, 200), f"status={r.status_code}")
    goals_html = c.get("/goals").get_data(as_text=True)
    check("goals shows new goal", "Smoke Goal" in goals_html)

    r = c.post("/notifications/read_all")
    check("POST /notifications/read_all", r.status_code in (302, 200), f"status={r.status_code}")

fails = [x for x in results if x[1] == "FAIL"]
print(f"\nSMOKE TOTAL: {len(results)} checks, {len(results)-len(fails)} PASS, {len(fails)} FAIL")
sys.exit(1 if fails else 0)
