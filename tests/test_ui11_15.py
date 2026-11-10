import io
from datetime import date

import pytest

from src.app import create_app
from src.db import get_conn
from src.prefs import get_pref
from src.views.feedback import outbox


@pytest.fixture
def client(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    return app.test_client()


def referral_block(html):
    block = html[html.index('id="referral-block"'):]
    return block[: block.index("</section>")]


def test_ui11_about_is_its_own_nav_item_and_route(client, db_path):
    for path in ("/", "/portfolio", "/settings"):
        html = client.get(path).get_data(as_text=True)
        assert '<a href="/about">About</a>' in html, path
    assert client.get("/about").status_code == 200


def test_ui11_about_blocks_all_render(client, db_path):
    html = client.get("/about").get_data(as_text=True)
    for block in (
        "about-hero",
        "developer-block",
        "source-block",
        "updates-block",
        "license-block",
        "support-block",
    ):
        assert f'id="{block}"' in html
    assert "Divakaran" in html
    assert "Adi-Mudi" in html
    assert "github.com/Adi-Mudi/dk-bond-tracker" in html
    assert 'id="repo-link"' in html
    assert 'id="check-updates"' in html
    assert 'id="toggle-auto-updates"' in html
    assert 'id="whats-new-link"' in html
    assert "MIT License" in html
    assert 'id="about-version-chip"' in html


def test_ui11_placeholders_are_clearly_marked(client, db_path):
    html = client.get("/about").get_data(as_text=True)
    assert "LICENSE file to be added" in html
    assert "example.invalid" not in html
    assert "PLACEHOLDER-referral-link" not in html


def test_ui11_referral_link_left_empty_until_owner_supplies_url(client, db_path):
    html = client.get("/about").get_data(as_text=True)
    disclosure = "I may earn a commission from purchases made through these links"
    assert disclosure in html
    block = referral_block(html)
    assert 'id="referral-link"' not in block, "no link until the real URL arrives"
    assert "example.invalid" not in block
    assert "<footer" not in block


def test_ui11_update_check_records_and_persists(client, db_path):
    response = client.post("/about", data={"action": "check"}, follow_redirects=True)
    assert response.status_code == 200
    with get_conn(db_path) as conn:
        assert get_pref(conn, "update_last_checked") == date.today().isoformat()
    assert "Update check done" in response.get_data(as_text=True)


def test_ui11_auto_update_toggle_persists(client, db_path):
    client.post("/about", data={"action": "auto", "auto": "on"}, follow_redirects=False)
    with get_conn(db_path) as conn:
        assert get_pref(conn, "update_auto_check") == "1"
    response = client.post("/about", data={"action": "auto"}, follow_redirects=True)
    with get_conn(db_path) as conn:
        assert get_pref(conn, "update_auto_check") == "0"
    assert "Auto-check: OFF" in response.get_data(as_text=True)


def test_ui15_feedback_is_its_own_nav_item_and_route(client, db_path):
    html = client.get("/").get_data(as_text=True)
    assert '<a href="/feedback">Feedback</a>' in html
    assert client.get("/feedback").status_code == 200


def test_ui15_type_switch_shows_only_that_types_fields(client, db_path):
    bug = client.get("/feedback?type=bug").get_data(as_text=True)
    assert 'id="fb-what-happened"' in bug
    assert 'id="fb-steps"' in bug
    assert 'id="fb-expected"' in bug
    assert 'id="fb-severity"' in bug
    assert 'id="fb-problem"' not in bug
    assert 'id="fb-question"' not in bug

    feature = client.get("/feedback?type=feature").get_data(as_text=True)
    assert 'id="fb-problem"' in feature
    assert 'id="fb-solution"' in feature
    assert 'id="fb-steps"' not in feature
    assert 'id="fb-severity"' not in feature

    question = client.get("/feedback?type=question").get_data(as_text=True)
    assert 'id="fb-question"' in question
    assert 'id="fb-steps"' not in question

    assert "Bug report" in bug
    assert "Feature request" in bug
    assert "type-question" in bug


def test_ui15_each_type_has_at_most_six_required_fields(client, db_path):
    for kind in ("bug", "feature", "question"):
        html = client.get(f"/feedback?type={kind}").get_data(as_text=True)
        start = html.index('id="feedback-form"')
        form = html[start : html.index("</form>", start)]
        assert 1 <= form.count("required") <= 6, kind


def test_ui15_screenshot_upload_with_preview(client, db_path):
    html = client.get("/feedback").get_data(as_text=True)
    assert 'enctype="multipart/form-data"' in html
    assert 'type="file"' in html
    assert 'name="screenshot"' in html
    assert 'id="fb-preview"' in html
    assert "readAsDataURL" in html


def test_ui15_context_is_auto_attached_without_user_input(client, db_path):
    html = client.get("/feedback").get_data(as_text=True)
    assert 'id="feedback-context"' in html
    assert "Auto-attached" in html
    assert 'name="context_page"' in html


def test_ui15_email_route_falls_back_to_local_outbox_when_smtp_unconfigured(
    client, db_path, monkeypatch
):
    monkeypatch.delenv("SMTP_USER", raising=False)
    response = client.post(
        "/feedback?type=question",
        data={"type": "question", "title": "Offline ask", "question": "Why?", "route": "email"},
        follow_redirects=False,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'id="feedback-confirmation"' in html
    assert "Saved locally" in html
    queued = outbox(db_path)
    assert len(queued) == 1
    assert queued[0]["title"] == "Offline ask"
    assert "App version" in queued[0]["body"]


def test_ui15_email_route_sends_via_smtp_with_screenshot(client, db_path, monkeypatch):
    calls = []

    def fake_send(subject, body, attachment=None, conn=None):
        calls.append((subject, body, attachment))
        return {"status": "sent"}

    monkeypatch.setattr("src.views.feedback.send_message", fake_send)
    response = client.post(
        "/feedback?type=bug",
        data={
            "type": "bug",
            "title": "Cell bug",
            "what_happened": "Green shows unpaid",
            "steps": "1 open 2 save",
            "expected_actual": "Expected green",
            "severity": "blocking",
            "route": "email",
            "screenshot": (io.BytesIO(b"png-bytes"), "shot.png"),
        },
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert response.status_code == 200
    assert "your report is in" in response.get_data(as_text=True)
    assert len(calls) == 1
    subject, body, attachment = calls[0]
    assert "Cell bug" in subject
    assert "Severity / blocking: blocking" in body
    assert "Green shows unpaid" in body
    assert attachment[0] == "shot.png"
    assert attachment[2] == b"png-bytes"
    assert outbox(db_path) == []


def test_ui15_github_route_prefills_issue_url(client, db_path):
    response = client.post(
        "/feedback?type=feature",
        data={
            "type": "feature",
            "title": "Dark mode",
            "problem": "Night use",
            "solution": "Add dark theme",
            "route": "github",
        },
        follow_redirects=False,
    )
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert "github.com/Adi-Mudi/dk-bond-tracker/issues/new" in html
    assert "title=Dark%20mode" in html
    assert "labels=feature" in html
    assert "Type%3A%20feature" in html


def test_ui15_outbox_retry_flushes_when_email_works(client, db_path, monkeypatch):
    monkeypatch.delenv("SMTP_USER", raising=False)
    client.post(
        "/feedback?type=question",
        data={"type": "question", "title": "Queued ask", "question": "Q?", "route": "email"},
        follow_redirects=False,
    )
    assert len(outbox(db_path)) == 1
    sent = []
    monkeypatch.setattr(
        "src.views.feedback.send_message",
        lambda subject, body, attachment=None, conn=None: sent.append(subject) or {"status": "sent"},
    )
    response = client.post("/feedback/retry", follow_redirects=True)
    assert sent == ["[question] DK Bond Tracker feedback: Queued ask"]
    assert outbox(db_path) == []
    assert "1 sent" in response.get_data(as_text=True)


def test_ui15_validation_error_is_named(client, db_path):
    response = client.post(
        "/feedback?type=bug",
        data={"type": "bug", "title": "", "route": "email"},
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert b"ERR-feedback" in response.data
    assert b"Title is required" in response.data


def test_ui15_confirmation_screen_explains_next_steps(client, db_path, monkeypatch):
    monkeypatch.setattr(
        "src.views.feedback.send_message",
        lambda subject, body, attachment=None, conn=None: {"status": "sent"},
    )
    response = client.post(
        "/feedback?type=question",
        data={"type": "question", "title": "Ask", "question": "How?", "route": "email"},
        follow_redirects=False,
    )
    html = response.get_data(as_text=True)
    assert 'id="confirmation-title"' in html
    assert "your report is in" in html
    assert "track progress on GitHub Issues" in html
    assert 'id="feedback-again"' in html
