import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"


def python_sources():
    return sorted(SRC.glob("*.py"))


def all_except_handlers():
    for path in python_sources():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler):
                yield path, node


def handler_names(handler):
    names = set()
    if handler.type is None:
        names.add("*")
    elif isinstance(handler.type, ast.Name):
        names.add(handler.type.id)
    elif isinstance(handler.type, ast.Tuple):
        for element in handler.type.elts:
            if isinstance(element, ast.Name):
                names.add(element.id)
    return names


def handler_calls(handler):
    calls = set()
    for node in ast.walk(handler):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.add(node.func.attr)
    return calls


def handler_raises(handler):
    return any(isinstance(node, ast.Raise) for node in ast.walk(handler))


def handler_returns(handler):
    return any(isinstance(node, ast.Return) for node in ast.walk(handler))


def test_no_bare_pass_under_except_blocks():
    offenders = []
    for path, handler in all_except_handlers():
        if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
            offenders.append(f"{path.name}:{handler.lineno}")
    assert offenders == []


def test_except_exception_never_continues_silently():
    log_calls = {"notify", "notify_once", "print", "write", "stderr"}
    offenders = []
    for path, handler in all_except_handlers():
        if "Exception" not in handler_names(handler):
            continue
        if handler_raises(handler) or handler_returns(handler):
            continue
        if handler_calls(handler) & log_calls:
            continue
        offenders.append(f"{path.name}:{handler.lineno}")
    assert offenders == []
