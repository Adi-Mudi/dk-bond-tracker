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
