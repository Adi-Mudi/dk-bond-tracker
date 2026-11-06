import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from src.app import create_app
from src.db import get_conn

ROOT = Path(__file__).resolve().parents[1]
APP_JS = ROOT / "src" / "static" / "app.js"

CANDIDATE_ISIN = "INE9000A0800"


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def candidate_form(**overrides):
    data = {
        "company": "Perbond Ltd",
        "isin": CANDIDATE_ISIN,
        "rating": "AA",
        "coupon_pct": "8.0",
        "expected_yield_pct": "8.5",
        "broker": "Zerodha",
        "watch_investment": "200000",
        "qty": "200",
    }
    data.update(overrides)
    return data


def move_payload(**overrides):
    data = {
        "purchase_date": "2026-08-01",
        "start_date": "2026-08-01",
        "end_date": "2028-08-01",
        "credit_day": "5",
        "qty": "200",
        "amount": "200000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def candidate_id(db_path):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (CANDIDATE_ISIN,)
        ).fetchone()["id"]


def move_panel(html, bond_id):
    match = re.search(
        r'<tr class="move-row" id="move-panel-' + str(bond_id) + r'" hidden>(.*?)</tr>',
        html,
        re.S,
    )
    assert match, "move panel must render as a hidden row"
    return match.group(1)


def per_bond_function_source():
    source = APP_JS.read_text(encoding="utf-8")
    start = source.index("function perBond")
    brace = source.index("{", start)
    depth = 0
    for index in range(brace, len(source)):
        char = source[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    raise AssertionError("perBond function braces do not balance")


def run_per_bond_cases(cases):
    script = (
        "var elements = {};\n"
        "var document = { getElementById: function (id) { return elements[id]; } };\n"
        + per_bond_function_source()
        + "\n"
        "function run(total, qty, seed) {\n"
        "  elements.t = { value: total };\n"
        "  elements.q = { value: qty };\n"
        "  elements.o = { value: seed };\n"
        "  perBond('t', 'q', 'o');\n"
        "  return elements.o.value;\n"
        "}\n"
        "var cases = " + json.dumps([[c[0], c[1], c[2]] for c in cases]) + ";\n"
        "var out = cases.map(function (c) { return run(c[0], c[1], c[2]); });\n"
        "console.log(JSON.stringify(out));\n"
    )
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


JS_CASES = [
    ("200000", "200", "STALE", "1000.00"),
    ("210000", "200", "1000.00", "1050.00"),
    ("", "200", "1000.00", ""),
    ("200000", "", "1000.00", ""),
    ("200000", "0", "1000.00", ""),
    ("200000", "abc", "1000.00", ""),
    ("abc", "200", "1000.00", ""),
    ("0", "200", "1000.00", "0.00"),
    ("-100", "200", "1000.00", ""),
    ("200000", "-5", "1000.00", ""),
    ("100", "3", "STALE", "33.33"),
]


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime not available")
def test_fr80_ac1_ac2_ac3_per_bond_js_derives_recomputes_and_clears():
    results = run_per_bond_cases(JS_CASES)
    assert results == [case[3] for case in JS_CASES]


@pytest.mark.skipif(shutil.which("node") is None, reason="node runtime not available")
def test_fr80_ac1_ac2_ac3_per_bond_js_clears_stale_value_on_invalid_input():
    seed = "1000.00"
    for total, qty in [("", "200"), ("200000", ""), ("200000", "0"), ("200000", "abc")]:
        assert run_per_bond_cases([(total, qty, seed)]) == [""]
    assert run_per_bond_cases([("200000", "200", "")]) == ["1000.00"]


def test_fr80_app_js_exposes_guarded_per_bond_helper(client, db_path):
    source = APP_JS.read_text(encoding="utf-8")
    assert "function perBond(totalId, qtyId, outId)" in source
    assert "window.perBond = perBond" in source
    assert "qty > 0 && total >= 0" in source
    assert ".toFixed(2)" in source
    served = client.get("/static/app.js").get_data(as_text=True)
    assert "function perBond" in served


def test_fr80_candidate_form_has_readonly_per_bond_output(client, db_path):
    html = client.get("/watch").get_data(as_text=True)
    tag = re.search(r'<input[^>]*id="c-perbond"[^>]*>', html)
    assert tag, "Add Candidate form must carry a per-bond price output"
    markup = tag.group(0)
    assert "readonly" in markup
    assert "required" not in markup
    assert 'name="' not in markup


def test_fr80_candidate_form_wires_per_bond_oninput(client, db_path):
    html = client.get("/watch").get_data(as_text=True)
    wiring = "perBond('c-invested','c-qty','c-perbond')"
    invested = re.search(r'<input[^>]*id="c-invested"[^>]*>', html).group(0)
    qty = re.search(r'<input[^>]*id="c-qty"[^>]*>', html).group(0)
    assert wiring in invested
    assert wiring in qty


def test_fr80_move_panel_has_readonly_per_bond_output_and_wiring(client, db_path):
    client.post("/watch", data=candidate_form(qty="200"))
    bond_id = candidate_id(db_path)
    panel = move_panel(client.get("/watch").get_data(as_text=True), bond_id)
    out = re.search(r'<input[^>]*id="move-perbond-' + str(bond_id) + r'"[^>]*>', panel)
    assert out, "move panel must carry a per-bond price output"
    assert "readonly" in out.group(0)
    assert "required" not in out.group(0)
    assert 'name="' not in out.group(0)
    wiring = "perBond('move-amount-%d','move-qty-%d','move-perbond-%d')" % (
        bond_id,
        bond_id,
        bond_id,
    )
    amount = re.search(
        r'<input[^>]*id="move-amount-' + str(bond_id) + r'"[^>]*>', panel
    ).group(0)
    qty = re.search(
        r'<input[^>]*id="move-qty-' + str(bond_id) + r'"[^>]*>', panel
    ).group(0)
    assert wiring in amount
    assert wiring in qty


def test_fr80_ac4_no_per_bond_column_on_any_table(db_path):
    with get_conn(db_path) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        for table in tables:
            columns = [info[1] for info in conn.execute(f"PRAGMA table_info({table})")]
            assert not [
                column
                for column in columns
                if "per" in column.lower() and "bond" in column.lower()
            ], f"{table} must not persist a per-bond price"
        schema_sql = " ".join(
            (row[0] or "") for row in conn.execute("SELECT sql FROM sqlite_master")
        )
    compact = re.sub(r"[\s_]", "", schema_sql).lower()
    assert "perbond" not in compact


def test_fr80_ac4_move_payload_ignores_per_bond_field(client, db_path):
    client.post("/watch", data=candidate_form())
    bond_id = candidate_id(db_path)
    response = client.post(
        f"/watch/{bond_id}/move",
        data=move_payload(per_bond_price="1000.00", per_bond="1000.00"),
    )
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT watch_state, amount, qty FROM bonds WHERE id = ?", (bond_id,)
        ).fetchone()
    assert row["watch_state"] == "holding"
    assert row["amount"] == 200000.0
    assert row["qty"] == 200


def test_fr80_ac4_add_candidate_ignores_per_bond_field(client, db_path):
    response = client.post("/watch", data=candidate_form(per_bond_price="1000.00"))
    assert response.status_code == 302
    with get_conn(db_path) as conn:
        row = conn.execute(
            "SELECT qty, watch_investment FROM bonds WHERE isin = ?", (CANDIDATE_ISIN,)
        ).fetchone()
    assert row["qty"] == 200
    assert row["watch_investment"] == 200000.0
