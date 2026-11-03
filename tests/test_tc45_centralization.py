import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
TEMPLATES = SRC / "templates"

SUM_ALLOWED = {"queries.py", "phase4.py"}
AGG_TOKENS = ("SUM(", "SELECT COUNT", "GROUP BY", "JOIN")


def python_sources():
    return sorted(SRC.glob("*.py"))


def test_status_logic_defined_only_in_status_module():
    offenders = []
    for path in python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name.startswith("compute_row_status") and path.name != "status.py":
                    offenders.append(f"{path.name}:{node.lineno} {node.name}")
    assert offenders == []
    status_text = (SRC / "status.py").read_text(encoding="utf-8")
    assert "def compute_row_status(" in status_text
    assert "def compute_row_status_daywise(" in status_text


def test_status_imports_not_redefined_in_callers():
    for caller in ("app.py", "queries.py"):
        text = (SRC / caller).read_text(encoding="utf-8")
        assert "compute_row_status_daywise" in text
        assert "def compute_row_status" not in text


def test_sum_aggregation_only_in_allowed_modules():
    offenders = []
    for path in python_sources():
        text = path.read_text(encoding="utf-8")
        if "SUM(" in text and path.name not in SUM_ALLOWED:
            offenders.append(path.name)
    for path in sorted(TEMPLATES.glob("*.html")):
        if "SUM(" in path.read_text(encoding="utf-8"):
            offenders.append(f"templates/{path.name}")
    assert offenders == []


def test_sum_actually_lives_in_query_modules():
    queries_text = (SRC / "queries.py").read_text(encoding="utf-8")
    assert "SUM(" in queries_text


def test_app_py_has_no_aggregation_or_join_sql():
    text = (SRC / "app.py").read_text(encoding="utf-8")
    for token in AGG_TOKENS:
        assert token not in text, token


def test_app_py_executes_are_point_lookups_from_query_modules():
    text = (SRC / "app.py").read_text(encoding="utf-8")
    assert "conn.execute(" in text
    assert "from src.queries import (" in text
    assert "status_overview" in text
    assert "summary_amounts" in text
    assert "chart_data" in text
