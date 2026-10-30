import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN_IMPORT_ROOTS = {"requests", "httpx", "urllib", "socket", "smtplib"}


def python_sources():
    return sorted(SRC.rglob("*.py"))


def imported_roots(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def test_no_network_or_mail_imports_in_src():
    offenders = []
    for path in python_sources():
        for root in imported_roots(path) & FORBIDDEN_IMPORT_ROOTS:
            offenders.append(f"{path.relative_to(SRC)}: imports {root}")
    assert offenders == []


def test_smtplib_not_imported_yet():
    offenders = [
        f"{path.relative_to(SRC)}: imports smtplib"
        for path in python_sources()
        if "smtplib" in imported_roots(path)
    ]
    assert offenders == []


def test_no_http_url_strings_in_src():
    offenders = []
    for path in python_sources():
        text = path.read_text(encoding="utf-8")
        for token in ("http://", "https://"):
            if token in text:
                offenders.append(f"{path.relative_to(SRC)}: contains {token}")
    assert offenders == []
