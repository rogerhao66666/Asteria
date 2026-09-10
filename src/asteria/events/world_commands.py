from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class WorldCommand:
    """Backend-neutral request for a world/game service operation."""

    name: str
    args: dict[str, Any]
    source_entity_id: str = ""

    def __init__(self, name: str, args=None, *, source_entity_id: str = ""):
        name = str(name).strip().upper()
        if not name:
            raise ValueError("world command name is required")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "args", dict(args or {}))
        object.__setattr__(self, "source_entity_id", str(source_entity_id))


class WorldCommandRouter:
    """Small service boundary; engine/game registers handlers explicitly."""

    def __init__(self):
        self._handlers: dict[str, Callable[[WorldCommand], object]] = {}

    def register(self, name: str, handler):
        key = str(name).strip().upper()
        if not key:
            raise ValueError("command name is required")
        if not callable(handler):
            raise TypeError("handler must be callable")
        if key in self._handlers:
            raise ValueError(f"duplicate world command handler: {key}")
        self._handlers[key] = handler
        return handler

    def can_handle(self, name: str) -> bool:
        return str(name).strip().upper() in self._handlers

    def dispatch(self, command: WorldCommand):
        try:
            handler = self._handlers[command.name]
        except KeyError as exc:
            raise KeyError(f"no handler for world command: {command.name}") from exc
        return handler(command)
