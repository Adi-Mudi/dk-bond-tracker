import sqlite3

from src.app import create_app


def test_tc85_forced_operational_error_renders_error_page(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True

    @app.route("/boom")
    def boom():
        raise sqlite3.OperationalError("disk I/O error")

    response = app.test_client().get("/boom")
    assert response.status_code == 500
    html = response.get_data(as_text=True)
    assert 'id="error-banner"' in html
    assert 'id="error-code"' in html
    assert "operation: ERR-unexpected" in html
    assert "boom" in html
    assert "disk I/O error" in html
    assert "<h1>Internal Server Error</h1>" not in html
    assert "<title>500 Internal Server Error</title>" not in html


def test_tc85_http_exceptions_pass_through_unaffected(db_path):
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    response = app.test_client().get("/no-such-page")
    assert response.status_code == 404
    html = response.get_data(as_text=True)
    assert "ERR-unexpected" not in html
