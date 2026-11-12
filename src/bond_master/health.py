from __future__ import annotations

from dataclasses import dataclass

from .base import FAILURE_OK, SOURCE_PRIORITY


@dataclass(frozen=True)
class SourceEvent:
    source: str
    isin: str | None
    ok: bool
    failure_code: str
    at: float


@dataclass(frozen=True)
class SourceStatus:
    source: str
    last_success: float | None
    last_failure: float | None
    failure_code: str

    def healthy(self):
        return self.failure_code == FAILURE_OK


class HealthView:
    def __init__(self, events):
        self._events = tuple(events)

    def status(self, source):
        last_success = None
        last_failure = None
        failure_code = FAILURE_OK
        for event in self._events:
            if event.source != source:
                continue
            if event.ok:
                if last_success is None or event.at >= last_success:
                    last_success = event.at
            else:
                failure_code = event.failure_code
                if last_failure is None or event.at >= last_failure:
                    last_failure = event.at
        return SourceStatus(
            source=source,
            last_success=last_success,
            last_failure=last_failure,
            failure_code=failure_code,
        )

    def sources(self):
        names = list(SOURCE_PRIORITY)
        for event in self._events:
            if event.source not in names:
                names.append(event.source)
        return tuple(self.status(name) for name in names)

    def as_dict(self):
        return {
            status.source: {
                "last_success": status.last_success,
                "last_failure": status.last_failure,
                "failure_code": status.failure_code,
            }
            for status in self.sources()
        }


def health_view(service):
    return HealthView(service.events())
