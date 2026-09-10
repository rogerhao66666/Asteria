from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any


def _name(value):
    value = str(value).strip()
    if not value:
        raise ValueError("lifecycle hook name is required")
    return value


@dataclass(frozen=True, slots=True)
class LifecycleEvent:
    name: str
    source: str = ""
    data: Mapping[str, Any] = field(default_factory=dict)

    def __init__(self, name, *, source="", data=None):
        object.__setattr__(self, "name", _name(name))
        object.__setattr__(self, "source", str(source))
        object.__setattr__(self, "data", MappingProxyType(dict(data or {})))


class LifecycleHookBus:
    """Synchronous named lifecycle seam shared by engine/toolkit subsystems.

    Hook names are intentionally strings. Systems may introduce domain-specific
    names without editing a central enum. `*` subscribers observe every hook.
    """

    def __init__(self):
        self._handlers: dict[str, list[Callable[[LifecycleEvent], None]]] = {}

    def subscribe(self, name, handler):
        name = "*" if str(name) == "*" else _name(name)
        if not callable(handler):
            raise TypeError("handler must be callable")
        handlers = self._handlers.setdefault(name, [])
        if handler in handlers:
            raise ValueError("handler already subscribed")
        handlers.append(handler)

    def unsubscribe(self, name, handler):
        handlers = self._handlers.get(str(name), [])
        if handler in handlers:
            handlers.remove(handler)
        if not handlers:
            self._handlers.pop(str(name), None)

    def emit(self, name, *, source="", data=None):
        event = LifecycleEvent(name, source=source, data=data)
        for handler in tuple(self._handlers.get(event.name, ())):
            handler(event)
        for handler in tuple(self._handlers.get("*", ())):
            handler(event)
        return event

    def clear(self):
        self._handlers.clear()


def emit_hook(hooks, name, *, source="", data=None):
    if hooks is None:
        return None
    if not isinstance(hooks, LifecycleHookBus):
        raise TypeError("hooks must be LifecycleHookBus")
    return hooks.emit(name, source=source, data=data)
