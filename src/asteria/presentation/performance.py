"""A frame budget and the diagnosis a presentation clip gets against it (the fidelity editor)."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FrameBudget:
    target_ms: float = 16.667
    max_events: int = 4096
    max_layers: int = 4096

    def __post_init__(self):
        if min(self.target_ms, self.max_events, self.max_layers) <= 0:
            raise ValueError("invalid budget")


@dataclass(frozen=True, slots=True)
class FrameDiagnostics:
    event_count: int
    layer_count: int
    estimated_work: int
    over_budget: bool
    notes: tuple = ()


def diagnose(events, layers, budget=FrameBudget()):
    n = []
    if events > budget.max_events:
        n.append("event_dispatch_pressure")
    if layers > budget.max_layers:
        n.append("layer_submission_pressure")
    return FrameDiagnostics(events, layers, events + layers, bool(n), tuple(n))
