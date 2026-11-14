import os
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "scripts" / "check-release-signature.sh"
BUILD_GRADLE = ROOT / "android" / "app" / "build.gradle"
WORKFLOW = ROOT / ".github" / "workflows" / "android-release.yml"
FORBIDDEN_SUFFIXES = (".jks", ".keystore")
FORBIDDEN_NAMES = ("keystore.properties",)


def read(path):
    return path.read_text(encoding="utf-8")


def test_tc_us_01_release_signing_reads_properties_or_env_and_fails_loudly():
    text = read(BUILD_GRADLE)
    assert "keystore.properties" in text
    for name in (
        "DKBT_RELEASE_KEYSTORE_FILE",
        "DKBT_RELEASE_STORE_PASSWORD",
        "DKBT_RELEASE_KEY_ALIAS",
        "DKBT_RELEASE_KEY_PASSWORD",
    ):
        assert name in text
    assert "throw new GradleException(" in text
    assert "Release signing is not configured" in text


def test_tc_us_02_debug_build_type_does_not_use_release_signing():
    text = read(BUILD_GRADLE)
    build_types = text.split("buildTypes {", 1)[1]
    assert "signingConfigs.release" in build_types.split("release {", 1)[1]
    assert "signingConfigs.release" not in build_types.split("release {", 1)[0]


def test_tc_us_03_workflow_triggers_only_on_v_tags_and_reads_secrets():
    text = read(WORKFLOW)
    assert re.search(r"^on:\n  push:\n    tags:\n      - 'v\*'\n", text, re.M)
    assert "pull_request" not in text
    assert "workflow_dispatch" not in text
    for line in text.splitlines():
        if re.search(r"(password|PASSWORD|keystore_path|\.jks)", line) and "secrets." not in line:
            if "DKBT_RELEASE" in line or "PASSWORD" in line.upper():
                assert "${{" not in line or "secrets." in line, line


def test_tc_us_03_no_signing_material_tracked_under_android():
    tracked = subprocess.run(
        ["git", "ls-files", "android"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    offenders = [
        name
        for name in tracked
        if name.endswith(FORBIDDEN_SUFFIXES) or Path(name).name in FORBIDDEN_NAMES
    ]
    assert not offenders, f"signing material is tracked: {offenders}"


def test_tc_us_04_workflow_declares_protected_environment():
    text = read(WORKFLOW)
    assert "environment: android-release" in text


def test_tc_cg_02_guard_skips_without_pin_and_fails_on_mismatch(tmp_path):
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"not really an apk")
    env = {k: v for k, v in os.environ.items() if k != "DKBT_RELEASE_FINGERPRINT"}
    skipped = subprocess.run(
        ["sh", str(GUARD), str(apk)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert skipped.returncode == 0
    assert "::notice::guard skipped: no pinned fingerprint configured" in skipped.stdout


def test_guard_mismatch_fails_naming_both_fingerprints(tmp_path):
    fake_bin = tmp_path / "build-tools" / "34.0.0"
    fake_bin.mkdir(parents=True)
    fake = fake_bin / "apksigner"
    fake.write_text("#!/bin/sh\necho 'Signer #1 certificate SHA-256 digest: deadbeef'\n")
    fake.chmod(0o755)
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"not really an apk")
    env = dict(os.environ)
    env["ANDROID_HOME"] = str(tmp_path)
    env["DKBT_RELEASE_FINGERPRINT"] = "cafe1234"
    result = subprocess.run(
        ["sh", str(GUARD), str(apk)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1
    assert "signature mismatch" in result.stderr
    assert "cafe1234" in result.stderr
    assert "deadbeef" in result.stderr


def test_guard_unextractable_fingerprint_is_a_named_error(tmp_path):
    fake_bin = tmp_path / "build-tools" / "34.0.0"
    fake_bin.mkdir(parents=True)
    fake = fake_bin / "apksigner"
    fake.write_text("#!/bin/sh\necho 'no certificate data here'\n")
    fake.chmod(0o755)
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"not really an apk")
    env = dict(os.environ)
    env["ANDROID_HOME"] = str(tmp_path)
    env["DKBT_RELEASE_FINGERPRINT"] = "cafe1234"
    result = subprocess.run(
        ["sh", str(GUARD), str(apk)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 1
    assert "could not extract" in result.stderr


def test_guard_apksigner_missing_is_a_named_error(tmp_path):
    apk = tmp_path / "app.apk"
    apk.write_bytes(b"not really an apk")
    env = {k: v for k, v in os.environ.items() if k != "ANDROID_HOME"}
    env["DKBT_RELEASE_FINGERPRINT"] = "cafe1234"
    env["PATH"] = "/usr/bin:/bin"
    result = subprocess.run(
        ["sh", str(GUARD), str(apk)],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "apksigner not found" in result.stderr


def test_guard_missing_apk_is_named_error(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "DKBT_RELEASE_FINGERPRINT"}
    result = subprocess.run(
        ["sh", str(GUARD), str(tmp_path / "absent.apk")],
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 2
    assert "APK not found" in result.stderr
