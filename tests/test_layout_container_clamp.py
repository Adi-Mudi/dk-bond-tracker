import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
THEME = ROOT / "src" / "static" / "theme.css"
CSS = THEME.read_text(encoding="utf-8")

SHELLS = {".card": "card", ".form-grid": "form-shell", ".table-wrap": "table-shell"}
HEADINGS = ("h1", "h2", ".page-title")
SECTIONS = (".card", ".stat-card")


def parse_rules(css):
    rules = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def scan(text, at):
        pos = 0
        while pos < len(text):
            brace = text.find("{", pos)
            if brace == -1:
                break
            header = text[pos:brace].strip()
            depth = 1
            end = brace + 1
            while end < len(text) and depth:
                if text[end] == "{":
                    depth += 1
                elif text[end] == "}":
                    depth -= 1
                end += 1
            body = text[brace + 1 : end - 1]
            if header.startswith("@"):
                scan(body, header)
            elif header:
                rules.append((at, header, body))
            pos = end

    scan(css, "")
    return rules


RULES = parse_rules(CSS)


def blocks_for(selector, rules=None):
    bodies = []
    for _at, header, body in (RULES if rules is None else rules):
        for part in header.split(","):
            if part.strip() == selector:
                bodies.append(body)
    return bodies


def container_queries(name):
    return [body for at, _header, body in RULES if at.startswith("@container") and name in at]


def test_parser_reads_nested_at_rule_bodies():
    sample = "@media (max-width: 768px) { .probe { padding: 1rem; } }"
    bodies = blocks_for(".probe", parse_rules(sample))
    assert [body.strip() for body in bodies] == ["padding: 1rem;"]


def test_shell_selectors_declare_container_type():
    for selector in SHELLS:
        bodies = blocks_for(selector)
        assert bodies, "missing shell rule: " + selector
        assert any("container-type" in body for body in bodies), selector
        assert any("container-name" in body for body in bodies), selector


def test_each_shell_has_a_container_query_rule():
    for selector, name in SHELLS.items():
        assert container_queries(name), "no @container rule for " + name


def test_a_container_query_adjusts_padding_or_columns():
    joined = " ".join(" ".join(container_queries(name)) for name in SHELLS.values())
    assert "padding" in joined or "grid-template-columns" in joined


def test_headings_use_fluid_clamp():
    for selector in HEADINGS:
        bodies = blocks_for(selector)
        assert bodies, "missing heading rule: " + selector
        assert any("clamp(" in body for body in bodies), selector


def test_section_paddings_use_fluid_clamp():
    for selector in SECTIONS:
        bodies = blocks_for(selector)
        assert bodies, "missing section rule: " + selector
        assert any("clamp(" in body and "padding" in body for body in bodies), selector


def test_main_padding_uses_fluid_clamp():
    bodies = [body for body in blocks_for(".main") if "padding" in body]
    assert bodies, "no .main padding rule found"
    assert all("clamp(" in body for body in bodies), bodies
