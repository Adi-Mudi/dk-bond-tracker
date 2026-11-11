import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SMOKE = ROOT / "android" / "device_smoke.sh"


def smoke_text():
    return SMOKE.read_text(encoding="utf-8")


def test_clean_install_is_the_default():
    text = smoke_text()
    match = re.search(r'if \[ "\$\{DKBT_CLEAN:-(\d)\}" = "1" \]', text)
    assert match, "DKBT_CLEAN guard missing"
    assert match.group(1) == "1", "clean install must default to on (core rule: uninstall before testing)"


def test_clean_install_removes_the_package_before_installing():
    text = smoke_text()
    remove_at = text.index('waydroid app remove "$PKG"')
    install_at = text.index('waydroid app install "$APK"')
    assert remove_at < install_at, "uninstall must run before install"


def test_clean_install_fails_loudly_when_the_package_survives():
    text = smoke_text()
    assert "still installed after remove" in text
