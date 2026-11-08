import os
import sys
from pathlib import Path

APP_ROOT = Path(os.environ.get("ANDROID_APP_PATH") or os.getcwd())
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

PORT = int(os.environ.get("WEBVIEW_PORT", "5000"))


def _db_file():
    private = Path(os.environ.get("ANDROID_PRIVATE") or str(APP_ROOT))
    data = private / "data"
    data.mkdir(parents=True, exist_ok=True)
    return data / "bonds.db"


def main():
    os.chdir(str(APP_ROOT))
    from src.app import create_app

    db_file = _db_file()
    print("DKBTSPIKE starting flask db=%s" % db_file, flush=True)
    app = create_app(db_file)

    from wsgiref.simple_server import make_server

    with make_server("127.0.0.1", PORT, app) as httpd:
        print("DKBTSPIKE serving http://127.0.0.1:%d/" % PORT, flush=True)
        httpd.serve_forever()


main()
