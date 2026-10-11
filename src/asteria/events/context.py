from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

_ALLOWED_SCALARS = (type(None), bool, int, float, str)


def _validate_value(value: Any):
    if not isinstance(value, _ALLOWED_SCALARS):
        raise TypeError("event values must be JSON-compatible scalar values")
    return value


@dataclass(slots=True)
class EventContext:
    """Serializable mutable state visible to event programs.

    Global state:
    - switches: boolean flags
    - variables: scalar values

    Local/self state:
    - scoped by stable owner/event identifier
    - stored separately so reusable/common events do not leak state
    """

    switches: dict[str, bool] = field(default_factory=dict)
    variables: dict[str, Any] = field(default_factory=dict)
    locals: dict[str, dict[str, Any]] = field(default_factory=dict)
    # Read-only values the host exposes to conditions (e.g. "battle": round, HP ratios). Never saved.
    providers: dict[str, Any] = field(default_factory=dict, compare=False, repr=False)

    def get_switch(self, name: str, default: bool = False) -> bool:
        return bool(self.switches.get(str(name), default))

    def set_switch(self, name: str, value: bool) -> None:
        name = str(name).strip()
        if not name:
            raise ValueError("switch name is required")
        self.switches[name] = bool(value)

    def get_variable(self, name: str, default=None):
        return self.variables.get(str(name), default)

    def set_variable(self, name: str, value) -> None:
        name = str(name).strip()
        if not name:
            raise ValueError("variable name is required")
        self.variables[name] = _validate_value(value)

    def get_local(self, scope_id: str, name: str, default=None):
        return self.locals.get(str(scope_id), {}).get(str(name), default)

    def set_local(self, scope_id: str, name: str, value) -> None:
        scope_id = str(scope_id).strip()
        name = str(name).strip()
        if not scope_id:
            raise ValueError("local scope_id is required")
        if not name:
            raise ValueError("local name is required")
        self.locals.setdefault(scope_id, {})[name] = _validate_value(value)

    def clear_local_scope(self, scope_id: str) -> None:
        self.locals.pop(str(scope_id), None)

    def to_data(self):
        return {
            "schema": "asteria.event_context",
            "version": 1,
            "switches": dict(self.switches),
            "variables": dict(self.variables),
            "locals": {scope: dict(values) for scope, values in self.locals.items()},
        }

    @classmethod
    def from_data(cls, data):
        expected = {"schema", "version", "switches", "variables", "locals"}
        if set(data) != expected:
            raise ValueError("invalid event context")
        if data["schema"] != "asteria.event_context" or data["version"] != 1:
            raise ValueError("unsupported event context")
        if not isinstance(data["switches"], dict):
            raise TypeError("switches must be a dict")
        if not isinstance(data["variables"], dict):
            raise TypeError("variables must be a dict")
        if not isinstance(data["locals"], dict):
            raise TypeError("locals must be a dict")
        ctx = cls()
        for name, value in data["switches"].items():
            ctx.set_switch(name, value)
        for name, value in data["variables"].items():
            ctx.set_variable(name, value)
        for scope, values in data["locals"].items():
            if not isinstance(values, dict):
                raise TypeError("local scope values must be a dict")
            for name, value in values.items():
                ctx.set_local(scope, name, value)
        return ctx
