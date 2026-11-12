import json
import re
import sqlite3
from datetime import date

from .queries import goal_derived
from .validators import AppError, parse_date_value, safe_float

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def months_until(end_date, today=None):
    if today is None:
        today = date.today()
    if isinstance(end_date, str):
        end_date = parse_date_value(end_date, "target_end_date")
    total = (end_date.year - today.year) * 12 + (end_date.month - today.month)
    if end_date.day < today.day:
        total -= 1
    return total


def months_between(start_raw, end_raw):
    start = parse_date_value(start_raw, "start_date")
    end = parse_date_value(end_raw, "target_end_date")
    total = (end.year - start.year) * 12 + (end.month - start.month)
    if end.day < start.day:
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


def _goal_date(raw, field="target_end_date"):
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return parse_date_value(text, field)
    except AppError as exc:
        raise AppError("ERR-goals-op", f"{field} must be a date: {raw!r}") from exc


def _parse_checkins(raw):
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, list):
        return []
    return sorted({str(item) for item in parsed})


def _dump_checkins(months):
    return json.dumps(sorted({str(item) for item in months}))


def _decorate(row, today, derived):
    entry = dict(row)
    end_raw = entry.get("target_end_date")
    target = entry.get("target_amount")
    saved = safe_float(entry.get("saved_amount"))
    entry["saved_amount"] = saved
    entry["is_legacy"] = end_raw is None
    entry["months_remaining"] = None
    entry["progress_pct"] = None
    entry["monthly_amount"] = safe_float(entry.get("monthly_amount"))
    entry["start_date"] = entry.get("start_date")
    entry["checkins"] = _parse_checkins(entry.get("checkins"))
    info = derived.get(entry["id"], {"invested": 0.0, "returns": 0.0, "bonds": []})
    entry["invested_via_bonds"] = info["invested"]
    entry["returns_received"] = info["returns"]
    entry["linked_bonds"] = info["bonds"]
    entry["linked_count"] = len(info["bonds"])
    entry["checkin_count"] = len(entry["checkins"])
    entry["derived_total"] = saved + info["invested"] + info["returns"]
    if end_raw is not None:
        end = parse_date_value(str(end_raw), "target_end_date")
        entry["months_remaining"] = months_until(end, today)
    if target is not None and float(target) > 0:
        entry["progress_pct"] = round(entry["derived_total"] / float(target) * 100.0, 1)
    return entry


def list_goals(conn, today=None):
    if today is None:
        today = date.today()
    try:
        rows = conn.execute(
            "SELECT id, name, target_amount, target_end_date, note, saved_amount, "
            "monthly_amount, start_date, checkins "
            "FROM financial_goals ORDER BY target_end_date, id"
        ).fetchall()
    except sqlite3.Error as exc:
        raise AppError("ERR-goals-op", f"list: goal query failed: {exc}") from exc
    derived = goal_derived(conn)
    return [_decorate(dict(row), today, derived) for row in rows]


def add_goal(
    conn,
    name,
    target_amount,
    target_end_date,
    note="",
    saved_amount=None,
    monthly_amount=None,
    start_date=None,
):
    clean_name = str(name or "").strip()
    if not clean_name:
        raise AppError("ERR-goals-op", "create: name is required")
    value = _goal_amount(target_amount, "target_amount")
    end = _goal_date(target_end_date)
    saved = _goal_amount(saved_amount, "saved_amount")
    monthly = _goal_amount(monthly_amount, "monthly_amount")
    start = _goal_date(start_date, "start_date")
    if value <= 0 and monthly > 0:
        if start is None or end is None:
            raise AppError(
                "ERR-goals-op", "create: start date and end date are required for a monthly plan"
            )
        months = months_between(start.isoformat(), end.isoformat()) + 1
        if months < 1:
            raise AppError("ERR-goals-op", "create: end date must be after start date")
        value = monthly * months
    clean_note = str(note or "").strip()
    try:
        cursor = conn.execute(
            "INSERT INTO financial_goals (name, target_amount, target_end_date, note, "
            "saved_amount, monthly_amount, start_date, checkins) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                clean_name,
                value,
                end.isoformat() if end else None,
                clean_note,
                saved,
                monthly,
                start.isoformat() if start else None,
                _dump_checkins([]),
            ),
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


def set_checkin(conn, goal_id, month, invested):
    _require_goal(conn, goal_id, "check-in")
    key = str(month or "").strip()
    if not MONTH_PATTERN.match(key):
        raise AppError("ERR-goals-op", f"check-in month must be YYYY-MM: {month!r}")
    row = conn.execute(
        "SELECT checkins FROM financial_goals WHERE id = ?", (goal_id,)
    ).fetchone()
    months = _parse_checkins(row["checkins"])
    if invested:
        if key not in months:
            months.append(key)
    else:
        months = [item for item in months if item != key]
    try:
        cursor = conn.execute(
            "UPDATE financial_goals SET checkins = ? WHERE id = ?",
            (_dump_checkins(months), goal_id),
        )
    except sqlite3.Error as exc:
        raise AppError("ERR-goals-op", f"check-in: goal write failed: {exc}") from exc
    if cursor.rowcount != 1:
        raise AppError(
            "ERR-goals-op", f"check-in: goal {goal_id} write affected {cursor.rowcount} rows"
        )
    return key


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
