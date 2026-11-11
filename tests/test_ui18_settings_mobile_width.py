import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = ROOT / "src" / "templates" / "settings.html"

STYLE_BLOCK = re.compile(r"<style[^>]*>(.*?)</style>", re.S)
MOBILE_QUERY = re.compile(r"@media\s*\(\s*max-width\s*:\s*768px\s*\)")
DECLARATION = re.compile(r"(?<![\w-])([\w-]+)\s*:\s*([^;{}]+)")


def top_level_blocks(css):
    blocks = []
    pos = 0
    while pos < len(css):
        brace = css.find("{", pos)
        if brace == -1:
            break
        header = css[pos:brace].strip()
        depth = 1
        end = brace + 1
        while end < len(css) and depth:
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
            end += 1
        blocks.append((header, css[brace + 1 : end - 1]))
        pos = end
    return blocks


def declarations(body):
    found = {}
    for prop, value in DECLARATION.findall(body):
        found[prop.strip().lower()] = " ".join(value.split()).lower()
    return found


def rules_in(body):
    rules = {}
    for header, inner in top_level_blocks(body):
        decls = declarations(inner)
        for part in header.split(","):
            selector = " ".join(part.split())
            if not selector:
                continue
            rules.setdefault(selector, {}).update(decls)
    return rules


def inline_css(path):
    text = path.read_text(encoding="utf-8")
    return "\n".join(STYLE_BLOCK.findall(text))


def mobile_rules(css):
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    for header, body in top_level_blocks(css):
        if MOBILE_QUERY.search(header):
            return rules_in(body)
    return {}


def mobile_width_guard(rules):
    layout = rules.get(".settings-layout", {})
    content = rules.get(".settings-content", {})
    return layout.get("align-items") == "stretch" or content.get("width") == "100%"


def test_parser_reads_mobile_block_rules():
    sample = (
        "@media (max-width: 768px) { .settings-layout { flex-direction: column; }"
        " .settings-content { width: 100%; } }"
    )
    rules = mobile_rules(sample)
    assert rules[".settings-layout"]["flex-direction"] == "column"
    assert rules[".settings-content"]["width"] == "100%"


def test_settings_mobile_block_prevents_content_collapse():
    rules = mobile_rules(inline_css(SETTINGS))
    assert rules, "missing @media (max-width: 768px) block in settings.html"
    assert rules.get(".settings-layout", {}).get("flex-direction") == "column"
    assert mobile_width_guard(rules), (
        "settings mobile block must set align-items: stretch on .settings-layout "
        "or width: 100% on .settings-content"
    )


def test_guard_fails_on_sample_without_rule():
    sample = (
        "@media (max-width: 768px) { .settings-layout { flex-direction: column; gap: 10px; }"
        " .settings-nav { width: 100%; } }"
    )
    rules = mobile_rules(sample)
    assert rules, "sample must contain a mobile block"
    assert not mobile_width_guard(rules)


def test_guard_fails_without_mobile_block():
    assert mobile_rules(".settings-layout { display: flex; }") == {}
