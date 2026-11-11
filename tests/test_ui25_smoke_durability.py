from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "android" / "device_smoke.sh"


def text():
    return SMOKE.read_text(encoding="utf-8")


def test_durability_accepts_a_rerendered_page_after_restart():
    body = text()
    assert "def rendered_page(name, min_ink=0.03)" in body
    assert "rerendered = rendered_page(" in body
    assert "ratio <= 0.02 or rerendered" in body


def test_durability_still_reports_the_strict_same_page_ratio():
    body = text()
    assert '"durability_same_page_within_2pct"' in body
    assert '"durability_page_rerendered"' in body


def test_blank_restart_screen_cannot_pass():
    body = text()
    assert "return (total - dominant) / total >= min_ink" in body
    assert "min_ink=0.03" in body


def test_install_presence_is_polled_not_single_shot():
    body = (ROOT / "android" / "device_smoke.sh").read_text(encoding="utf-8")
    assert "after 20s poll" in body
    poll_at = body.index("for _ in 1 2 3 4 5 6 7 8 9 10; do")
    check_at = body.index('say "package present')
    assert poll_at < check_at
