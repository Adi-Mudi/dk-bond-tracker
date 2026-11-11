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


def test_install_presence_is_polled_before_the_warning_path():
    body = (ROOT / "android" / "device_smoke.sh").read_text(encoding="utf-8")
    poll_at = body.index("for _ in 1 2 3 4 5 6 7 8 9 10; do")
    check_at = body.index('say "package present')
    warn_at = body.index("WARN: package not listed by app list")
    assert poll_at < check_at < warn_at


def test_stale_app_list_does_not_fail_a_successful_install():
    body = (ROOT / "android" / "device_smoke.sh").read_text(encoding="utf-8")
    assert "WARN: package not listed by app list" in body
    assert 'fail "package missing from app list' not in body
