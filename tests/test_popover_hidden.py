from pathlib import Path


def test_popover_hidden_css_override_exists():
    css = Path("src/static/guide.css").read_text(encoding="utf-8")
    assert ".guide-popover[hidden]" in css
    assert ".why-popover[hidden]" in css
    block_start = css.index(".guide-popover[hidden]")
    block = css[block_start : css.index("}", block_start)]
    assert "display: none" in block


def test_popover_markup_uses_hidden_attribute():
    base = Path("src/templates/base.html").read_text(encoding="utf-8")
    assert 'id="whyBonds" role="dialog"' in base and "hidden>" in base.split('id="whyBonds"', 1)[1][:200]
    assert 'id="pageGuide"' in base
