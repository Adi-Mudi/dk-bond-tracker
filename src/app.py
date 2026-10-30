import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from flask import Flask, render_template

from src.import_xlsm import import_workbook
from src.validators import AppError

DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "bonds.db"


def create_app(db_path=None):
    app = Flask(__name__)
    app.config["DB_PATH"] = db_path

    @app.route("/")
    def index():
        return render_template("base.html")

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
    create_app().run(host="127.0.0.1", port=5000)
    return 0


if __name__ == "__main__":
    sys.exit(main())
