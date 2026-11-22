import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "static"
TEMPLATES = ROOT / "src" / "templates"
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
STYLE_GUIDE = ROOT.parent / ".IDE_Plans" / "dk-bond-style-guide.html"
INTERACTIVE = ("button", "input", "select", "a")


def _css_sources():
    for path in sorted(STATIC.glob("*.css")):
        yield path.read_text(encoding="utf-8")
    for path in sorted(TEMPLATES.glob("*.html")):
        for block in STYLE_BLOCK.findall(path.read_text(encoding="utf-8")):
            yield block


def _rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    found = []
    for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        header = " ".join(match.group(1).split())
        found.append((header, match.group(2)))
    return found


def _bodies_for(selector):
    bodies = []
    for css in _css_sources():
        for header, body in _rules(css):
            if selector in [part.strip() for part in header.split(",")]:
                bodies.append(body)
    return bodies


def test_section_titles_are_sentence_case():
    for selector in (".zone-title", ".sec-head", ".feed-group-title"):
        bodies = _bodies_for(selector)
        assert bodies, f"no rule found for {selector}"
        for body in bodies:
            assert not re.search(r"text-transform:\s*uppercase", body), f"{selector} still uppercase"


def test_style_guide_documents_three_rem_controls():
    if not STYLE_GUIDE.exists():
        pytest.skip(".IDE_Plans is gitignored and not present in this checkout")
    html = STYLE_GUIDE.read_text(encoding="utf-8")
    assert "40px tall" not in html
    assert "height: 40px" not in html
    assert "3rem" in html


def test_numeric_table_cells_use_tabular_numerals():
    assert any(
        "tabular-nums" in body for body in _bodies_for(".num")
    ), ".num cells must use tabular-nums"


def test_feedback_pill_gap_is_at_least_8px():
    html = (TEMPLATES / "feedback.html").read_text(encoding="utf-8")
    match = re.search(r"\.feedback-types\s*\{[^}]*gap:\s*(\d+)px", html)
    assert match, ".feedback-types gap not found"
    assert int(match.group(1)) >= 8


def test_html_has_scroll_padding_for_sticky_topbar():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    assert re.search(r"(^|\s)html\s*\{[^}]*scroll-padding-top:\s*4\.5rem", css)


def test_interactive_controls_have_focus_visible_rings():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    focus_rules = [header for header, _ in _rules(css) if ":focus-visible" in header]
    assert focus_rules, "no :focus-visible rules in theme.css"
    joined = " ".join(focus_rules)
    for tag in INTERACTIVE:
        assert re.search(rf"(^|[\s,]){tag}:focus-visible", joined), f"no focus ring for {tag}"
