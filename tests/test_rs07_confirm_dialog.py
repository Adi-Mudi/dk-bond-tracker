from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = ROOT / "src" / "templates"
PAGES = ("portfolio.html", "portfolio_detail.html")
DIALOG = (TEMPLATES / "_confirm_dialog.html").read_text(encoding="utf-8")


def test_rs07_no_window_confirm_left_in_portfolio_pages():
    for name in PAGES:
        assert "window.confirm(" not in (TEMPLATES / name).read_text(encoding="utf-8"), name


def test_rs07_both_pages_use_shared_dialog():
    for name in PAGES:
        text = (TEMPLATES / name).read_text(encoding="utf-8")
        assert '{% include "_confirm_dialog.html" %}' in text, name
        assert "window.appConfirm(result.data.message" in text, name


def test_rs07_dialog_markup_contract():
    for hook in (
        'id="app-confirm"',
        'role="alertdialog"',
        'id="app-confirm-title"',
        'id="app-confirm-body"',
        'id="app-confirm-cancel"',
        'id="app-confirm-accept"',
        "window.appConfirm = function",
    ):
        assert hook in DIALOG, hook
    assert ">OK<" not in DIALOG


def test_rs07_confirm_path_runs_the_refresh_request():
    assert "refreshIsin(button, url, true);" in (TEMPLATES / "portfolio.html").read_text(encoding="utf-8")
    assert "refreshFacts(url, true);" in (TEMPLATES / "portfolio_detail.html").read_text(encoding="utf-8")
    assert "next();" in DIALOG


def test_rs07_cancel_path_sends_nothing():
    assert 'cancel.addEventListener("click", closeDialog);' in DIALOG
    closing = DIALOG.split("function closeDialog()", 1)[1].split("window.appConfirm", 1)[0]
    assert "fetch(" not in closing
    assert "pending = null" in closing
