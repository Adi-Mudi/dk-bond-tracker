import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDE_CSS = ROOT / "src" / "static" / "guide.css"
THEME_CSS = ROOT / "src" / "static" / "theme.css"

WRAPPER_RELATIVE_MAX = re.compile(
    r"(?<![\w-])max-width\s*:\s*100%\s*[;}]"
)


def parse_rules(css):
    rules = []
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)

    def scan(text, media):
        pos = 0
        while pos < len(text):
            brace = text.find("{", pos)
            if brace == -1:
                break
            header = " ".join(text[pos:brace].split())
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
                scan(body, header if header.startswith("@media") else media)
            elif header:
                rules.append((header, body, media))
            pos = end

    scan(css, "")
    return rules


def blocks_for(rules, selector, media=None):
    found = []
    for header, body, at in rules:
        if media is not None and at != media:
            continue
        for part in header.split(","):
            if " ".join(part.split()) == selector:
                found.append(body)
                break
    return found


def declares(body, prop, value):
    pattern = re.compile(
        r"(?<![\w-])" + re.escape(prop) + r"\s*:\s*" + re.escape(value) + r"\s*(?:;|})"
    )
    return bool(pattern.search(body + "}"))


def search_panel_guard(css_text):
    rules = parse_rules(css_text)
    base = blocks_for(rules, ".search-panel", media="")
    if not base:
        return False
    if any(WRAPPER_RELATIVE_MAX.search(body) for body in base):
        return False
    if not any("92vw" in body for body in base):
        return False
    mobile = [
        body
        for media, body in (
            (at, body)
            for header, body, at in rules
            if header == ".search-panel" and at
        )
        if "768px" in media
    ]
    if not mobile:
        return False
    return all(
        declares(body, "position", "fixed")
        and declares(body, "left", "0.5rem")
        and declares(body, "right", "0.5rem")
        and declares(body, "width", "auto")
        for body in mobile
    )


def overflow_panel_guard(css_text):
    rules = parse_rules(css_text)
    base = blocks_for(rules, ".overflow-panel", media="")
    if not base:
        return False
    if any(WRAPPER_RELATIVE_MAX.search(body) for body in base):
        return False
    return any("90vw" in body for body in base)


def test_parser_reads_media_scoped_blocks():
    sample = "@media (max-width: 768px) { .search-panel { position: fixed; } }"
    rules = parse_rules(sample)
    assert rules[0][2] == "@media (max-width: 768px)"
    assert declares(rules[0][1], "position", "fixed")


def test_guard_rejects_wrapper_relative_max_width():
    bad = ".search-panel { width: min(26rem, 92vw); max-width: 100%; }"
    assert search_panel_guard(bad) is False
    good = (
        ".search-panel { width: min(26rem, 92vw); max-width: 92vw; }"
        "@media (max-width: 768px) { .search-panel { position: fixed; left: 0.5rem;"
        " right: 0.5rem; top: 3.75rem; width: auto; max-width: none; } }"
    )
    assert search_panel_guard(good) is True


def test_guard_rejects_missing_mobile_anchor():
    no_mobile = ".search-panel { width: min(26rem, 92vw); max-width: 92vw; }"
    assert search_panel_guard(no_mobile) is False


def test_search_panel_cannot_collapse_to_the_icon_width():
    css = GUIDE_CSS.read_text(encoding="utf-8")
    assert search_panel_guard(css) is True


def test_overflow_panel_is_not_clamped_to_its_icon_wrapper():
    css = THEME_CSS.read_text(encoding="utf-8")
    assert overflow_panel_guard(css) is True
    assert overflow_panel_guard(".overflow-panel { width: min(20rem, 90vw); max-width: 100%; }") is False
