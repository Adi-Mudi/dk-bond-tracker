import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "android" / "device_smoke.sh"


def smoke_text():
    return SMOKE.read_text(encoding="utf-8")


def test_state_reset_is_the_default_not_uninstall():
    text = smoke_text()
    match = re.search(r'if \[ "\$\{DKBT_RESET:-(\d)\}" = "1" \]', text)
    assert match, "DKBT_RESET guard missing"
    assert match.group(1) == "1", "pm clear reset must default on"
    assert 'waydroid shell -- pm clear "$PKG"' in text


def test_uninstall_only_runs_in_explicit_fresh_mode():
    text = smoke_text()
    match = re.search(r'if \[ "\$\{DKBT_FRESH:-(\d)\}" = "1" \]', text)
    assert match, "DKBT_FRESH guard missing"
    assert match.group(1) == "0", "full uninstall must be opt-in"
    fresh_block_start = text.index('DKBT_FRESH')
    remove_at = text.index('waydroid app remove "$PKG"')
    install_at = text.index('waydroid app install "$APK"')
    assert fresh_block_start < remove_at < install_at


def test_fresh_mode_fails_loudly_and_suggests_the_pm_uninstall():
    text = smoke_text()
    assert "still installed after remove" in text
    assert "pm uninstall --user 0" in text


def test_clean_flag_is_gone():
    assert "DKBT_CLEAN" not in smoke_text()
