import sys
import threading
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

PORT = 5000
_thread = None
_server = None


def _serve(db_dir):
    global _server
    from src.app import create_app
    from werkzeug.serving import make_server

    db_file = Path(db_dir) / "bonds.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    app = create_app(db_file)
    _server = make_server("127.0.0.1", PORT, app, threaded=True)
    print("DKBTSPIKE-B serving http://127.0.0.1:%d/ db=%s" % (PORT, db_file), flush=True)
    _server.serve_forever()


def start(db_dir):
    global _thread
    if _thread is None:
        _thread = threading.Thread(target=_serve, args=(db_dir,), daemon=True)
        _thread.start()
    return True


def stop():
    global _server
    if _server is not None:
        _server.shutdown()
    return True
