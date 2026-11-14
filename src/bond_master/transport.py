from __future__ import annotations

import urllib.error
import urllib.request

from ..version import APP_VERSION

DEFAULT_TIMEOUT = 10.0
USER_AGENT = f"DK Bond Tracker / {APP_VERSION}"


def http_get(url, timeout=DEFAULT_TIMEOUT):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"HTTP error {exc.code} from the source") from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"could not reach the source: {exc.reason}") from exc
