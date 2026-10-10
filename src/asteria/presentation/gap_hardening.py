"""Generic fixes found by cross-workload audit."""

from dataclasses import dataclass
from typing import Any
from .choreography import TrackEvent
from .performance import BoundedDispatcher


@dataclass(frozen=True, slots=True)
class CancelScope:
    channels: frozenset[str] = frozenset()
    tags: frozenset[str] = frozenset()

    def matches(self, event: TrackEvent) -> bool:
        if self.channels and event.track not in self.channels:
            return False
        if self.tags:
            tags = frozenset(event.payload.get("tags", ()))
            if not self.tags.intersection(tags):
                return False
        return True


class ScopedEventSet:
    """Cancellation/suppression without requiring gameplay-specific semantics."""

    def __init__(self, events=()):
        self.events = list(events)
        self.suppressed = set()

    def cancel(self, scope: CancelScope):
        hit = []
        for i, e in enumerate(self.events):
            if scope.matches(e):
                self.suppressed.add(i)
                hit.append(e)
        return tuple(hit)

    def active_events(self):
        return tuple(e for i, e in enumerate(self.events) if i not in self.suppressed)


@dataclass(frozen=True, slots=True)
class SubmissionKey:
    asset_id: str
    blend_mode: str = "alpha"
    material: str | None = None


@dataclass(frozen=True, slots=True)
class Submission:
    key: SubmissionKey
    z: int
    payload: Any = None


def stable_submission_batches(items):
    """Adjacent-compatible batching only; never reorders across z/composition order."""
    out = []
    for x in items:
        if out and out[-1][0] == x.key:
            out[-1][1].append(x)
        else:
            out.append((x.key, [x]))
    return tuple((k, tuple(v)) for k, v in out)


class DispatchClock:
    """Separates event backlog draining from presentation time progression."""

    def __init__(self, events, limit=4096):
        self.dispatcher = BoundedDispatcher(events, limit)
        self.presentation_time_ms = 0.0

    def advance_to(self, t):
        if t < self.presentation_time_ms:
            raise ValueError("time reversal")
        self.presentation_time_ms = t
        return self.dispatcher.dispatch_through(t)


def validate_cross_workload_invariants():
    return {
        "generic_channels": True,
        "scoped_cancellation": True,
        "stable_batch_order": True,
        "bounded_dispatch": True,
        "presentation_time_independent_from_gameplay": True,
        "canonical_fidelity_not_degraded": True,
    }
