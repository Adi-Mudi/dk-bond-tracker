from pathlib import Path


def test_confirm_dialog_hidden_override():
    html = Path("src/templates/watch.html").read_text(encoding="utf-8")
    assert ".confirm-dialog[hidden]" in html
    block_start = html.index(".confirm-dialog[hidden]")
    block = html[block_start : html.index("}", block_start)]
    assert "display: none" in block


def test_screenshot_preview_hidden_override():
    html = Path("src/templates/feedback.html").read_text(encoding="utf-8")
    assert ".screenshot-preview[hidden]" in html
    block_start = html.index(".screenshot-preview[hidden]")
    block = html[block_start : html.index("}", block_start)]
    assert "display: none" in block


def test_markup_keeps_hidden_attributes():
    watch = Path("src/templates/watch.html").read_text(encoding="utf-8")
    assert 'id="delete-confirm"' in watch and "hidden>" in watch.split('id="delete-confirm"', 1)[1][:250]
    fb = Path("src/templates/feedback.html").read_text(encoding="utf-8")
    assert 'id="fb-preview"' in fb and "hidden>" in fb.split('id="fb-preview"', 1)[1][:120]
