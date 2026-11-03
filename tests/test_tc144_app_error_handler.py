import pytest

from src.app import create_app
from src.validators import AppError


def make_client(db_path, code):
    app = create_app(str(db_path))

    @app.route("/_raise")
    def raise_error():
        raise AppError(code, "handler fixture fault")

    app.config["TESTING"] = True
    return app.test_client()


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("ERR-add-insert", 409),
        ("ERR-active-position", 409),
        ("ERR-watch-dup", 409),
        ("ERR-entry-guard", 403),
        ("ERR-date-range", 500),
    ],
)
def test_tc144_app_error_handler_maps_codes_once(db_path, code, expected):
    response = make_client(db_path, code).get("/_raise")
    assert response.status_code == expected
    html = response.get_data(as_text=True)
    assert f"operation: {code}" in html
    assert "handler fixture fault" in html
