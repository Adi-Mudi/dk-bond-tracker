from __future__ import annotations

import urllib.error
import urllib.request

from ..version import APP_VERSION

DEFAULT_TIMEOUT = 10.0
_GITHUB_API = "".join(("ht", "tps://api.github.com"))
RELEASE_LATEST_URL = f"{_GITHUB_API}/repos/Adi-Mudi/dk-bond-tracker/releases/latest"
USER_AGENT = f"DK Bond Tracker / {APP_VERSION}"


def github_release_json(url, timeout=DEFAULT_TIMEOUT):
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, b""
    except urllib.error.URLError as exc:
        raise ConnectionError(f"could not reach the source: {exc.reason}") from exc


def http_get(url, timeout=DEFAULT_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"HTTP error {exc.code} from the source") from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"could not reach the source: {exc.reason}") from exc
