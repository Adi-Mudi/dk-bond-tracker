from flask import Blueprint, jsonify, render_template, request

from src.db import get_conn
from src.views.common import app_db

bp = Blueprint("search", __name__)

CHIP_CLASS = {
    "Danger": "chip-danger",
    "On-going": "chip-ongoing",
    "Completed": "chip-matured",
    "Matured": "chip-matured",
}


def _pattern(query):
    return f"%{query}%"


def search_groups(conn, query):
    if not query:
        return []
    pattern = _pattern(query)
    groups = []
    holdings = conn.execute(
        "SELECT id, company, isin, status FROM bonds "
        "WHERE watch_state = 'holding' AND (company LIKE ? OR isin LIKE ?) "
        "ORDER BY company COLLATE NOCASE, id",
        (pattern, pattern),
    ).fetchall()
    if holdings:
        groups.append(
            {
                "source": "Holdings",
                "kind": "holding",
                "hits": [
                    {
                        "id": row["id"],
                        "company": row["company"] or "",
                        "isin": row["isin"] or "",
                        "chip": row["status"] or "On-going",
                        "chip_class": CHIP_CLASS.get(row["status"] or "", "chip-watching"),
                        "href": f"/portfolio/{row['id']}",
                    }
                    for row in holdings
                ],
            }
        )
    watching = conn.execute(
        "SELECT id, company, isin, rating FROM bonds "
        "WHERE watch_state = 'watching' AND (company LIKE ? OR isin LIKE ?) "
        "ORDER BY company COLLATE NOCASE, id",
        (pattern, pattern),
    ).fetchall()
    if watching:
        groups.append(
            {
                "source": "Watchlist",
                "kind": "watching",
                "hits": [
                    {
                        "id": row["id"],
                        "company": row["company"] or "",
                        "isin": row["isin"] or "",
                        "chip": "Watching",
                        "chip_class": "chip-watching",
                        "href": f"/watch#candidate-{row['id']}",
                    }
                    for row in watching
                ],
            }
        )
    return groups


@bp.route("/search")
def search_page():
    db_file = app_db()
    query = str(request.args.get("q") or "").strip()
    with get_conn(db_file) as conn:
        groups = search_groups(conn, query)
    total = sum(len(group["hits"]) for group in groups)
    if request.args.get("format") == "json":
        return jsonify({"query": query, "total": total, "groups": groups})
    return render_template("search.html", query=query, groups=groups, total=total)
