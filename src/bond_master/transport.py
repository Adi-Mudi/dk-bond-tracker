from __future__ import annotations

import urllib.error
import urllib.request

DEFAULT_TIMEOUT = 10.0


def http_get(url, timeout=DEFAULT_TIMEOUT):
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise ConnectionError(f"HTTP error {exc.code} from the source") from exc
    except urllib.error.URLError as exc:
        raise ConnectionError(f"could not reach the source: {exc.reason}") from exc
