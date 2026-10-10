"""Non-destructive live Presentation preview session."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from .bridge import ExecutorRegistry, ExecutorSignal, ImmediateExecutor, PresentationRunner
from .canonical import Context
from .runtime import Runtime, RuntimeEvent


@dataclass(frozen=True, slots=True)
class PreviewDiagnostic:
    time_ms: float
    kind: str
    node_id: str | None
    detail: object = None


class PreviewExecutorRegistry(ExecutorRegistry):
    """Sandbox registry. Preview adapters must not mutate game/project state."""

    @classmethod
    def permissive(cls, channels):
        r = cls()
        for c in channels:
            r.register(c, ImmediateExecutor())
        return r


class PresentationPreviewSession:
    def __init__(self, sequence, library=None, context=None, registry=None):
        self.sequence = sequence
        self.library = library
        self.base_context = deepcopy(context or Context())
        self.registry = registry or ExecutorRegistry()
        self.time_ms = 0.0
        self.playing = False
        self.diagnostics = []
        self._make_runner()

    def _make_runner(self):
        self.context = deepcopy(self.base_context)
        self.runtime = Runtime(self.sequence, self.library, self.context)
        self.runner = PresentationRunner(self.runtime, self.registry)

    def play(self):
        self.playing = True

    def pause(self):
        self.playing = False

    def reset(self):
        self.time_ms = 0.0
        self.playing = False
        self.diagnostics.clear()
        # clear deterministic sandbox executor transient state where available
        for ch in self.registry.channels():
            ex = self.registry.get(ch)
            if hasattr(ex, "active"):
                ex.active.clear()
            if hasattr(ex, "received"):
                ex.received.clear()
        self._make_runner()

    def replay(self):
        self.reset()
        self.play()

    @property
    def completed(self):
        return self.runner.completed

    def signal(self, name, payload=None):
        self.runner.signal(name, payload)

    def step(self, dt_ms):
        if dt_ms < 0:
            raise ValueError("negative dt")
        if not self.playing:
            return ()
        ev = self.runner.update(dt_ms)
        self.time_ms += dt_ms
        self._record(ev)
        return ev

    def _record(self, events):
        for e in events:
            if isinstance(e, RuntimeEvent):
                self.diagnostics.append(PreviewDiagnostic(self.time_ms, e.kind, e.node_id, e.payload))
            elif isinstance(e, ExecutorSignal):
                self.diagnostics.append(PreviewDiagnostic(self.time_ms, "signal", None, (e.name, e.payload)))

    def scrub(self, target_ms, quantum_ms=16):
        """Deterministic replay-from-zero scrub; preview state never enters canonical data."""
        if target_ms < 0:
            raise ValueError("negative preview time")
        was = self.playing
        self.reset()
        self.play()
        remaining = float(target_ms)
        # Process zero-time commands first.
        self._record(self.runner.update(0))
        guard = 0
        while remaining > 0 and not self.completed and guard < 100000:
            dt = min(float(quantum_ms), remaining)
            self._record(self.runner.update(dt))
            self.time_ms += dt
            remaining -= dt
            guard += 1
        self.time_ms = float(target_ms)
        self.playing = was
        return tuple(self.diagnostics)

    def active_nodes(self):
        out = []

        def walk(f):
            if f.started and not f.done:
                out.append(f.n.id)
            for c in f.children:
                walk(c)

        walk(self.runtime.root)
        return tuple(out)
