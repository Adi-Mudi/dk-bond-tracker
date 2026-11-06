import ast
import re
import sqlite3
from pathlib import Path

import pytest

from conftest import add_bond
from src.app import create_app
from src.db import get_conn

SRC_DIR = Path(__file__).resolve().parents[1] / "src"

HOLDING_WRITE = re.compile(
    r"UPDATE\s+bonds\s+SET\b(?:(?!\bWHERE\b)[\s\S])*?watch_state\s*=\s*'holding'",
    re.IGNORECASE,
)
WATCHING_WRITE = re.compile(
    r"UPDATE\s+bonds\s+SET\b(?:(?!\bWHERE\b)[\s\S])*?watch_state\s*=\s*'watching'",
    re.IGNORECASE,
)
INSERT_BONDS = re.compile(
    r"INSERT\s+INTO\s+bonds\s*\(([^)]*)\)\s*VALUES\s*\(([^)]*)\)",
    re.IGNORECASE | re.DOTALL,
)

SURFACES = ("/", "/grid", "/portfolio", "/print", "/share", "/export.csv?scope=full")

FORBIDDEN_CONTROLS = (
    'action="/add"',
    'href="/add"',
    'id="add-candidate-form"',
    'id="add-candidate-submit"',
    "add-position",
    "add_position",
)

ADD_LIKE_FORM = {
    "company": "Sneaky Co",
    "isin": "INE9000A0681",
    "amount": "1000",
    "start_date": "2026-11-01",
    "end_date": "2027-11-01",
    "credit_day": "5",
}


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def _ordered_strings(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = []

    def visit(node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.append(node.value)
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(tree)
    return out


def strings_by_module():
    return {
        path.name: "\n".join(_ordered_strings(path))
        for path in sorted(SRC_DIR.glob("*.py"))
    }


def matches_by_module(pattern, modules):
    found = {}
    for name, text in modules.items():
        count = len(pattern.findall(text))
        if count:
            found[name] = count
    return found


def make_candidate(client, db_path, company="Alpha Ltd", isin="INE9000A0300", **overrides):
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
        return conn.execute(
            "SELECT id FROM bonds WHERE isin = ?", (isin.upper(),)
        ).fetchone()["id"]


def valid_move(**overrides):
    data = {
        "purchase_date": "2026-08-01",
        "start_date": "2026-08-01",
        "end_date": "2028-08-01",
        "credit_day": "5",
        "qty": "100",
        "amount": "100000",
        "broker": "Zerodha",
    }
    data.update(overrides)
    return data


def row_state(db_path, bond_id):
    with get_conn(db_path) as conn:
        return conn.execute(
            "SELECT watch_state FROM bonds WHERE id = ?", (bond_id,)
        ).fetchone()["watch_state"]


def companies_rows(db_path, company):
    with get_conn(db_path) as conn:
        return [
            dict(row)
            for row in conn.execute(
                "SELECT id, watch_state FROM bonds WHERE company = ?", (company,)
            ).fetchall()
        ]


def test_fr82_ac1_exactly_one_holding_write_site_in_source():
    modules = strings_by_module()
    holding_sites = matches_by_module(HOLDING_WRITE, modules)
    assert holding_sites == {"app.py": 1}, (
        "FR-82: expected exactly one write site setting watch_state='holding' "
        f"(the watch move handler in src/app.py); found {holding_sites}"
    )
    assert matches_by_module(WATCHING_WRITE, modules) == {}, (
        "FR-82: no UPDATE may set watch_state='watching'; candidates are born watching"
    )


def test_fr82_ac1_candidate_insert_always_names_watch_state_watching():
    modules = strings_by_module()
    inserts = []
    for name, text in modules.items():
        for columns, values in INSERT_BONDS.findall(text):
            inserts.append((name, columns, values))
    assert len(inserts) == 1, (
        "FR-82: expected exactly one INSERT INTO bonds statement; "
        f"found {len(inserts)} ({[name for name, _c, _v in inserts]})"
    )
    name, columns, values = inserts[0]
    assert name == "app.py"
    column_list = [column.strip().lower() for column in columns.split(",")]
    assert "watch_state" in column_list, (
        "FR-82: candidate INSERT must name watch_state explicitly (never rely on the "
        "DB default 'holding')"
    )
    value_list = [value.strip() for value in values.split(",")]
    assert value_list[column_list.index("watch_state")] == "'watching'", (
        "FR-82: candidate INSERT must write watch_state='watching' explicitly; "
        f"found {value_list[column_list.index('watch_state')]!r}"
    )


def test_fr82_ac1_candidate_adds_watching_then_move_flips_holding(client, db_path):
    candidate_id = make_candidate(client, db_path, company="Alpha Ltd", isin="INE9000A0301")
    assert row_state(db_path, candidate_id) == "watching"
    response = client.post(f"/watch/{candidate_id}/move", data=valid_move())
    assert response.status_code == 302
    assert row_state(db_path, candidate_id) == "holding"


def test_fr82_ac2_move_flips_in_place_without_creating_a_duplicate_row(client, db_path):
    company = "Beta Finance Ltd"
    candidate_id = make_candidate(client, db_path, company=company, isin="INE9000A0302")
    assert companies_rows(db_path, company) == [
        {"id": candidate_id, "watch_state": "watching"}
    ]
    response = client.post(f"/watch/{candidate_id}/move", data=valid_move())
    assert response.status_code == 302
    rows = companies_rows(db_path, company)
    assert len(rows) == 1
    assert rows[0]["id"] == candidate_id
    assert rows[0]["watch_state"] == "holding"


def test_fr82_ac3_no_surface_offers_a_create_position_control(client, db_path):
    with get_conn(db_path) as conn:
        add_bond(conn, "PlainCo", "INE0000000820", "2026-01-01", 12)
    for route in SURFACES:
        response = client.get(route)
        assert response.status_code == 200, route
        body = response.get_data(as_text=True)
        for marker in FORBIDDEN_CONTROLS:
            assert marker not in body, f"FR-82: {marker!r} leaked onto surface {route}"


def test_fr82_ac3_no_create_position_route_exists(client, db_path):
    assert client.get("/add").status_code == 404
    assert client.post("/add", data=ADD_LIKE_FORM).status_code == 404


def test_fr82_no_other_route_mutates_watch_state(client, db_path):
    candidate_id = make_candidate(client, db_path, company="Gamma Ltd", isin="INE9000A0303")
    before = companies_rows(db_path, "Gamma Ltd")
    attempts = (
        ("/", ADD_LIKE_FORM),
        ("/grid", ADD_LIKE_FORM),
        ("/portfolio", ADD_LIKE_FORM),
        ("/export.csv?scope=full", ADD_LIKE_FORM),
    )
    for route, payload in attempts:
        client.post(route, data=payload)
        assert row_state(db_path, candidate_id) == "watching", route
    assert companies_rows(db_path, "Gamma Ltd") == before


def test_fr82_schema_check_constraint_rejects_unknown_watch_state(db_path):
    with pytest.raises(sqlite3.IntegrityError):
        with get_conn(db_path) as conn:
            conn.execute(
                "INSERT INTO bonds (company, isin, watch_state) VALUES (?, ?, ?)",
                ("Bogus Co", "INE0000000821", "bogus"),
            )
    with get_conn(db_path) as conn:
        assert conn.execute("SELECT COUNT(*) AS n FROM bonds").fetchone()["n"] == 0


def test_fr82_schema_check_constraint_accepts_both_states(db_path):
    with get_conn(db_path) as conn:
        conn.execute(
            "INSERT INTO bonds (company, isin, watch_state) VALUES (?, ?, ?)",
            ("Watch Co", "INE0000000823", "watching"),
        )
        conn.execute(
            "INSERT INTO bonds (company, isin, watch_state) VALUES (?, ?, ?)",
            ("Hold Co", "INE0000000824", "holding"),
        )
        states = [
            row["watch_state"]
            for row in conn.execute(
                "SELECT watch_state FROM bonds ORDER BY id"
            ).fetchall()
        ]
    assert states == ["watching", "holding"]
