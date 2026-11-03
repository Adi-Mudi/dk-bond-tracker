from pathlib import Path

from src.db import get_conn
from src.prefs import get_pref, set_pref


def test_tc146_pref_roundtrip_and_default(db_path):
    with get_conn(db_path) as conn:
        assert get_pref(conn, "missing") is None
        assert get_pref(conn, "missing", "fallback") == "fallback"
        set_pref(conn, "privacy_mode", "on")
        assert get_pref(conn, "privacy_mode") == "on"
        set_pref(conn, "privacy_mode", "off")
        assert get_pref(conn, "privacy_mode") == "off"
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM alert_prefs WHERE key = 'privacy_mode'"
        ).fetchone()
        assert row["n"] == 1


def test_tc146_single_privacy_mechanism():
    root = Path(__file__).resolve().parents[1]
    js = (root / "src" / "static" / "app.js").read_text(encoding="utf-8")
    base = (root / "src" / "templates" / "base.html").read_text(encoding="utf-8")
    assert "hide-amounts" not in js
    assert "applyMask" not in js
    assert "privacy-on" in base
