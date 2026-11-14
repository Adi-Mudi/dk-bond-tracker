import pytest

from src.bond_master import transport as transport_module


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_http_get_returns_the_response_bytes(monkeypatch):
    monkeypatch.setattr(
        transport_module.urllib.request,
        "urlopen",
        lambda request, timeout=None: FakeResponse(b"payload-bytes"),
    )
    assert transport_module.http_get("http://example.invalid/data.csv", 7.5) == b"payload-bytes"


def test_http_get_sends_the_declared_user_agent_and_timeout(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout=None):
        seen["request"] = request
        seen["timeout"] = timeout
        return FakeResponse(b"")

    monkeypatch.setattr(transport_module.urllib.request, "urlopen", fake_urlopen)
    transport_module.http_get("http://example.invalid/data.csv", 3.5)
    request = seen["request"]
    assert request.full_url == "http://example.invalid/data.csv"
    assert request.get_header("User-agent") == transport_module.USER_AGENT
    assert transport_module.USER_AGENT.startswith("DK Bond Tracker / ")
    assert seen["timeout"] == 3.5


def test_http_get_maps_a_url_error_to_connection_error(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise transport_module.urllib.error.URLError("dns failure")

    monkeypatch.setattr(transport_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ConnectionError) as exc_info:
        transport_module.http_get("http://example.invalid/data.csv", 1.0)
    assert "dns failure" in str(exc_info.value)


def test_http_get_maps_an_http_error_to_connection_error(monkeypatch):
    def fake_urlopen(request, timeout=None):
        raise transport_module.urllib.error.HTTPError(request.full_url, 503, "unavailable", {}, None)

    monkeypatch.setattr(transport_module.urllib.request, "urlopen", fake_urlopen)
    with pytest.raises(ConnectionError):
        transport_module.http_get("http://example.invalid/data.csv", 1.0)
