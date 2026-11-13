import src.app as app_module
from src.app import create_app
from src.bond_master import service as service_module
from src.bond_master import transport as transport_module


class _NoopService:
    def refresh(self, isin):
        return None

    def events(self):
        return ()


def test_create_app_wires_the_real_http_transport(db_path, monkeypatch):
    monkeypatch.setattr(app_module, "http_get", transport_module.http_get)
    app = create_app(str(db_path))
    wired = app.config.get("BOND_MASTER_TRANSPORT")
    assert wired is transport_module.http_get
    assert callable(wired)


def _capture(seen):
    def fake_build(cache, transport, **kwargs):
        seen["transport"] = transport
        return _NoopService()

    return fake_build


def test_refresh_all_passes_an_explicit_transport_through(db_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(service_module, "build_default_service", _capture(seen))
    sender = lambda url, timeout: b""
    service_module.refresh_all(str(db_path), trigger="manual", transport=sender)
    assert seen["transport"] is sender


def test_refresh_all_defaults_to_no_transport(db_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(service_module, "build_default_service", _capture(seen))
    service_module.refresh_all(str(db_path), trigger="manual")
    assert seen["transport"] is None


def test_manual_refresh_route_uses_the_configured_transport(db_path, monkeypatch):
    monkeypatch.setattr(app_module, "_auto_refresh_started", True)
    app = create_app(str(db_path))
    app.config["TESTING"] = True
    sender = lambda url, timeout: b""
    app.config["BOND_MASTER_TRANSPORT"] = sender
    seen = {}

    def fake_refresh_all(db_file, trigger="manual", transport=None):
        seen["transport"] = transport
        return {"NSDL": {"status": "ok", "failure_code": "OK", "as_of": None}}

    monkeypatch.setattr(service_module, "refresh_all", fake_refresh_all)
    response = app.test_client().post("/watch/refresh")
    assert response.status_code == 200
    assert seen["transport"] is sender


def test_startup_auto_refresh_receives_the_configured_transport(db_path, monkeypatch):
    seen = {}
    monkeypatch.setattr(app_module, "_auto_refresh_started", False)
    monkeypatch.setattr(
        app_module,
        "_start_auto_refresh",
        lambda db_file, transport: seen.update(transport=transport) or None,
    )
    app = create_app(str(db_path))
    assert seen["transport"] is app.config["BOND_MASTER_TRANSPORT"]
