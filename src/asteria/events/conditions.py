from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .context import EventContext

_COMPARATORS = {"==", "!=", "<", "<=", ">", ">="}


@dataclass(frozen=True, slots=True)
class EventCondition:
    """Small deterministic condition object for event branching."""

    source: str
    name: str
    operator: str = "=="
    value: Any = True
    scope_id: str | None = None

    def evaluate(self, context: EventContext) -> bool:
        source = self.source.strip().lower()
        if source == "switch":
            current = context.get_switch(self.name)
        elif source == "variable":
            current = context.get_variable(self.name)
        elif source == "local":
            if not self.scope_id:
                raise ValueError("local condition requires scope_id")
            current = context.get_local(self.scope_id, self.name)
        else:
            raise ValueError(f"unsupported condition source: {self.source}")

        op = self.operator
        if op not in _COMPARATORS:
            raise ValueError(f"unsupported comparator: {op}")

        try:
            if op == "==":
                return current == self.value
            if op == "!=":
                return current != self.value
            if op == "<":
                return current < self.value
            if op == "<=":
                return current <= self.value
            if op == ">":
                return current > self.value
            return current >= self.value
        except TypeError:
            return False

    def to_data(self):
        return {
            "source": self.source,
            "name": self.name,
            "operator": self.operator,
            "value": self.value,
            "scope_id": self.scope_id,
        }

    @classmethod
    def from_data(cls, data):
        expected = {"source", "name", "operator", "value", "scope_id"}
        if set(data) != expected:
            raise ValueError("invalid event condition")
        return cls(
            source=str(data["source"]),
            name=str(data["name"]),
            operator=str(data["operator"]),
            value=data["value"],
            scope_id=data["scope_id"],
        )
