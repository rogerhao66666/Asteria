"""Generic audio synchronization runtime for Presentation timelines."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True, slots=True)
class AudioCue:
    id: str
    asset_id: str
    start_ms: float
    bus: str = "default"
    volume: float = 1
    pitch: float = 1
    loop: bool = False
    parameters: Mapping[str, float] | None = None

    def __post_init__(self):
        if not self.id or not self.asset_id:
            raise ValueError("cue id and asset id required")
        if self.start_ms < 0:
            raise ValueError("negative cue time")


@dataclass(frozen=True, slots=True)
class AudioCommand:
    cue: AudioCue
    offset_ms: float


class AudioRuntime:
    """Samples scheduled cues against the same continuous presentation clock."""

    def __init__(self, cues=()):
        self._cues = tuple(sorted(cues, key=lambda c: (c.start_ms, c.id)))
        if len({c.id for c in self._cues}) != len(self._cues):
            raise ValueError("duplicate cue id")
        self._fired: set[str] = set()
        self.properties = {}

    def apply_properties(self, values: Mapping[str, float]) -> None:
        self.properties.update(values)

    def advance(self, previous_ms: float, current_ms: float) -> tuple[AudioCommand, ...]:
        if previous_ms < 0 or current_ms < previous_ms:
            raise ValueError("invalid clock range")
        out = []
        for c in self._cues:
            # Initial sample includes t=0; later ranges are (previous,current].
            due = (previous_ms == 0 and c.start_ms == 0) or (previous_ms < c.start_ms <= current_ms)
            if due and c.id not in self._fired:
                self._fired.add(c.id)
                out.append(AudioCommand(c, max(0.0, current_ms - c.start_ms)))
        return tuple(out)

    def seek(self, time_ms: float) -> None:
        if time_ms < 0:
            raise ValueError("negative seek")
        self._fired = {c.id for c in self._cues if c.start_ms < time_ms}

    def reset(self) -> None:
        self._fired.clear()
        self.properties.clear()


class AudioBackend(Protocol):
    def resolve_audio(self, asset_id: str) -> Any: ...
    def play(self, resource: Any, command: AudioCommand, properties: Mapping[str, float]) -> None: ...


class AudioBackendExecutor:
    def __init__(self, backend: AudioBackend):
        self.backend = backend
        self._resources = {}

    def execute(self, commands, properties=()):
        props = dict(properties)
        for cmd in commands:
            aid = cmd.cue.asset_id
            if aid not in self._resources:
                self._resources[aid] = self.backend.resolve_audio(aid)
            self.backend.play(self._resources[aid], cmd, props)

    def invalidate(self, asset_id: str) -> None:
        self._resources.pop(asset_id, None)

    def clear_resources(self) -> None:
        self._resources.clear()
