"""Named countdown / count-up timers for event programs (YEP EventTimerControl).

All state lives in the ``EventContext`` variables (``timer.<id>.*``), so timers are saved with the
game and need no extra save format. ``update(dt)`` advances every running timer and returns the
ones that finished, with the event program each asked to run.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

PREFIX = "timer."
FIELDS = ("left", "limit", "running", "up", "expire", "show")


@dataclass(frozen=True, slots=True)
class TimerFinished:
    timer_id: str
    on_expire: str = ""


def _seconds(value, label):
    value = float(value)
    if not isfinite(value) or value < 0:
        raise ValueError(f"{label} must be finite and >= 0")
    return value


class EventTimers:
    def __init__(self, context):
        self.context = context
        # (variables dict, its key revision, active ids): valid while that dict's key set is
        # unchanged; a replaced or untracked variables dict is rescanned.
        self._active_cache = None

    def _key(self, timer_id, field):
        return f"{PREFIX}{timer_id}.{field}"

    def _get(self, timer_id, field, default=None):
        return self.context.get_variable(self._key(timer_id, field), default)

    def _set(self, timer_id, field, value):
        self.context.set_variable(self._key(timer_id, field), value)

    def _id(self, timer_id):
        timer_id = str(timer_id).strip()
        if not timer_id or "." in timer_id:
            raise ValueError("a timer id is a non-empty name without dots")
        return timer_id

    # -- control -------------------------------------------------------------------------------
    def start(self, timer_id, seconds, *, on_expire="", count_up=False, show=True):
        """Start (or restart) a timer. Counting down it finishes at 0; counting up it runs from 0
        and finishes at ``seconds`` (0 = never)."""
        timer_id = self._id(timer_id)
        seconds = _seconds(seconds, "seconds")
        self._set(timer_id, "up", bool(count_up))
        self._set(timer_id, "limit", seconds)
        self._set(timer_id, "left", 0.0 if count_up else seconds)
        self._set(timer_id, "running", True)
        self._set(timer_id, "expire", str(on_expire or ""))
        self._set(timer_id, "show", bool(show))
        self.context.set_switch(f"{PREFIX}{timer_id}.expired", False)

    def stop(self, timer_id):
        timer_id = self._id(timer_id)
        for field in FIELDS:
            self.context.variables.pop(self._key(timer_id, field), None)

    def pause(self, timer_id):
        if self.exists(timer_id):
            self._set(self._id(timer_id), "running", False)

    def resume(self, timer_id):
        if self.exists(timer_id):
            self._set(self._id(timer_id), "running", True)

    def add(self, timer_id, seconds):
        """Add (or, negative, take away) time; a countdown never drops below 0."""
        timer_id = self._id(timer_id)
        if not self.exists(timer_id):
            raise KeyError(timer_id)
        value = float(self._get(timer_id, "left")) + float(seconds)
        self._set(timer_id, "left", max(0.0, value))

    # -- reading -------------------------------------------------------------------------------
    def exists(self, timer_id):
        return self._get(str(timer_id), "left") is not None

    def active(self):
        variables = self.context.variables
        revision = getattr(variables, "key_revision", None)
        cache = self._active_cache
        if (
            revision is not None
            and cache is not None
            and cache[0] is variables
            and cache[1] == revision
        ):
            return cache[2]
        names = {
            key[len(PREFIX) :].rsplit(".", 1)[0]
            for key in variables
            if key.startswith(PREFIX) and key.endswith(".left")
        }
        result = tuple(sorted(names))
        self._active_cache = None if revision is None else (variables, revision, result)
        return result

    def running(self, timer_id):
        return bool(self._get(str(timer_id), "running", False))

    def remaining(self, timer_id):
        """Seconds left (countdown) or until the limit (count-up with one); ``None`` if none."""
        timer_id = str(timer_id)
        left = self._get(timer_id, "left")
        if left is None:
            return None
        if self._get(timer_id, "up"):
            limit = float(self._get(timer_id, "limit", 0.0))
            return max(0.0, limit - float(left)) if limit else None
        return float(left)

    def elapsed(self, timer_id):
        timer_id = str(timer_id)
        left = self._get(timer_id, "left")
        if left is None:
            return None
        if self._get(timer_id, "up"):
            return float(left)
        return max(0.0, float(self._get(timer_id, "limit", 0.0)) - float(left))

    def display(self):
        """``(timer id, "MM:SS")`` for each visible timer, countdowns showing time left."""
        rows = []
        for timer_id in self.active():
            if not self._get(timer_id, "show", True):
                continue
            up = bool(self._get(timer_id, "up"))
            seconds = self.elapsed(timer_id) if up else self.remaining(timer_id)
            whole = int(seconds or 0)
            rows.append((timer_id, f"{whole // 60:02d}:{whole % 60:02d}"))
        return tuple(rows)

    # -- time ----------------------------------------------------------------------------------
    def update(self, dt):
        dt = max(0.0, float(dt))
        finished = []
        for timer_id in self.active():
            if not self.running(timer_id):
                continue
            left = float(self._get(timer_id, "left"))
            up = bool(self._get(timer_id, "up"))
            left = left + dt if up else max(0.0, left - dt)
            self._set(timer_id, "left", left)
            limit = float(self._get(timer_id, "limit", 0.0))
            done = (left >= limit > 0) if up else left <= 0
            if done:
                program = str(self._get(timer_id, "expire", ""))
                self.stop(timer_id)
                self.context.set_switch(f"{PREFIX}{timer_id}.expired", True)
                finished.append(TimerFinished(timer_id, program))
        return tuple(finished)
