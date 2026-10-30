import argparse
import json
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template

from src.db import get_conn, init_db
from src.import_xlsm import import_workbook
from src.queries import (
    active_bonds_in_month,
    chart_data,
    monthly_history,
    status_overview,
    summary_amounts,
    summary_counts,
    this_month_returns,
)
from src.status import month_key
from src.validators import AppError

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "bonds.db"


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = str(db_path) if db_path else str(DEFAULT_DB_PATH)

    @app.route("/")
    def index():
        db_file = Path(app.config["DB_PATH"])
        if not db_file.exists():
            init_db(db_file)
        try:
            with get_conn(db_file) as conn:
                today = date.today()
                context = {
                    "counts": summary_counts(conn, today),
                    "amounts": summary_amounts(conn, today),
                    "this_month": this_month_returns(conn, today),
                    "active_bonds": active_bonds_in_month(conn, today),
                    "history": monthly_history(conn, today),
                    "overview": status_overview(conn, today),
                    "charts": chart_data(conn, today),
                    "current_month": month_key(today),
                }
        except AppError as exc:
            return render_template("error.html", code=exc.code, message=exc.message), 500
        return render_template("dashboard.html", **context)

    return app


def main(argv=None):
    parser = argparse.ArgumentParser(prog="dk-bond-tracker")
    parser.add_argument("--import", dest="import_path", metavar="XLSM")
    parser.add_argument("--db", dest="db_path", default=str(DEFAULT_DB_PATH), metavar="SQLITE")
    args = parser.parse_args(argv)
    if args.import_path:
        try:
            summary = import_workbook(args.import_path, args.db_path)
        except AppError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(summary, indent=2))
        return 0
    create_app(args.db_path).run(host="127.0.0.1", port=5000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
