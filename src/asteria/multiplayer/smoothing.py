"""Client-side smoothing for real-time games: snapshot interpolation and input prediction.

Both are pure helpers the game's own loop drives; the network layer never calls them.

- ``SnapshotInterpolator``: remote players arrive in ticks (say 20 per second). Drawing them at
  ``now - delay`` and blending the two snapshots around that time hides the steps. Past the newest
  snapshot it extrapolates for at most ``max_extrapolation`` seconds, then holds still.
- ``InputPredictor``: the local player moves at once from their own input, remembers the inputs
  the server has not confirmed yet and, when an authoritative position arrives for input ``n``,
  snaps to it and replays the later inputs - so the player feels no lag and is still corrected.
"""

from __future__ import annotations

from collections import deque
from math import hypot


class SnapshotInterpolator:
    def __init__(self, *, delay=0.1, max_extrapolation=0.25, capacity=64):
        if delay < 0 or max_extrapolation < 0 or capacity < 2:
            raise ValueError("delay and extrapolation must be >= 0 and capacity >= 2")
        self.delay = float(delay)
        self.max_extrapolation = float(max_extrapolation)
        self._snapshots = deque(maxlen=int(capacity))

    def push(self, time, positions):
        """Record ``{id: (x, y)}`` as seen at ``time`` (seconds, any clock; must not go back)."""
        time = float(time)
        if self._snapshots and time <= self._snapshots[-1][0]:
            return False  # an old or duplicate snapshot
        self._snapshots.append(
            (time, {k: (float(v[0]), float(v[1])) for k, v in positions.items()})
        )
        return True

    def sample(self, now):
        """Positions to draw at ``now`` (the clock ``push`` used)."""
        if not self._snapshots:
            return {}
        when = float(now) - self.delay
        first, last = self._snapshots[0], self._snapshots[-1]
        if when <= first[0]:
            return dict(first[1])
        if when >= last[0]:
            return self._extrapolate(last, when)
        for (t0, a), (t1, b) in zip(self._snapshots, list(self._snapshots)[1:], strict=False):
            if t0 <= when <= t1:
                t = (when - t0) / (t1 - t0)
                return {
                    key: (
                        a[key][0] + (b[key][0] - a[key][0]) * t,
                        a[key][1] + (b[key][1] - a[key][1]) * t,
                    )
                    if key in a
                    else b[key]
                    for key in b
                }
        return dict(last[1])

    def _extrapolate(self, last, when):
        if len(self._snapshots) < 2 or not self.max_extrapolation:
            return dict(last[1])
        prev = self._snapshots[-2]
        span = last[0] - prev[0]
        ahead = min(when - last[0], self.max_extrapolation)
        result = {}
        for key, (x, y) in last[1].items():
            if key in prev[1] and span > 0:
                vx, vy = (x - prev[1][key][0]) / span, (y - prev[1][key][1]) / span
                result[key] = (x + vx * ahead, y + vy * ahead)
            else:
                result[key] = (x, y)
        return result


class InputPredictor:
    """Predicts the local player from their own inputs and reconciles with the server."""

    def __init__(self, position=(0.0, 0.0), *, speed=1.0, max_pending=240):
        self.position = (float(position[0]), float(position[1]))
        self.speed = float(speed)
        self.max_pending = int(max_pending)
        self._pending = deque()  # (sequence, move_x, move_y, dt)
        self.corrections = 0
        self.last_error = 0.0

    def _step(self, position, move_x, move_y, dt):
        length = hypot(move_x, move_y)
        if length > 1.0:
            move_x, move_y = move_x / length, move_y / length
        return position[0] + move_x * self.speed * dt, position[1] + move_y * self.speed * dt

    @property
    def pending(self):
        return len(self._pending)

    def apply_local(self, sequence, move_x, move_y, dt):
        """Move now; remember the input until the server confirms ``sequence``."""
        self.position = self._step(self.position, move_x, move_y, dt)
        self._pending.append((int(sequence), float(move_x), float(move_y), float(dt)))
        while len(self._pending) > self.max_pending:
            self._pending.popleft()
        return self.position

    def reconcile(self, server_position, acked_sequence):
        """Adopt the server's position as of input ``acked_sequence`` and replay what came after;
        returns how far the prediction was off (0 when it was right)."""
        while self._pending and self._pending[0][0] <= acked_sequence:
            self._pending.popleft()
        position = (float(server_position[0]), float(server_position[1]))
        for _, move_x, move_y, dt in self._pending:
            position = self._step(position, move_x, move_y, dt)
        self.last_error = hypot(position[0] - self.position[0], position[1] - self.position[1])
        if self.last_error > 1e-9:
            self.corrections += 1
        self.position = position
        return self.last_error
