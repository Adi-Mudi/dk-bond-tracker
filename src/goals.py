import sqlite3
from datetime import date

from .validators import AppError, parse_date_value


def months_until(end_date, today=None):
    if today is None:
        today = date.today()
    if isinstance(end_date, str):
        end_date = parse_date_value(end_date, "target_end_date")
    total = (end_date.year - today.year) * 12 + (end_date.month - today.month)
    if end_date.day < today.day:
        total -= 1
    return total


def _goal_amount(raw, field):
    text = str(raw or "").strip()
    if not text:
        return 0.0
    try:
        value = float(text.replace(",", "").replace("₹", ""))
    except ValueError:
        raise AppError("ERR-goals-op", f"{field} must be a number: {raw!r}") from None
    if value < 0:
        raise AppError("ERR-goals-op", f"{field} must not be negative: {raw!r}")
    return value


def _goal_date(raw):
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return parse_date_value(text, "target_end_date")
    except AppError as exc:
        raise AppError(
            "ERR-goals-op", f"target_end_date must be a date: {raw!r}"
        ) from exc


def _decorate(row, today):
    entry = dict(row)
    end_raw = entry.get("target_end_date")
    target = entry.get("target_amount")
    saved = entry.get("saved_amount") or 0.0
    entry["saved_amount"] = float(saved)
    entry["is_legacy"] = end_raw is None
    entry["months_remaining"] = None
    entry["progress_pct"] = None
    if end_raw is not None:
        end = parse_date_value(str(end_raw), "target_end_date")
        entry["months_remaining"] = months_until(end, today)
    if target is not None and float(target) > 0:
        entry["progress_pct"] = round(float(saved) / float(target) * 100.0, 1)
    return entry


def list_goals(conn, today=None):
    if today is None:
        today = date.today()
    try:
        rows = conn.execute(
            "SELECT id, name, target_amount, target_end_date, note, saved_amount "
            "FROM financial_goals ORDER BY target_end_date, id"
        ).fetchall()
    except Exception as exc:
        raise AppError("ERR-goals-op", f"list: goal query failed: {exc}") from exc
    return [_decorate(dict(row), today) for row in rows]


def add_goal(conn, name, target_amount, target_end_date, note="", saved_amount=None):
    clean_name = str(name or "").strip()
    if not clean_name:
        raise AppError("ERR-goals-op", "create: name is required")
    value = _goal_amount(target_amount, "target_amount")
    end = _goal_date(target_end_date)
    saved = _goal_amount(saved_amount, "saved_amount")
    clean_note = str(note or "").strip()
    try:
        cursor = conn.execute(
            "INSERT INTO financial_goals (name, target_amount, target_end_date, note, saved_amount) "
            "VALUES (?, ?, ?, ?, ?)",
            (clean_name, value, end.isoformat() if end else None, clean_note, saved),
        )
    except sqlite3.Error as exc:
        raise AppError("ERR-goals-op", f"create: goal insert failed: {exc}") from exc
    if cursor.rowcount != 1:
        raise AppError("ERR-goals-op", f"create: goal insert affected {cursor.rowcount} rows")
    return cursor.lastrowid


def _require_goal(conn, goal_id, operation):
    row = conn.execute("SELECT id FROM financial_goals WHERE id = ?", (goal_id,)).fetchone()
    if row is None:
        raise AppError("ERR-goals-op", f"{operation}: goal not found: {goal_id!r}")
    return row


def update_goal(conn, goal_id, name, target_amount, target_end_date, saved_amount=None):
    _require_goal(conn, goal_id, "update")
    clean_name = str(name or "").strip()
    if not clean_name:
        raise AppError("ERR-goals-op", "update: name is required")
    value = _goal_amount(target_amount, "target_amount")
    end = _goal_date(target_end_date)
    saved = None
    if saved_amount not in (None, ""):
        saved = _goal_amount(saved_amount, "saved_amount")
    try:
        if saved is None:
            cursor = conn.execute(
                "UPDATE financial_goals SET name = ?, target_amount = ?, target_end_date = ? "
                "WHERE id = ?",
                (clean_name, value, end.isoformat() if end else None, goal_id),
            )
        else:
            cursor = conn.execute(
                "UPDATE financial_goals SET name = ?, target_amount = ?, target_end_date = ?, "
                "saved_amount = ? WHERE id = ?",
                (clean_name, value, end.isoformat() if end else None, saved, goal_id),
            )
    except sqlite3.Error as exc:
        raise AppError("ERR-goals-op", f"update: goal write failed: {exc}") from exc
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-goals-op", f"update: goal {goal_id} write affected {cursor.rowcount} rows"
        )
    return goal_id


def delete_goal(conn, goal_id):
    _require_goal(conn, goal_id, "delete")
    try:
        cursor = conn.execute("DELETE FROM financial_goals WHERE id = ?", (goal_id,))
    except sqlite3.Error as exc:
        raise AppError("ERR-goals-op", f"delete: goal write failed: {exc}") from exc
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-goals-op", f"delete: goal {goal_id} write affected {cursor.rowcount} rows"
        )
    return goal_id
