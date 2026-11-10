import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "static"
TEMPLATES = ROOT / "src" / "templates"

STRUCTURAL_DECL = re.compile(
    r"(?<![\w-])(width|min-width|max-width|margin-left|margin-right)\s*:\s*([^;{}]+)"
)
PX_VALUE = re.compile(r"^\s*([0-9]*\.?[0-9]+)px\s*$")
STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
INLINE_STYLE = re.compile(r'style="([^"]*)"')

ALLOWLIST = {
    ("src/static/theme.css", ".swatch", "width", 12.0),
    ("src/static/theme.css", ".check-row input", "width", 16.0),
    ("src/static/theme.css", ".bell-badge-v3", "min-width", 18.0),
    ("src/templates/base.html", ".brand-mark", "width", 24.0),
    ("src/templates/grid.html", ".grid-legend .swatch", "width", 14.0),
    ('src/templates/payment_edit.html', '.field input[type="checkbox"]', "width", 16.0),
    ("src/templates/portfolio.html", ".check-inline input", "width", 14.0),
    ("src/templates/share.html", ".share-checks input", "width", 16.0),
}

GRID_TARGETS = (
    ("src/static/theme.css", ".stat-row"),
    ("src/static/theme.css", ".form-grid"),
    ("src/templates/watch.html", ".facts-grid"),
)

DEAD_TOKENS = ("status-legend", "legend-chip", "disclaimer-line")


def parse_rules(css):
    rules = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def scan(text):
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
                scan(body)
            elif header:
                rules.append((header, body))
            pos = end

    scan(css)
    return rules


def px_offsets(relpath, css):
    found = []
    for header, body in parse_rules(css):
        for part in header.split(","):
            selector = " ".join(part.split())
            if not selector:
                continue
            for prop, raw in STRUCTURAL_DECL.findall(body):
                match = PX_VALUE.match(raw)
                if match:
                    found.append((relpath, selector, prop, float(match.group(1))))
    return found


def px_offsets_inline(relpath, fragment):
    found = []
    for prop, raw in STRUCTURAL_DECL.findall(fragment):
        match = PX_VALUE.match(raw)
        if match:
            found.append((relpath, "[inline]", prop, float(match.group(1))))
    return found


def css_text(relpath):
    path = ROOT / relpath
    if path.suffix == ".css":
        return path.read_text(encoding="utf-8")
    return "\n".join(STYLE_BLOCK.findall(path.read_text(encoding="utf-8")))


def blocks_for(relpath, selector):
    bodies = []
    for header, body in parse_rules(css_text(relpath)):
        for part in header.split(","):
            if " ".join(part.split()) == selector:
                bodies.append(body)
    return bodies


def scanned_px_offsets():
    found = []
    for path in sorted(STATIC.glob("*.css")):
        relpath = str(path.relative_to(ROOT))
        found.extend(px_offsets(relpath, path.read_text(encoding="utf-8")))
    for path in sorted(TEMPLATES.glob("*.html")):
        relpath = str(path.relative_to(ROOT))
        html = path.read_text(encoding="utf-8")
        for block in STYLE_BLOCK.findall(html):
            found.extend(px_offsets(relpath, block))
        for attr in INLINE_STYLE.findall(html):
            found.extend(px_offsets_inline(relpath, attr))
    return found


def test_sweep_flags_an_unallowlisted_fixed_width():
    found = px_offsets("src/static/theme.css", ".ghost { width: 333px; }")
    assert found == [("src/static/theme.css", ".ghost", "width", 333.0)]


def test_sweep_flags_an_unallowlisted_fixed_margin():
    found = px_offsets("src/static/theme.css", ".ghost { margin-left: 220px; }")
    assert found == [("src/static/theme.css", ".ghost", "margin-left", 220.0)]


def test_sweep_permits_an_allowlisted_icon_width():
    found = px_offsets("src/static/theme.css", ".swatch { width: 12px; }")
    assert found and found[0] in ALLOWLIST


def test_sweep_ignores_non_structural_declarations_and_rem_values():
    css = (
        ".x { padding: 24px; height: 48px; width: 10rem; max-width: 80vw;"
        " margin: 8px 0 0 20px; margin-left: auto; margin-right: 0; }"
    )
    assert px_offsets("src/static/theme.css", css) == []


def test_sweep_ignores_media_conditions():
    css = "@media (max-width: 768px) { .y { width: 100%; } }"
    assert px_offsets("src/static/theme.css", css) == []


def test_sweep_reads_the_known_icon_allowlist():
    found = set(scanned_px_offsets())
    assert found & ALLOWLIST, "no allowlisted hits found - the sweep may have stopped reading files"


def test_no_structural_fixed_px_outside_allowlist():
    offenders = [hit for hit in scanned_px_offsets() if hit not in ALLOWLIST]
    assert not offenders, offenders


def test_grid_skeletons_use_auto_fit_minmax():
    for relpath, selector in GRID_TARGETS:
        bodies = blocks_for(relpath, selector)
        assert bodies, (relpath, selector)
        assert any("auto-fit" in body and "minmax(" in body for body in bodies), (relpath, selector)


def test_removed_component_css_is_gone():
    text = "\n".join(css_text(str(p.relative_to(ROOT))) for p in sorted(STATIC.glob("*.css")))
    text += "\n" + "\n".join(p.read_text(encoding="utf-8") for p in sorted(TEMPLATES.glob("*.html")))
    for token in DEAD_TOKENS:
        assert token not in text, token
