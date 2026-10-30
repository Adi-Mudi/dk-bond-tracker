import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
PORT = 5077
LAUNCH_BUDGET_SECONDS = 60
REALISTIC_BUDGET_SECONDS = 15


def _wait_for_dashboard(proc, url, deadline_seconds):
    start = time.monotonic()
    body = None
    while time.monotonic() - start < deadline_seconds:
        if proc.poll() is not None:
            raise AssertionError(
                f"app process exited early with code {proc.returncode}"
            )
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    body = response.read().decode("utf-8", errors="replace")
                    break
        except (urllib.error.URLError, ConnectionError, TimeoutError, OSError):
            pass
        time.sleep(0.25)
    elapsed = time.monotonic() - start
    return body, elapsed


def test_clean_launch_reaches_live_dashboard(tmp_path):
    db_path = tmp_path / "fresh_bonds.db"
    env = dict(os.environ)
    env["PORT"] = str(PORT)
    env["PYTHONUNBUFFERED"] = "1"
    url = f"http://127.0.0.1:{PORT}/"
    proc = subprocess.Popen(
        [sys.executable, "src/app.py", "--db", str(db_path)],
        cwd=str(WORKSPACE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        body, elapsed = _wait_for_dashboard(proc, url, LAUNCH_BUDGET_SECONDS)
        assert body is not None, f"dashboard not up within {LAUNCH_BUDGET_SECONDS}s"
        assert "DK Bond Tracker" in body
        assert db_path.exists()
        assert elapsed < LAUNCH_BUDGET_SECONDS
        assert elapsed < REALISTIC_BUDGET_SECONDS, f"launch took {elapsed:.1f}s"
        print(f"TC-43 measured launch seconds: {elapsed:.2f}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)
