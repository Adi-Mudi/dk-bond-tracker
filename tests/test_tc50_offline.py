import ast
from pathlib import Path

import pytest

from src.mailer import send_alert_email
from src.validators import AppError

SRC = Path(__file__).resolve().parents[1] / "src"

FORBIDDEN_IMPORT_ROOTS = {"requests", "httpx", "urllib", "socket"}


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


def smtplib_importers():
    return [path for path in python_sources() if "smtplib" in imported_roots(path)]


def test_no_network_imports_in_src():
    offenders = []
    for path in python_sources():
        for root in imported_roots(path) & FORBIDDEN_IMPORT_ROOTS:
            offenders.append(f"{path.relative_to(SRC)}: imports {root}")
    assert offenders == []


def test_no_http_url_strings_in_src():
    offenders = []
    for path in python_sources():
        text = path.read_text(encoding="utf-8")
        for token in ("http://", "https://"):
            if token in text:
                offenders.append(f"{path.relative_to(SRC)}: contains {token}")
    assert offenders == []


def test_smtplib_only_imported_in_mailer():
    importers = [path.relative_to(SRC).as_posix() for path in smtplib_importers()]
    assert importers == ["mailer.py"]


def test_mailer_is_only_smtplib_module():
    offenders = [
        path.relative_to(SRC).as_posix()
        for path in smtplib_importers()
        if path.name != "mailer.py"
    ]
    assert offenders == []


def test_send_alert_email_without_app_password_raises_unconfigured(monkeypatch):
    monkeypatch.delenv("SMTP_APP_PASSWORD", raising=False)
    monkeypatch.setenv("SMTP_USER", "owner@example.test")
    with pytest.raises(AppError) as exc_info:
        send_alert_email(
            {"company": "CredCo", "month": "2026-10", "severity": "reminder", "credit_day": 5}
        )
    assert exc_info.value.code == "ERR-smtp-unconfigured"
    assert "SMTP_APP_PASSWORD" in exc_info.value.message


def test_no_socket_or_http_client_calls_in_src():
    offenders = []
    for path in python_sources():
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
        roots = imported_roots(path)
        if "http" in roots:
            offenders.append(f"{path.relative_to(SRC)}: imports http client")
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr == "create_connection":
                    offenders.append(f"{path.relative_to(SRC)}: calls create_connection")
                elif isinstance(func, ast.Name) and func.id == "create_connection":
                    offenders.append(f"{path.relative_to(SRC)}: calls create_connection")
    assert offenders == []
