from __future__ import annotations

import time

from .base import (
    FAILURE_BLOCKED,
    FAILURE_INVALID_ISIN,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_OK,
    FAILURE_PARSE_ERROR,
    FAILURE_RATE_LIMITED,
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    SOURCE_PRIORITY,
    FetchResult,
)
from .cache import CooldownActive
from .health import SourceEvent
from .normalize import normalize_isin

DEFAULT_RETRIES = 2
DEFAULT_RETRY_BACKOFF = 0.5
DEFAULT_THROTTLE_SECONDS = 1.0
DEFAULT_TIMEOUT = 10.0

_RETRYABLE = (FAILURE_UNREACHABLE, FAILURE_TIMEOUT)

_FAILURE_PRIORITY = (
    FAILURE_TIMEOUT,
    FAILURE_UNREACHABLE,
    FAILURE_BLOCKED,
    FAILURE_RATE_LIMITED,
    FAILURE_PARSE_ERROR,
    FAILURE_MALFORMED,
    FAILURE_NOT_FOUND,
    FAILURE_OFFLINE,
    FAILURE_INVALID_ISIN,
    FAILURE_OK,
)

_ADAPTER_CLASS = {
    "NSDL": "NsdlAdapter",
    "RBI": "RbiAdapter",
    "NSE": "NseAdapter",
    "BSE": "BseAdapter",
}


def _dominant_failure(codes):
    for code in _FAILURE_PRIORITY:
        if code in codes:
            return code
    return FAILURE_NOT_FOUND


def _empty_code(failure_code):
    return FAILURE_NOT_FOUND if failure_code == FAILURE_OK else failure_code


class BondMasterService:
    def __init__(
        self,
        adapters,
        cache,
        clock=None,
        sleep=None,
        retries=DEFAULT_RETRIES,
        retry_backoff=DEFAULT_RETRY_BACKOFF,
        throttle_seconds=DEFAULT_THROTTLE_SECONDS,
    ):
        self._adapters = dict(adapters)
        self._cache = cache
        self._clock = clock or time.time
        self._sleep = sleep or time.sleep
        self.retries = retries
        self.retry_backoff = retry_backoff
        self.throttle_seconds = throttle_seconds
        self._last_request_at = None
        self._events = []

    def events(self):
        return tuple(self._events)

    def sources(self):
        return tuple(name for name in SOURCE_PRIORITY if name in self._adapters)

    def lookup(self, isin):
        normalized = normalize_isin(isin)
        if normalized is None:
            return FetchResult(isin=isin, failure_code=FAILURE_INVALID_ISIN)
        cached = self._cached_answer(normalized)
        if cached is not None:
            return cached
        if not self._claim_refresh():
            return FetchResult(isin=normalized, failure_code=FAILURE_RATE_LIMITED)
        failures = []
        for source in SOURCE_PRIORITY:
            adapter = self._adapters.get(source)
            if adapter is None:
                continue
            result = self._fetch_session(source, normalized, adapter)
            if result.has_facts():
                self._record(source, normalized, True, result.failure_code)
                return result
            code = _empty_code(result.failure_code)
            failures.append((source, code))
            self._record(source, normalized, False, code)
        return self._total_failure(normalized, failures)

    def _cached_answer(self, isin):
        failures = []
        for source in SOURCE_PRIORITY:
            cached = self._cache.session_result(source, isin)
            if cached is None:
                continue
            if cached.has_facts():
                return cached
            failures.append((source, cached.failure_code))
        if failures:
            return self._total_failure(isin, failures)
        return None

    def _claim_refresh(self):
        try:
            self._cache.begin_refresh()
            return True
        except CooldownActive:
            return False

    def _fetch_session(self, source, isin, adapter):
        cached = self._cache.session_result(source, isin)
        if cached is not None:
            return cached

        def fetcher():
            self._throttle()
            return self._attempt(source, isin, adapter)

        return self._cache.fetch_session(source, isin, fetcher)

    def _attempt(self, source, isin, adapter):
        attempt = 0
        while True:
            result = self._safe_fetch(adapter, isin)
            if result.failure_code not in _RETRYABLE or attempt >= self.retries:
                return result
            attempt += 1
            self._pause(self.retry_backoff * attempt)

    def _safe_fetch(self, adapter, isin):
        try:
            result = adapter.fetch(isin)
        except TimeoutError:
            return FetchResult(isin=isin, failure_code=FAILURE_TIMEOUT)
        except Exception:
            return FetchResult(isin=isin, failure_code=FAILURE_UNREACHABLE)
        if not isinstance(result, FetchResult):
            return FetchResult(isin=isin, failure_code=FAILURE_MALFORMED)
        return result

    def _throttle_wait(self):
        if self.throttle_seconds <= 0 or self._last_request_at is None:
            return 0.0
        return max(0.0, self.throttle_seconds - (self._clock() - self._last_request_at))

    def _throttle(self):
        wait = self._throttle_wait()
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = self._clock()

    def _pause(self, delay):
        wait = max(delay, self._throttle_wait())
        if wait > 0:
            self._sleep(wait)
        self._last_request_at = self._clock()

    def _record(self, source, isin, ok, failure_code):
        self._events.append(
            SourceEvent(
                source=source,
                isin=isin,
                ok=ok,
                failure_code=failure_code,
                at=self._clock(),
            )
        )

    def _total_failure(self, isin, failures):
        codes = [_empty_code(code) for _, code in failures]
        if codes and all(code == FAILURE_UNREACHABLE for code in codes):
            return FetchResult(isin=isin, failure_code=FAILURE_OFFLINE)
        return FetchResult(isin=isin, failure_code=_dominant_failure(codes))


def default_adapters(transport, timeout=DEFAULT_TIMEOUT):
    from . import bse, nsdl, nse, rbi

    modules = {"NSDL": nsdl, "RBI": rbi, "NSE": nse, "BSE": bse}
    adapters = {}
    for source in SOURCE_PRIORITY:
        adapter_class = getattr(modules[source], _ADAPTER_CLASS[source])
        adapters[source] = adapter_class(transport=transport, timeout=timeout)
    return adapters


def build_default_service(cache, transport, **kwargs):
    return BondMasterService(default_adapters(transport), cache, **kwargs)
