"""Generic runtime→executor bridge.

The bridge does not know gameplay semantics. Any project-defined channel/action may be
registered. Executors return signals/events; blocking completion is fed back into the
canonical sequence runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .canonical import Command
from .runtime import Runtime, RuntimeEvent


@dataclass(frozen=True, slots=True)
class ExecutorSignal:
    name: str
    payload: Any = None


class Executor(Protocol):
    def dispatch(self, node_id: str, command: Command) -> tuple[ExecutorSignal, ...]: ...
    def update(self, dt_ms: float) -> tuple[ExecutorSignal, ...]: ...
    def cancel(self, node_id: str) -> None: ...


class ExecutorRegistry:
    def __init__(self):
        self._items: dict[str, Executor] = {}

    def register(self, channel: str, executor: Executor):
        if not channel:
            raise ValueError("channel required")
        self._items[channel] = executor

    def unregister(self, channel: str):
        self._items.pop(channel, None)

    def get(self, channel: str) -> Executor:
        if channel not in self._items:
            raise KeyError(f"no executor registered for channel {channel!r}")
        return self._items[channel]

    def channels(self):
        return tuple(sorted(self._items))


@dataclass(slots=True)
class ImmediateExecutor:
    """Headless/reference executor. Completes blocking commands immediately."""

    received: list[tuple[str, Command]] = field(default_factory=list)

    def dispatch(self, node_id, command):
        self.received.append((node_id, command))
        return (ExecutorSignal(f"command.completed:{node_id}"),) if command.blocking else ()

    def update(self, dt_ms):
        return ()

    def cancel(self, node_id):
        pass


@dataclass(slots=True)
class TimedExecutor:
    """Deterministic reference executor for transitions/movement/VFX-like tasks."""

    active: dict[str, float] = field(default_factory=dict)
    received: list[tuple[str, Command]] = field(default_factory=list)

    def dispatch(self, node_id, command):
        self.received.append((node_id, command))
        if not command.blocking:
            return ()
        duration = float(command.args.get("duration_ms", 0))
        if duration <= 0:
            return (ExecutorSignal(f"command.completed:{node_id}"),)
        self.active[node_id] = duration
        return ()

    def update(self, dt_ms):
        out = []
        for nid in list(self.active):
            self.active[nid] -= dt_ms
            if self.active[nid] <= 0:
                del self.active[nid]
                out.append(ExecutorSignal(f"command.completed:{nid}"))
        return tuple(out)

    def cancel(self, node_id):
        self.active.pop(node_id, None)


class PresentationRunner:
    """Owns one canonical Runtime and routes only presentation commands/signals."""

    def __init__(self, runtime: Runtime, registry: ExecutorRegistry):
        self.runtime = runtime
        self.registry = registry
        self.output_events: list[RuntimeEvent | ExecutorSignal] = []
        self._active_blocking: dict[str, str] = {}

    @property
    def completed(self):
        return self.runtime.completed

    def signal(self, name, payload=None):
        self.runtime.signal(name)
        self.output_events.append(ExecutorSignal(name, payload))

    def cancel(self):
        for node_id, channel in tuple(self._active_blocking.items()):
            self.registry.get(channel).cancel(node_id)
        self._active_blocking.clear()
        self.runtime.cancel()

    def update(self, dt_ms: float):
        if dt_ms < 0:
            raise ValueError("negative dt")
        # Executors advance first; their completion/events become runtime signals.
        for channel in self.registry.channels():
            for sig in self.registry.get(channel).update(dt_ms):
                self.runtime.signal(sig.name)
                self.output_events.append(sig)
                if sig.name.startswith("command.completed:"):
                    self._active_blocking.pop(sig.name.split(":", 1)[1], None)
        # Drain instantaneous runtime work and immediate executor feedback.
        guard = 0
        while not self.runtime.completed and guard < 10000:
            guard += 1
            events = self.runtime.update(dt_ms if guard == 1 else 0)
            if not events:
                break
            self.output_events.extend(events)
            feedback = False
            for ev in events:
                if ev.kind == "command":
                    cmd = ev.payload
                    if cmd.blocking:
                        self._active_blocking[ev.node_id] = cmd.channel
                    for sig in self.registry.get(cmd.channel).dispatch(ev.node_id, cmd):
                        self.runtime.signal(sig.name)
                        self.output_events.append(sig)
                        feedback = True
                        if sig.name.startswith("command.completed:"):
                            self._active_blocking.pop(sig.name.split(":", 1)[1], None)
            if not feedback:
                break
        out = tuple(self.output_events)
        self.output_events.clear()
        return out
