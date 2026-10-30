import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN_PATTERNS = [
    (re.compile(r"api_key", re.IGNORECASE), "api_key"),
    (re.compile(r"password\s*=\s*['\"][^'\"]+['\"]", re.IGNORECASE), "password literal assignment"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "AWS access key id"),
    (re.compile(r"\bsk-[A-Za-z0-9]{16,}"), "secret key literal"),
]


def python_sources():
    return sorted(SRC.rglob("*.py"))


def test_src_contains_python_files():
    files = python_sources()
    assert files
    assert (SRC / "app.py") in files
    assert (SRC / "db.py") in files


def test_no_forbidden_secret_patterns_in_src():
    offenders = []
    for path in python_sources():
        text = path.read_text(encoding="utf-8")
        for pattern, label in FORBIDDEN_PATTERNS:
            for match in pattern.finditer(text):
                offenders.append(f"{path.relative_to(SRC)}: {label}: {match.group(0)!r}")
    assert offenders == []
