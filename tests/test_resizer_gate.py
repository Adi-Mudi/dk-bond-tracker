import re
from html.parser import HTMLParser

import pytest

from src.app import create_app

pytestmark = pytest.mark.remote

WIDTHS = (320, 360, 375, 414, 480, 768, 1024, 1440)
CORE_ROUTES = (
    "/",
    "/grid",
    "/portfolio",
    "/watch",
    "/goals",
    "/notifications",
    "/settings",
    "/about",
    "/feedback",
    "/search",
)
SCROLL_CONTAINER_CLASSES = {"table-wrap"}
VOID_TAGS = {
    "area",
    "base",
    "br",
    "col",
    "embed",
    "hr",
    "img",
    "input",
    "link",
    "meta",
    "param",
    "source",
    "track",
    "wbr",
}
WIDTH_DECL = re.compile(r"(?<![\w-])(width|min-width)\s*:\s*([^;}]+)")
MAX_WIDTH = re.compile(r"(?<![\w-])max-width\s*:\s*([0-9.]+)(px|%|vw)")
OVERFLOW_GUARD = re.compile(r"overflow(?:-x)?\s*:\s*(auto|scroll)")
WIDTH_CONDITION = re.compile(r"\(\s*(max|min)-width\s*:\s*(\d+)px\s*\)")
INLINE_STYLE = re.compile(r'style="([^"]*)"')


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


class Element:
    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = attrs
        self.parent = parent
        self.children = []


class TreeBuilder(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Element("#document", {}, None)
        self._stack = [self.root]

    def handle_starttag(self, tag, attrs):
        node = Element(tag, dict(attrs), self._stack[-1])
        self._stack[-1].children.append(node)
        if tag not in VOID_TAGS:
            self._stack.append(node)

    def handle_startendtag(self, tag, attrs):
        node = Element(tag, dict(attrs), self._stack[-1])
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return


def build_tree(html):
    builder = TreeBuilder()
    builder.feed(html)
    return builder.root


def walk(node):
    yield node
    for child in node.children:
        yield from walk(child)


def element_classes(node):
    return (node.attrs.get("class") or "").split()


def inside_scroll_container(node):
    current = node.parent
    while current is not None:
        if SCROLL_CONTAINER_CLASSES.intersection(element_classes(current)):
            return True
        current = current.parent
    return False


def parse_stylesheets(client, html):
    sheets = []
    for match in re.finditer(r"<style[^>]*>(.*?)</style>|<link[^>]*>", html, re.S):
        if match.group(1) is not None:
            sheets.append(match.group(1))
            continue
        tag = match.group(0)
        href = re.search(r'href="([^"]+)"', tag)
        if href and "stylesheet" in tag:
            response = client.get(href.group(1))
            if response.status_code == 200:
                sheets.append(response.get_data(as_text=True))
    return "\n".join(sheets)


def parse_rules(css, media=None):
    rules = []
    position = 0
    while position < len(css):
        brace = css.find("{", position)
        if brace == -1:
            break
        header = css[position:brace].strip()
        depth = 1
        end = brace + 1
        while end < len(css) and depth:
            if css[end] == "{":
                depth += 1
            elif css[end] == "}":
                depth -= 1
            end += 1
        body = css[brace + 1 : end - 1]
        if header.startswith("@media"):
            nested = f"{media} {header}" if media else header
            rules.extend(parse_rules(body, nested))
        elif not header.startswith("@") and header:
            rules.append((media, header, body))
        position = end
    return rules


def media_applies(media, width):
    if not media:
        return True
    for kind, value in WIDTH_CONDITION.findall(media):
        limit = int(value)
        if kind == "max" and width > limit:
            return False
        if kind == "min" and width < limit:
            return False
    return True


def body_is_guarded(body, width):
    if OVERFLOW_GUARD.search(body):
        return True
    for value, unit in MAX_WIDTH.findall(body):
        if unit in ("%", "vw"):
            return True
        if unit == "px" and float(value) <= width:
            return True
    return False


def px_widths(declarations):
    resolved = {}
    for prop, raw in WIDTH_DECL.findall(declarations):
        resolved[prop] = raw.strip()
    return [
        (prop, int(raw[:-2]))
        for prop, raw in resolved.items()
        if re.fullmatch(r"\d+px", raw)
    ]


def winning_widths(css, width):
    resolved = {}
    for media, selectors, body in parse_rules(css):
        if not media_applies(media, width):
            continue
        for selector in selectors.split(","):
            selector = selector.strip()
            if not selector:
                continue
            for prop, raw in WIDTH_DECL.findall(body):
                resolved[(selector, prop)] = (raw.strip(), body)
    return resolved


def simple_token_matches(token, node):
    if token.startswith("#"):
        return node.attrs.get("id") == token[1:]
    if token.startswith("."):
        return token[1:] in element_classes(node)
    return node.tag == token


def selector_matches(selector, node):
    last = selector.strip().split()[-1]
    last = re.sub(r"\[[^\]]*\]", "", last)
    last = re.sub(r"::?[\w-]+(\([^)]*\))?", "", last)
    tokens = re.findall(r"[.#]?[\w-]+", last)
    return bool(tokens) and all(simple_token_matches(token, node) for token in tokens)


def selector_is_contained(selector, root):
    matched = [node for node in walk(root) if selector_matches(selector, node)]
    return all(inside_scroll_container(node) for node in matched)


def overflow_findings(client, html, width):
    root = build_tree(html)
    css = parse_stylesheets(client, html)
    findings = []
    for (selector, prop), (raw, body) in winning_widths(css, width).items():
        match = re.fullmatch(r"(\d+)px", raw)
        if not match:
            continue
        pixels = int(match.group(1))
        if pixels <= width:
            continue
        if body_is_guarded(body, width):
            continue
        if selector_is_contained(selector, root):
            continue
        findings.append(f"{selector} {{{prop}: {pixels}px}} at {width}px")
    return findings


@pytest.mark.parametrize("width", WIDTHS)
def test_core_routes_render_at_every_width(client, width):
    for route in CORE_ROUTES:
        assert client.get(route).status_code == 200, (route, width)


def test_viewport_meta_declares_device_width_on_core_routes(client):
    for route in CORE_ROUTES:
        html = client.get(route).get_data(as_text=True)
        assert re.search(r'<meta[^>]*name="viewport"[^>]*content="width=device-width[^"]*"', html), route


@pytest.mark.parametrize("width", WIDTHS)
def test_no_effective_fixed_content_width_exceeds_viewport(client, width):
    for route in CORE_ROUTES:
        html = client.get(route).get_data(as_text=True)
        findings = overflow_findings(client, html, width)
        assert not findings, (route, findings)


@pytest.mark.parametrize("width", WIDTHS)
def test_no_inline_fixed_width_exceeds_viewport(client, width):
    for route in CORE_ROUTES:
        html = client.get(route).get_data(as_text=True)
        for match in INLINE_STYLE.finditer(html):
            style = match.group(1)
            for prop, pixels in px_widths(style):
                assert pixels <= width or body_is_guarded(style, width), (route, width, prop, pixels)


def test_every_table_sits_inside_a_horizontal_scroll_container(client):
    for route in CORE_ROUTES:
        root = build_tree(client.get(route).get_data(as_text=True))
        for node in walk(root):
            if node.tag == "table":
                assert inside_scroll_container(node), route


def test_gate_flags_an_unguarded_fixed_width(client):
    html = (
        "<!doctype html><html><head><style>.wide-only { width: 4800px; }</style></head>"
        '<body><div class="wide-only">x</div></body></html>'
    )
    findings = overflow_findings(client, html, 320)
    assert findings, "an unguarded fixed width must be reported"
    assert "wide-only" in findings[0]


def test_gate_ignores_a_guarded_fixed_width(client):
    html = (
        "<!doctype html><html><head>"
        "<style>.ok-only { width: 4800px; overflow-x: auto; }</style></head>"
        '<body><div class="ok-only">x</div></body></html>'
    )
    assert overflow_findings(client, html, 320) == []


def test_gate_ignores_a_width_inside_a_scroll_container(client):
    html = (
        "<!doctype html><html><head>"
        "<style>#inside-table { min-width: 4800px; }</style></head>"
        '<body><div class="table-wrap"><table id="inside-table"></table></div></body></html>'
    )
    assert overflow_findings(client, html, 320) == []
