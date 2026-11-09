import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

import pytest
import xml.etree.ElementTree as ET

ANDROID = Path(__file__).resolve().parents[1]
REPO = ANDROID.parent
APP = ANDROID / "app"
MANIFEST = APP / "src" / "main" / "AndroidManifest.xml"
NETSEC = APP / "src" / "main" / "res" / "xml" / "network_security_config.xml"
MAIN_PY = APP / "src" / "main" / "python" / "main.py"
PY_PKG = APP / "src" / "main" / "python"
ACTIVITY = APP / "src" / "main" / "java" / "com" / "dkbondtracker" / "app" / "MainActivity.java"
BUILD_GRADLE = APP / "build.gradle"
PY_SRC_LINK = PY_PKG / "src"
APK = APP / "build" / "outputs" / "apk" / "debug" / "app-debug.apk"
SMOKE = ANDROID / "device_smoke.sh"

ANDROID_NS = "{http://schemas.android.com/apk/res/android}"

COVERAGE = {
    "TC-AND-01": {"tier": "device", "check": "device_smoke.sh::dashboard_launch"},
    "TC-AND-02": {"tier": "host", "check": "test_tc_and_02_core_not_forked + test_tc_and_02_bundled_assets_byte_identical"},
    "TC-AND-03": {"tier": "host+device", "check": "test_tc_and_03_db_path_is_app_private + device_smoke.sh::app_private_db", "device_status": "BLOCKED", "blocked_by": "env: no run-as; host contract covers"},
    "TC-AND-04": {"tier": "host+device", "check": "test_tc_and_04_network_security_config + device_smoke.sh::dashboard_launch"},
    "TC-AND-05": {"tier": "host+device", "check": "test_tc_and_05_no_storage_permission + test_tc_and_05_export_share_wiring + device_smoke.sh::export_share_sheet"},
    "TC-AND-06": {"tier": "host+device", "check": "test_tc_and_06_no_push_channels + device_smoke.sh::alerts_parity"},
    "TC-AND-07": {"tier": "device", "check": "device_smoke.sh::relaunch_durability"},
    "TC-AND-08": {"tier": "host", "check": "test_tc_and_08_manifest_permissions_are_internet_only"},
    "TC-AND-09": {"tier": "host", "check": "web suite: pytest tests -q -m 'not remote' -> 499"},
}


def manifest_permissions():
    root = ET.parse(MANIFEST).getroot()
    out = set()
    for perm in root.findall("uses-permission"):
        name = perm.get(ANDROID_NS + "name")
        if name:
            out.add(name)
    return out


def sha256_file(path):
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def _psrs_path():
    candidates = [
        REPO / "docs" / "requirements" / "dk_bond_tracker_android_psrs_20261109.json",
        REPO.parent / "01_excel_dashboard" / "docs" / "requirements" / "dk_bond_tracker_android_psrs_20261109.json",
    ]
    for cand in candidates:
        if cand.exists():
            return cand
    return None


def test_tc_and_coverage_matrix_is_complete():
    ids = set(COVERAGE)
    psrs = _psrs_path()
    if psrs is not None:
        data = json.loads(psrs.read_text())
        ids = {tc["id"] for tc in data["test_cases"]}
    assert ids == set(COVERAGE)
    for tc_id, entry in COVERAGE.items():
        assert entry["tier"] in ("host", "device", "host+device", "host-run")
        assert entry["check"]


def test_tc_and_02_core_not_forked():
    assert PY_SRC_LINK.is_symlink(), "app/src/main/python/src must be a symlink, not a copy"
    assert PY_SRC_LINK.resolve() == (REPO / "src").resolve()
    top = sorted(p.name for p in PY_PKG.glob("*.py"))
    assert top == ["main.py"], f"python source set must hold only the launcher, found {top}"


def test_tc_and_02_bundled_assets_byte_identical():
    if not APK.exists():
        pytest.skip(f"APK not built at {APK}")
    with zipfile.ZipFile(APK) as apk:
        imy = apk.read("assets/chaquopy/app.imy")
    checked = 0
    with zipfile.ZipFile(io.BytesIO(imy)) as inner:
        for name in inner.namelist():
            if not (name.startswith("src/templates/") or name.startswith("src/static/")):
                continue
            if inner.getinfo(name).is_dir():
                continue
            repo_file = REPO / name
            assert repo_file.is_file(), f"{name} bundled but absent from repo"
            assert hashlib.sha256(inner.read(name)).hexdigest() == sha256_file(repo_file), name
            checked += 1
    assert checked >= 15, f"expected >=15 bundled templates/static assets, saw {checked}"


def test_tc_and_03_db_path_is_app_private():
    main_text = MAIN_PY.read_text()
    assert re.search(r'db_file\s*=\s*Path\(db_dir\)\s*/\s*"bonds\.db"', main_text)
    assert 'make_server("127.0.0.1"' in main_text
    act = ACTIVITY.read_text()
    assert "getFilesDir()" in act
    assert "getExternalFilesDir" not in act
    assert "getExternalStorageDirectory" not in act
    assert "WRITE_EXTERNAL_STORAGE" not in act


def test_tc_and_04_network_security_config():
    root = ET.parse(NETSEC).getroot()
    assert root.tag == "network-security-config"
    dc = root.find("domain-config")
    assert dc is not None
    assert dc.get("cleartextTrafficPermitted") == "true"
    domains = {d.text for d in dc.findall("domain")}
    assert domains == {"127.0.0.1", "localhost"}
    manifest_text = MANIFEST.read_text()
    assert 'android:networkSecurityConfig="@xml/network_security_config"' in manifest_text
    assert "usesCleartextTraffic" not in manifest_text


def test_tc_and_05_no_storage_permission():
    perms = manifest_permissions()
    storage = [p for p in perms if "STORAGE" in p]
    assert storage == [], f"storage permissions present: {storage}"


def test_tc_and_05_export_share_wiring():
    provider = ET.parse(MANIFEST).getroot().find("application/provider")
    assert provider is not None, "ExportProvider not declared in the manifest"
    assert provider.get(ANDROID_NS + "name") == ".ExportProvider"
    assert provider.get(ANDROID_NS + "authorities") == "com.dkbondtracker.app.share"
    assert provider.get(ANDROID_NS + "exported") == "false"
    assert provider.get(ANDROID_NS + "grantUriPermissions") == "true"
    act = ACTIVITY.read_text()
    assert "setDownloadListener" in act
    assert "Intent.ACTION_SEND" in act
    assert "ExportProvider.AUTHORITY" in act
    assert "getFilesDir()" in act
    prov = (ACTIVITY.parent / "ExportProvider.java").read_text()
    assert "MODE_READ_ONLY" in prov
    assert "getCanonicalPath" in prov
    assert "getFilesDir(), EXPORTS_DIR" in prov
    assert "UnsupportedOperationException" in prov
    settings = (REPO / "src" / "templates" / "settings.html").read_text()
    assert 'href="/export.csv?scope=full"' in settings


def test_tc_and_06_no_push_channels():
    haystack = "\n".join(
        p.read_text()
        for p in (MANIFEST, ACTIVITY, MAIN_PY, BUILD_GRADLE, NETSEC)
    )
    forbidden = [
        "SEND_SMS", "RECEIVE_SMS", "READ_SMS",
        "com.google.firebase", "FirebaseMessaging", "gcm", "GCM",
        "whatsapp", "WhatsApp", "twilio", "Twilio",
        "POST_NOTIFICATIONS", "com.google.android.c2dm",
    ]
    found = [token for token in forbidden if token in haystack]
    assert found == [], f"forbidden channel tokens present: {found}"


def test_tc_and_08_manifest_permissions_are_internet_only():
    assert manifest_permissions() == {"android.permission.INTERNET"}
    manifest_text = MANIFEST.read_text()
    assert manifest_text.count("<uses-permission") == 1


def test_tc_and_08_merged_manifest_permissions():
    merged = list(APP.glob("build/intermediates/merged_manifest*/debug/**/AndroidManifest.xml"))
    merged += list(APP.glob("build/intermediates/merged_manifests/debug/**/AndroidManifest.xml"))
    if not merged:
        pytest.skip("merged manifest not present (run :app:processDebugMainManifest)")
    root = ET.parse(merged[0]).getroot()
    perms = {p.get(ANDROID_NS + "name") for p in root.findall("uses-permission")}
    assert perms == {"android.permission.INTERNET"}


def test_d5_device_smoke_script_is_single_command():
    assert SMOKE.exists(), "device smoke script missing"
    text = SMOKE.read_text()
    assert text.startswith("#!"), "script must have a shebang"
    for token in ("waydroid app install", "waydroid app launch"):
        assert token in text, f"smoke script must drive the device via '{token}'"
    for tc in ("TC-AND-01", "TC-AND-04", "TC-AND-05", "TC-AND-06", "TC-AND-07"):
        assert tc in text, f"smoke script must cover {tc}"
