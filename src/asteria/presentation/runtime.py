from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import Command, Context, Kind, Library, bind


@dataclass(frozen=True, slots=True)
class RuntimeEvent:
    kind: str
    node_id: str
    payload: Any = None


class RuntimeSafetyError(RuntimeError):
    pass


class RuntimeLimits:
    def __init__(self, max_ops_per_update=100000, max_depth=256, max_events_per_update=100000):
        self.max_ops_per_update = max_ops_per_update
        self.max_depth = max_depth
        self.max_events_per_update = max_events_per_update


class Frame:
    def __init__(self, n):
        self.n = n
        self.i = 0
        self.elapsed = 0.0
        self.started = False
        self.children = []
        self.iter = 0
        self.done = False


class Runtime:
    def __init__(self, sequence, library=None, context=None, limits=None):
        sequence.validate()
        self.sequence = sequence
        self.lib = library or Library()
        self.ctx = context or Context()
        self.root = Frame(sequence.root)
        self.signals = set()
        self.events = []
        self.cancelled = False
        self.limits = limits or RuntimeLimits()
        self._ops = 0

    def signal(self, x):
        self.signals.add(x)

    @property
    def completed(self):
        return self.cancelled or self.root.done

    def cancel(self):
        if not self.cancelled:
            self.cancelled = True
            self.events.append(RuntimeEvent("cancelled", self.root.n.id))

    def _guard(self, depth):
        self._ops += 1
        if self._ops > self.limits.max_ops_per_update:
            raise RuntimeSafetyError("operation budget exceeded")
        if depth > self.limits.max_depth:
            raise RuntimeSafetyError("presentation nesting depth exceeded")

    def _emit(self, e):
        self.events.append(e)
        if len(self.events) > self.limits.max_events_per_update:
            raise RuntimeSafetyError("event budget exceeded")

    def update(self, dt):
        if dt < 0:
            raise ValueError("negative dt")
        self._ops = 0
        if not self.cancelled:
            self._tick(self.root, float(dt), 0)
        e = tuple(self.events)
        self.events.clear()
        self.signals.clear()
        return e

    def _init_children(self, f):
        n = f.n
        k = n.kind
        if k == Kind.BRANCH:
            xs = n.children if n.condition.eval(self.ctx) else n.else_children
        elif k == Kind.NESTED:
            xs = (self.lib.get(n.sequence_ref).root,)
        else:
            xs = n.children
        f.children = [Frame(x) for x in xs]
        f.started = True

    def _serial(self, f, budget, depth):
        remaining = budget
        while f.i < len(f.children):
            c = f.children[f.i]
            remaining = self._tick(c, remaining, depth + 1)
            if not c.done:
                return 0.0
            f.i += 1
        f.done = True
        return remaining

    def _tick(self, f, budget, depth):
        self._guard(depth)
        if f.done:
            return budget
        n = f.n
        k = n.kind
        if k == Kind.COMMAND:
            if not f.started:
                cmd = Command(n.command.channel, n.command.action, bind(n.command.args, self.ctx), n.command.blocking)
                self._emit(RuntimeEvent("command", n.id, cmd))
                f.started = True
            if not n.command.blocking or "command.completed:" + n.id in self.signals:
                f.done = True
            return budget
        if k == Kind.WAIT:
            need = max(0.0, n.duration_ms - f.elapsed)
            used = min(need, budget)
            f.elapsed += used
            if f.elapsed >= n.duration_ms:
                f.done = True
                return budget - used
            return 0.0
        if k == Kind.WAIT_EVENT:
            f.done = n.event_name in self.signals
            return budget if f.done else 0.0
        if k == Kind.EMIT_EVENT:
            self._emit(RuntimeEvent("emit", n.id, n.event_name))
            f.done = True
            return budget
        if k == Kind.SET_VARIABLE:
            self.ctx.variables[n.variable] = bind(n.value, self.ctx)
            self._emit(RuntimeEvent("variable", n.id, (n.variable, self.ctx.variables[n.variable])))
            f.done = True
            return budget
        if k in (Kind.SEQUENCE, Kind.PARALLEL, Kind.BRANCH, Kind.LOOP, Kind.NESTED):
            if not f.started:
                self._init_children(f)
            if k == Kind.PARALLEL:
                leftovers = []
                for c in f.children:
                    leftovers.append(self._tick(c, budget, depth + 1))
                f.done = all(c.done for c in f.children)
                return min(leftovers, default=budget) if f.done else 0.0
            remaining = self._serial(f, budget, depth)
            if k == Kind.LOOP and f.done:
                f.iter += 1
                if f.iter < n.loop_count:
                    f.done = False
                    f.i = 0
                    f.children = [Frame(x) for x in n.children]
                    return (
                        self._tick(f, remaining, depth)
                        if remaining > 0
                        or all(x.n.kind not in (Kind.WAIT, Kind.WAIT_EVENT, Kind.COMMAND) for x in f.children)
                        else 0.0
                    )
            return remaining if f.done else 0.0
        return 0.0

    def snapshot(self):
        def snap(f):
            return {
                "id": f.n.id,
                "i": f.i,
                "elapsed": f.elapsed,
                "started": f.started,
                "iter": f.iter,
                "done": f.done,
                "children": [snap(x) for x in f.children],
            }

        return {
            "schema": "asteria.presentation.runtime_snapshot.v1",
            "sequence_id": self.sequence.id,
            "variables": dict(self.ctx.variables),
            "cancelled": self.cancelled,
            "frame": snap(self.root),
        }

    def restore(self, s):
        if s["sequence_id"] != self.sequence.id:
            raise ValueError("snapshot sequence mismatch")
        self.ctx.variables = dict(s["variables"])
        self.cancelled = bool(s["cancelled"])

        def load(f, d):
            f.i = d["i"]
            f.elapsed = d["elapsed"]
            f.started = d["started"]
            f.iter = d["iter"]
            f.done = d["done"]
            if f.started and not f.children:
                self._init_children(f)
            for x, y in zip(f.children, d["children"]):
                load(x, y)

        load(self.root, s["frame"])
