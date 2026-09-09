from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class TimeState:
    """Per-frame timing state owned by the application."""

    delta_seconds: float = 0.0
    elapsed_seconds: float = 0.0
    frame_index: int = 0

    def advance(self, delta_seconds: float) -> None:
        if delta_seconds < 0:
            raise ValueError("delta_seconds must be >= 0")
        self.delta_seconds = delta_seconds
        self.elapsed_seconds += delta_seconds
        self.frame_index += 1
