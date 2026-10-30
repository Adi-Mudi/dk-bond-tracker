import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
TEMPLATES = SRC / "templates"

FORBIDDEN_LITERALS = ("Feb-2027", "Feb-27")
MONTH_LITERAL = re.compile(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)-\d{2,4}\b")


def scan_files():
    files = sorted(SRC.glob("*.py")) + sorted(TEMPLATES.glob("*.html"))
    assert files
    return files


def test_no_hardcoded_feb2027_literals():
    offenders = []
    for path in scan_files():
        text = path.read_text(encoding="utf-8")
        for literal in FORBIDDEN_LITERALS:
            if literal in text:
                offenders.append(f"{path.relative_to(ROOT)}: {literal!r}")
    assert offenders == []


def test_no_hardcoded_month_header_literals_anywhere():
    offenders = []
    for path in scan_files():
        text = path.read_text(encoding="utf-8")
        for match in MONTH_LITERAL.finditer(text):
            offenders.append(f"{path.relative_to(ROOT)}: {match.group(0)!r}")
    assert offenders == []


def test_header_coupling_uses_header_key_helper():
    import_xlsm = (SRC / "import_xlsm.py").read_text(encoding="utf-8")
    assert "header_key(" in import_xlsm
