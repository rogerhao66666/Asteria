from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

E = TypeVar("E")
EventHandler = Callable[[Any], None]


class EventBus:
    """Small synchronous typed event bus.

    Publishing snapshots subscribers so handlers may safely subscribe/unsubscribe
    during dispatch. Events are intentionally synchronous in the Core baseline.
    """

    __slots__ = ("_handlers",)

    def __init__(self) -> None:
        self._handlers: dict[type[object], list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        handlers = self._handlers[event_type]
        if handler in handlers:
            raise ValueError("handler already subscribed")
        handlers.append(handler)  # type: ignore[arg-type]

    def unsubscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        handlers = self._handlers.get(event_type)
        if not handlers or handler not in handlers:
            return
        handlers.remove(handler)  # type: ignore[arg-type]
        if not handlers:
            self._handlers.pop(event_type, None)

    def publish(self, event: E) -> None:
        for handler in tuple(self._handlers.get(type(event), ())):
            handler(event)

    def clear(self) -> None:
        self._handlers.clear()
