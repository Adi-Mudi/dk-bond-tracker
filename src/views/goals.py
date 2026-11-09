import calendar
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.goals import add_goal, delete_goal, list_goals, months_between, set_checkin, update_goal
from src.queries import portfolio_totals, this_month_returns
from src.validators import AppError
from src.views.common import app_db, error_page

bp = Blueprint("goals", __name__)


def _month_span(start_key, count):
    year, mon = map(int, start_key.split("-"))
    return [
        f"{year + (mon - 1 + offset) // 12:04d}-{(mon - 1 + offset) % 12 + 1:02d}"
        for offset in range(count)
    ]


def _checkin_months(goal, today):
    start = goal.get("start_date")
    end = goal.get("target_end_date")
    keys = []
    if start and end:
        try:
            count = months_between(start, end) + 1
        except AppError:
            count = 0
        if count < 1 or count > 36:
            count = 12
        keys = _month_span(str(start)[:7], count)
    else:
        keys = [f"{today.year:04d}-{month:02d}" for month in range(1, 13)]
    checked = set(goal["checkins"])
    return [
        {
            "key": key,
            "label": f"{calendar.month_abbr[int(key[5:7])]} {key[2:4]}",
            "invested": key in checked,
        }
        for key in keys
    ]


def _consolidated(goals):
    return {
        "monthly_commitment": sum(goal["monthly_amount"] for goal in goals),
        "saved": sum(goal["saved_amount"] for goal in goals),
        "invested": sum(goal["invested_via_bonds"] for goal in goals),
        "returns": sum(goal["returns_received"] for goal in goals),
    }


def _goals_context(db_file, today):
    with get_conn(db_file) as conn:
        goals = list_goals(conn, today)
        month_returns = this_month_returns(conn)
        totals = portfolio_totals(conn)
    for goal in goals:
        goal["checkin_months"] = _checkin_months(goal, today)
    return {
        "goals": goals,
        "consolidated": _consolidated(goals),
        "earned_this_month": month_returns["total"] or 0.0,
        "total_received": totals["till_return"],
    }


def goals_error_page(db_file, exc, form, today):
    try:
        context = _goals_context(db_file, today)
    except AppError:
        context = {
            "goals": [],
            "consolidated": {
                "monthly_commitment": 0.0,
                "saved": 0.0,
                "invested": 0.0,
                "returns": 0.0,
            },
            "earned_this_month": 0.0,
            "total_received": 0.0,
        }
    return (
        render_template(
            "goals.html",
            error=exc.message,
            error_code=exc.code,
            form=form,
            **context,
        ),
        400,
    )


def _goal_form_fields(form):
    return (
        form.get("name", ""),
        form.get("target_amount", ""),
        form.get("target_end_date", ""),
        form.get("saved_amount", ""),
    )


@bp.route("/goals", methods=["GET", "POST"])
def goals_page():
    db_file = app_db()
    today = date.today()
    if request.method == "POST":
        try:
            name, target_amount, target_end_date, saved_amount = _goal_form_fields(request.form)
            with get_conn(db_file) as conn:
                add_goal(
                    conn,
                    name,
                    target_amount,
                    target_end_date,
                    request.form.get("note", ""),
                    saved_amount,
                    request.form.get("monthly_amount", ""),
                    request.form.get("start_date", ""),
                )
        except AppError as exc:
            return goals_error_page(db_file, exc, request.form, today)
        flash("Goal added", "success")
        return redirect(url_for("goals.goals_page"))
    try:
        context = _goals_context(db_file, today)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Financial Goals failed", 500)
    return render_template(
        "goals.html",
        error=None,
        error_code=None,
        form={},
        **context,
    )


@bp.route("/goals/<int:goal_id>/checkin", methods=["POST"])
def goals_checkin(goal_id):
    db_file = app_db()
    try:
        invested = request.form.get("invested") in ("on", "1", "true", "yes")
        with get_conn(db_file) as conn:
            key = set_checkin(conn, goal_id, request.form.get("month", ""), invested)
    except AppError as exc:
        return goals_error_page(db_file, exc, request.form, date.today())
    flash(f"Check-in saved for {key}", "success")
    return redirect(url_for("goals.goals_page"))


@bp.route("/goals/<int:goal_id>/edit", methods=["POST"])
def goals_edit(goal_id):
    db_file = app_db()
    try:
        name, _target, _end, saved_amount = _goal_form_fields(request.form)
        with get_conn(db_file) as conn:
            stored = conn.execute(
                "SELECT target_amount, target_end_date FROM financial_goals WHERE id = ?",
                (goal_id,),
            ).fetchone()
            if stored is None:
                raise AppError("ERR-goals-op", f"update: goal not found: {goal_id!r}")
            update_goal(
                conn,
                goal_id,
                name,
                stored["target_amount"],
                stored["target_end_date"],
                saved_amount,
            )
    except AppError as exc:
        return goals_error_page(db_file, exc, request.form, date.today())
    flash(f"Goal updated: {goal_id}", "success")
    return redirect(url_for("goals.goals_page"))


@bp.route("/goals/<int:goal_id>/delete", methods=["POST"])
def goals_delete(goal_id):
    db_file = app_db()
    try:
        with get_conn(db_file) as conn:
            delete_goal(conn, goal_id)
    except AppError as exc:
        return goals_error_page(db_file, exc, request.form, date.today())
    flash(f"Goal deleted: {goal_id}", "success")
    return redirect(url_for("goals.goals_page"))
