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


BASE_HTML = TEMPLATES / "base.html"
BOTTOM_TABS = re.compile(r'<nav class="bottom-tabs".*?</nav>', re.S)
UNICODE_GLYPHS = ("&#9638;", "&#9636;", "&#9678;", "&#9670;", "&#9776;")


def test_viewport_meta_has_viewport_fit_cover():
    html = BASE_HTML.read_text(encoding="utf-8")
    match = re.search(r'<meta name="viewport" content="([^"]*)"', html)
    assert match and "viewport-fit=cover" in match.group(1)


def test_bottom_tabs_respect_safe_area_inset():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    bodies = [body for header, body in _rules(css) if header == ".bottom-tabs"]
    assert any("env(safe-area-inset-bottom)" in body for body in bodies)


def test_bottom_tabs_use_svg_icons_not_unicode_glyphs():
    html = BASE_HTML.read_text(encoding="utf-8")
    block = BOTTOM_TABS.search(html)
    assert block, "bottom-tabs nav not found"
    tabs = block.group(0)
    for glyph in UNICODE_GLYPHS:
        assert glyph not in tabs
    assert tabs.count("<svg") == 5
    assert tabs.count('aria-hidden="true"') >= 5


def test_mobile_hides_drawer_button_below_768px():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    assert re.search(
        r"@media \(max-width:\s*767px\)\s*\{\s*\.drawer-btn\s*\{\s*display:\s*none",
        css,
    )


def test_interactive_controls_have_focus_visible_rings():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    focus_rules = [header for header, _ in _rules(css) if ":focus-visible" in header]
    assert focus_rules, "no :focus-visible rules in theme.css"
    joined = " ".join(focus_rules)
    for tag in INTERACTIVE:
        assert re.search(rf"(^|[\s,]){tag}:focus-visible", joined), f"no focus ring for {tag}"


LAYER_DECLARATION = "@layer base, components, templates, overrides;"


def _strip_layer_wrapper(css, layer):
    stripped = css.strip()
    opener = f"@layer {layer} {{"
    assert stripped.startswith(opener), f"not wrapped in @layer {layer}"
    assert stripped.endswith("}"), f"@layer {layer} wrapper not closed"
    return stripped[len(opener):-1]


def test_theme_declares_cascade_layer_order_first():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    assert css.splitlines()[0].strip() == LAYER_DECLARATION


def test_theme_body_is_wrapped_in_components_layer():
    css = (STATIC / "theme.css").read_text(encoding="utf-8")
    body = css.split(LAYER_DECLARATION, 1)[1].split("@layer overrides {", 1)[0]
    assert _rules(_strip_layer_wrapper(body, "components")), "components layer has no rules"


def test_every_template_style_block_is_wrapped_in_templates_layer():
    wrapped = 0
    for path in sorted(TEMPLATES.glob("*.html")):
        for block in STYLE_BLOCK.findall(path.read_text(encoding="utf-8")):
            body = block.strip()
            if not body:
                continue
            if body.startswith(LAYER_DECLARATION):
                body = body[len(LAYER_DECLARATION):]
            _strip_layer_wrapper(body, "templates")
            wrapped += 1
    assert wrapped >= 16, f"expected 16 layered template style blocks, found {wrapped}"


def test_no_unlayered_top_level_rules_remain():
    for path in [STATIC / "theme.css", STATIC / "guide.css"]:
        css = re.sub(r"/\*.*?\*/", "", path.read_text(encoding="utf-8"), flags=re.S)
        depth = 0
        for line in css.splitlines():
            stripped = line.strip()
            if depth == 0 and stripped:
                assert stripped.startswith("@layer"), f"unlayered top-level content in {path.name}: {stripped[:60]}"
            depth += line.count("{") - line.count("}")
        assert depth == 0, f"unbalanced braces in {path.name}"
