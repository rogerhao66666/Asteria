"""Generic continuous camera choreography runtime."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from math import sin, tau


@dataclass(frozen=True, slots=True)
class CameraState:
    x: float = 0
    y: float = 0
    zoom: float = 1
    rotation_deg: float = 0
    viewport_x: float = 0
    viewport_y: float = 0
    parameters: Mapping[str, float] | None = None


@dataclass(frozen=True, slots=True)
class CameraModulation:
    target: str
    amplitude: float
    frequency_hz: float
    duration_ms: float
    phase: float = 0
    decay_power: float = 1

    def sample(self, time_ms: float) -> float:
        if time_ms < 0 or time_ms >= self.duration_ms:
            return 0.0
        env = (1 - time_ms / self.duration_ms) ** self.decay_power
        return self.amplitude * sin(tau * (self.frequency_hz * time_ms / 1000 + self.phase)) * env


class CameraRuntime:
    """Base properties + authored channels + layerable continuous modulation."""

    _core = {"x", "y", "zoom", "rotation_deg", "viewport_x", "viewport_y"}

    def __init__(self, state: CameraState = CameraState()):
        self._base = {k: getattr(state, k) for k in self._core}
        self._extra = dict(state.parameters or {})
        self._mods: list[CameraModulation] = []

    def apply_properties(self, values: Mapping[str, float]) -> None:
        for k, v in values.items():
            (self._base if k in self._core else self._extra)[k] = float(v)

    def add_modulation(self, m: CameraModulation) -> None:
        if not m.target:
            raise ValueError("target required")
        if m.frequency_hz < 0 or m.duration_ms <= 0 or m.decay_power < 0:
            raise ValueError("invalid modulation")
        self._mods.append(m)

    def sample(self, time_ms: float) -> CameraState:
        v = dict(self._base)
        extra = dict(self._extra)
        for m in self._mods:
            value = m.sample(time_ms)
            if m.target in self._core:
                v[m.target] = v.get(m.target, 0) + value
            else:
                extra[m.target] = extra.get(m.target, 0) + value
        return CameraState(parameters=extra, **v)

    def prune(self, time_ms: float) -> None:
        self._mods = [m for m in self._mods if time_ms < m.duration_ms]

    def clear_modulations(self) -> None:
        self._mods.clear()
