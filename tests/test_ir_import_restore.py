import io
from datetime import date

import pytest

from src.app import create_app
from src.db import get_conn, init_db
from src.import_csv import import_backup_csv
from src.validators import AppError
from tests.conftest import add_bond, add_payment


def seed(db_path):
    init_db(db_path)
    with get_conn(db_path) as conn:
        bond_id = add_bond(conn, "Alpha Corp", "INE000000001", date(2025, 1, 1), 12, credit_day=5)
        add_bond(conn, "Beta Ltd", "INE000000002", date(2025, 3, 1), 24, credit_day=10, amount=250000.0)
        add_payment(conn, bond_id, "2025-02", 1000.0)
        add_payment(conn, bond_id, "2025-03", 1000.0, paid=0)
        conn.execute(
            "INSERT INTO financial_goals (name, target_amount, target_end_date, note, saved_amount) "
            "VALUES ('Car', 500000.0, '2027-01-01', 'first goal', 1200.0)"
        )


def empty_db(tmp_path, name):
    path = tmp_path / name
    init_db(path)
    return path


def backup_text(db_path):
    client = create_app(str(db_path)).test_client()
    response = client.get("/export.csv?scope=backup")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def row_count(db_path):
    with get_conn(db_path) as conn:
        return {
            table: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            for table in ("bonds", "payment_ledger", "financial_goals")
        }


def test_round_trip_backup_import_backup_is_equal(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    text = backup_text(source)
    target = empty_db(tmp_path, "target.db")
    with get_conn(target) as conn:
        counts = import_backup_csv(conn, text)
    assert counts == {"bonds": 2, "payments": 2, "goals": 1}
    assert backup_text(target) == text


def test_unknown_extra_column_is_rejected_by_name(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    text = backup_text(source).replace("isin,company,name", "isin,company,extra_col,name", 1)
    target = empty_db(tmp_path, "target.db")
    with get_conn(target) as conn, pytest.raises(AppError) as info:
        import_backup_csv(conn, text)
    assert "extra_col" in info.value.message


def test_missing_required_column_is_rejected_by_name(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    text = backup_text(source).replace("isin,company,name,amount", "isin,company,name", 1)
    target = empty_db(tmp_path, "target.db")
    with get_conn(target) as conn, pytest.raises(AppError) as info:
        import_backup_csv(conn, text)
    assert "amount" in info.value.message


def test_broken_row_aborts_with_row_number_and_writes_nothing(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    lines = backup_text(source).splitlines(keepends=True)
    bond_row = next(i for i, line in enumerate(lines) if line.startswith("INE000000002"))
    lines[bond_row] = lines[bond_row].replace("250000.0", "not-a-number", 1)
    text = "".join(lines)
    target = empty_db(tmp_path, "target.db")
    with get_conn(target) as conn, pytest.raises(AppError) as info:
        import_backup_csv(conn, text)
    assert f"row {bond_row + 1}" in info.value.message
    assert row_count(target) == {"bonds": 0, "payment_ledger": 0, "financial_goals": 0}


def test_mid_write_failure_rolls_back_every_table(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    lines = backup_text(source).splitlines(keepends=True)
    payment_row = next(i for i, line in enumerate(lines) if line.startswith("INE000000001,2025-03"))
    lines.insert(payment_row + 1, lines[payment_row])
    text = "".join(lines)
    target = empty_db(tmp_path, "target.db")
    with get_conn(target) as conn, pytest.raises(AppError) as info:
        import_backup_csv(conn, text)
    assert info.value.code == "ERR-import-write"
    assert row_count(target) == {"bonds": 0, "payment_ledger": 0, "financial_goals": 0}


def test_importing_twice_is_refused_without_duplicates(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    text = backup_text(source)
    target = empty_db(tmp_path, "target.db")
    with get_conn(target) as conn:
        import_backup_csv(conn, text)
    before = row_count(target)
    with get_conn(target) as conn, pytest.raises(AppError) as info:
        import_backup_csv(conn, text)
    assert "already restored" in info.value.message
    assert row_count(target) == before


def test_settings_page_shows_import_form_and_warning(tmp_path):
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    app = create_app(str(db_path))
    html = app.test_client().get("/settings?section=data").get_data(as_text=True)
    assert 'action="/settings/import"' in html
    assert "restoring a backup adds its bonds" in html
    assert 'href="/export.csv?scope=backup"' in html


def test_post_import_valid_redirects_with_counts_and_invalid_is_named(tmp_path):
    source = tmp_path / "source.db"
    seed(source)
    text = backup_text(source)
    db_path = tmp_path / "bonds.db"
    init_db(db_path)
    app = create_app(str(db_path))
    client = app.test_client()

    ok = client.post(
        "/settings/import",
        data={"file": (io.BytesIO(text.encode("utf-8")), "backup.csv")},
        content_type="multipart/form-data",
    )
    assert ok.status_code == 302
    follow = client.get("/settings?section=data").get_data(as_text=True)
    assert "Restored 2 bonds, 2 payments, 1 goals" in follow

    bad = client.post(
        "/settings/import",
        data={"file": (io.BytesIO(b"not,a,backup\n1,2,3\n"), "bad.csv")},
        content_type="multipart/form-data",
    )
    assert bad.status_code == 400
    assert "ERR-import-format" in bad.get_data(as_text=True)


def test_backup_export_route_scope(tmp_path):
    db_path = tmp_path / "bonds.db"
    seed(db_path)
    app = create_app(str(db_path))
    response = app.test_client().get("/export.csv?scope=backup")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.startswith("section,bonds\r\n")
    assert "start_date" in body and "credit_day" in body
