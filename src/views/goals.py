from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for

from src.db import get_conn
from src.goals import add_goal, delete_goal, list_goals, update_goal
from src.queries import portfolio_totals, this_month_returns
from src.validators import AppError
from src.views.common import app_db, error_page

bp = Blueprint("goals", __name__)


def goals_error_page(db_file, exc, form, today):
    try:
        with get_conn(db_file) as conn:
            goals = list_goals(conn, today)
    except AppError:
        goals = []
    return (
        render_template(
            "goals.html",
            goals=goals,
            error=exc.message,
            error_code=exc.code,
            form=form,
            earned_this_month=0.0,
            total_received=0.0,
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
                )
        except AppError as exc:
            return goals_error_page(db_file, exc, request.form, today)
        flash("Goal added", "success")
        return redirect(url_for("goals.goals_page"))
    try:
        with get_conn(db_file) as conn:
            goals = list_goals(conn, today)
            month_returns = this_month_returns(conn)
            totals = portfolio_totals(conn)
    except AppError as exc:
        return error_page(exc.code, exc.message, "Financial Goals failed", 500)
    return render_template(
        "goals.html",
        goals=goals,
        error=None,
        error_code=None,
        form={},
        earned_this_month=month_returns["total"] or 0.0,
        total_received=totals["till_return"],
    )


@bp.route("/goals/<int:goal_id>/edit", methods=["POST"])
def goals_edit(goal_id):
    db_file = app_db()
    try:
        name, target_amount, target_end_date, saved_amount = _goal_form_fields(request.form)
        with get_conn(db_file) as conn:
            update_goal(
                conn,
                goal_id,
                name,
                target_amount,
                target_end_date,
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
