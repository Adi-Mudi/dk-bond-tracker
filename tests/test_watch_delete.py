import html.parser
import json

import pytest

from src.app import create_app
from src.db import get_conn


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def seed_candidate(conn, company, isin, watch_state="watching"):
    cursor = conn.execute(
        "INSERT INTO bonds (company, isin, name, watch_state) VALUES (?, ?, ?, ?)",
        (company, isin, company, watch_state),
    )
    return cursor.lastrowid


def count(conn, sql, params=()):
    return conn.execute(sql, params).fetchone()["n"]


def seed_ledger(conn, bond_id, months=("2026-01", "2026-02")):
    for month in months:
        conn.execute(
            "INSERT INTO payment_ledger (bond_id, month, amount, paid) VALUES (?, ?, ?, ?)",
            (bond_id, month, 1000.0, 0),
        )


def test_fr76_ac1_delete_removes_candidate_from_every_surface(client, db_path):
    with get_conn(db_path) as conn:
        seed_candidate(conn, "Alpha Steel", "INE000000076A")
        removed_id = seed_candidate(conn, "Beta Cement", "INE000000076B")
        seed_candidate(conn, "Gamma Alloys", "INE000000076C")

    response = client.post(f"/watch/{removed_id}/delete")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/watch")

    with get_conn(db_path) as conn:
        assert count(conn, "SELECT COUNT(*) AS n FROM bonds WHERE watch_state = 'watching'") == 2
        assert count(conn, "SELECT COUNT(*) AS n FROM bonds WHERE id = ?", (removed_id,)) == 0

    flash_page = client.get("/watch").get_data(as_text=True)
    assert "Candidate deleted: Beta Cement" in flash_page

    watch = client.get("/watch").get_data(as_text=True)
    assert "Beta Cement" not in watch
    assert "Alpha Steel" in watch
    assert "Gamma Alloys" in watch

    grid = client.get("/grid").get_data(as_text=True)
    dashboard = client.get("/").get_data(as_text=True)
    assert "Beta Cement" not in grid
    assert "Beta Cement" not in dashboard


def test_fr76_ac1_row_delete_control_rendered_per_candidate(client, db_path):
    with get_conn(db_path) as conn:
        first = seed_candidate(conn, "Alpha Steel", "INE000000076A")
        second = seed_candidate(conn, "Beta Cement", "INE000000076B")

    html = client.get("/watch").get_data(as_text=True)
    for bond_id in (first, second):
        assert f'action="/watch/{bond_id}/delete"' in html
        assert f'id="delete-candidate-{bond_id}"' in html


def test_fr76_ac2_confirm_dialog_present_and_no_write_without_post(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = seed_candidate(conn, "Alpha Steel", "INE000000076A")

    html = client.get("/watch").get_data(as_text=True)
    assert "return confirm(" in html
    assert "Delete candidate Alpha Steel? This cannot be undone." in html

    with get_conn(db_path) as conn:
        assert count(conn, "SELECT COUNT(*) AS n FROM bonds WHERE id = ?", (bond_id,)) == 1


def test_fr76_ac3_holding_cannot_be_deleted(client, db_path):
    with get_conn(db_path) as conn:
        holding_id = seed_candidate(conn, "Held Corp", "INE000000076H", watch_state="holding")
        seed_ledger(conn, holding_id)

    response = client.post(f"/watch/{holding_id}/delete")
    assert response.status_code == 409
    body = response.get_data(as_text=True)
    assert "ERR-watch-delete" in body
    assert "never deleted" in body

    with get_conn(db_path) as conn:
        assert count(conn, "SELECT COUNT(*) AS n FROM bonds WHERE id = ?", (holding_id,)) == 1
        assert count(conn, "SELECT COUNT(*) AS n FROM payment_ledger WHERE bond_id = ?", (holding_id,)) == 2


def test_fr76_ac4_delete_cascades_ledger_rows(client, db_path):
    with get_conn(db_path) as conn:
        bond_id = seed_candidate(conn, "Alpha Steel", "INE000000076A")
        seed_ledger(conn, bond_id, months=("2026-01", "2026-02", "2026-03"))

    response = client.post(f"/watch/{bond_id}/delete")
    assert response.status_code == 302

    with get_conn(db_path) as conn:
        assert count(conn, "SELECT COUNT(*) AS n FROM bonds WHERE id = ?", (bond_id,)) == 0
        assert count(conn, "SELECT COUNT(*) AS n FROM payment_ledger WHERE bond_id = ?", (bond_id,)) == 0


def test_fr76_unknown_candidate_delete_returns_404(client, db_path):
    response = client.post("/watch/424242/delete")
    assert response.status_code == 404
    body = response.get_data(as_text=True)
    assert "ERR-watch-delete" in body
    assert "not found" in body


class _DeleteFormAttrs(html.parser.HTMLParser):
    def __init__(self, form_id):
        super().__init__(convert_charrefs=True)
        self._form_id = form_id
        self.attrs = {}

    def handle_starttag(self, tag, attrs):
        if tag == "form":
            attributes = dict(attrs)
            if attributes.get("id") == self._form_id:
                self.attrs = attributes


def render_delete_form(client, db_path, company, isin):
    with get_conn(db_path) as conn:
        bond_id = seed_candidate(conn, company, isin)

    page = client.get("/watch").get_data(as_text=True)
    reader = _DeleteFormAttrs(f"delete-form-{bond_id}")
    reader.feed(page)
    return page, reader.attrs


def test_fr76_ac2_confirm_message_survives_apostrophe(client, db_path):
    company = "D'Mello Finance"
    page, attrs = render_delete_form(client, db_path, company, "INE000000076A")

    handler = attrs["onsubmit"]
    assert "return confirm(" in handler
    assert company not in handler
    assert json.loads(attrs["data-confirm-message"]) == (
        f"Delete candidate {company}? This cannot be undone."
    )
    assert "confirm('Delete candidate" not in page


def test_fr76_ac2_confirm_message_survives_backslash(client, db_path):
    company = "Back\\slash Investments"
    page, attrs = render_delete_form(client, db_path, company, "INE000000076A")

    handler = attrs["onsubmit"]
    assert "return confirm(" in handler
    assert company not in handler
    assert json.loads(attrs["data-confirm-message"]) == (
        f"Delete candidate {company}? This cannot be undone."
    )
    assert "confirm('Delete candidate" not in page


def test_fr76_ac2_delete_route_is_post_only(client):
    assert client.get("/watch/1/delete").status_code == 405
