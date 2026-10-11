"""Afterimages and trails (VFX-03): fading echoes of a moving sprite.

``MotionEcho`` keeps a short ring of snapshots (any payload: a TextureDraw, a pygame blit
spec...) taken every ``interval`` seconds while active, and returns them with their opacity
so a renderer can draw them behind the live sprite.

* ``afterimage`` - a few spaced copies of the pose that fade (dashes, quick steps)
* ``trail``      - a dense, fast-fading stream of copies (streaks behind fast motion)

Echoes are pure presentation: they never touch game state. A renderer drops an entity's echo
when the entity disappears or the scene changes (``MotionEchoes.prune``).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

PRESETS = {
    "afterimage": {"interval": 0.06, "count": 4, "fade": 0.55, "lifetime": 0.35},
    "trail": {"interval": 0.016, "count": 12, "fade": 0.78, "lifetime": 0.2},
}


@dataclass(slots=True)
class EchoSettings:
    kind: str = "afterimage"
    interval: float = 0.06
    count: int = 4
    fade: float = 0.55  # opacity multiplier per older copy
    lifetime: float = 0.35  # seconds a copy stays

    @classmethod
    def of(cls, kind, **overrides):
        values = dict(PRESETS.get(kind, PRESETS["afterimage"]))
        values.update({k: v for k, v in overrides.items() if k in values and v is not None})
        return cls(
            kind if kind in PRESETS else "afterimage",
            float(values["interval"]),
            int(values["count"]),
            float(values["fade"]),
            float(values["lifetime"]),
        )


class MotionEcho:
    def __init__(self, settings: EchoSettings):
        self.settings = settings
        self.snapshots = deque(maxlen=max(1, settings.count))
        self.active_until = 0.0
        self._last = -1e9

    def activate(self, now, duration):
        self.active_until = max(self.active_until, now + float(duration))

    def record(self, now, payload, *, moving=True):
        """Take a snapshot when active (or moving, for always-on trails) and the interval has passed."""
        if (now <= self.active_until or moving) and now - self._last >= self.settings.interval:
            self.snapshots.append((now, payload))
            self._last = now

    def ghosts(self, now):
        """``[(payload, opacity)]`` oldest first; expired copies are dropped."""
        while self.snapshots and now - self.snapshots[0][0] > self.settings.lifetime:
            self.snapshots.popleft()
        n = len(self.snapshots)
        return [(payload, self.settings.fade ** (n - i)) for i, (_, payload) in enumerate(self.snapshots)]

    @property
    def idle(self):
        return not self.snapshots


class MotionEchoes:
    """Echoes by key (entity / member id) with cleanup for removed keys."""

    def __init__(self):
        self.by_key = {}

    def get(self, key, settings):
        echo = self.by_key.get(key)
        if echo is None or echo.settings != settings:
            echo = self.by_key[key] = MotionEcho(settings)
        return echo

    def prune(self, alive_keys):
        for key in [k for k in self.by_key if k not in alive_keys]:
            del self.by_key[key]

    def clear(self):
        self.by_key.clear()
