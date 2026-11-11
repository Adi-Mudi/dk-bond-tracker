import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"

ASSET_REF = re.compile(r'(?:href|src)="(/static/[^"?]+\.(?:css|js))(\?[^"]*)?"')
VERSIONED = re.compile(r"\?v=\d+")


def unversioned_refs(text):
    found = []
    for name, query in ASSET_REF.findall(text):
        if not query or not VERSIONED.fullmatch(query):
            found.append(name + (query or ""))
    return found


def test_guard_rejects_unversioned_sample():
    sample = '<link rel="stylesheet" href="/static/theme.css">'
    assert unversioned_refs(sample) == ["/static/theme.css"]
    good = '<link rel="stylesheet" href="/static/theme.css?v=3">'
    assert unversioned_refs(good) == []


def test_guard_rejects_other_query_strings():
    sample = '<script src="/static/app.js?cache=1"></script>'
    assert unversioned_refs(sample) == ["/static/app.js?cache=1"]


def test_every_template_asset_reference_is_cache_busted():
    offenders = []
    for template in sorted(TEMPLATES.glob("*.html")):
        hits = unversioned_refs(template.read_text(encoding="utf-8"))
        offenders.extend(f"{template.name}: {hit}" for hit in hits)
    assert offenders == []


def test_base_template_versions_core_assets():
    base = (TEMPLATES / "base.html").read_text(encoding="utf-8")
    for asset in ("theme.css", "guide.css", "theme.js", "app.js", "guide.js"):
        assert f"/static/{asset}?v=" in base, asset
