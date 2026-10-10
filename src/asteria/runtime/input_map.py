"""Input actions, device bindings and rebinding (ASTERIA_SPEC §8 Input).

Gameplay reads named actions ("move_left", "confirm", ...) from an
``InputSnapshot``; an ``InputActionMap`` decides which keys, gamepad buttons
and gamepad axes produce them. Maps are project data (serialized with the
Project) and can be rebound at runtime. Several control schemes coexist by
binding one action to several devices.

Backends report raw device state as ``RawInputState`` using portable names:
keys by their lower-case name ("a", "left", "return", "space"), gamepad
buttons by index, axes by index with values in [-1, 1].
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .input import InputSnapshot

DEVICES = ("key", "gamepad_button", "gamepad_axis", "gamepad_hat")


@dataclass(frozen=True, slots=True)
class InputBinding:
    """One physical input. For axes/hats, ``direction`` is -1 or +1."""

    device: str
    code: str
    direction: int = 1
    threshold: float = 0.5

    def __post_init__(self):
        if self.device not in DEVICES:
            raise ValueError(f"unknown input device: {self.device}")
        object.__setattr__(self, "code", str(self.code).strip().lower())
        if not self.code:
            raise ValueError("binding code is required")
        if self.direction not in (-1, 1):
            raise ValueError("direction must be -1 or 1")
        if not 0.0 < float(self.threshold) <= 1.0:
            raise ValueError("threshold must be in (0, 1]")

    def value(self, raw: RawInputState) -> float:
        if self.device == "key":
            return 1.0 if self.code in raw.keys else 0.0
        if self.device == "gamepad_button":
            return 1.0 if self.code in raw.buttons else 0.0
        if self.device == "gamepad_axis":
            amount = raw.axes.get(self.code, 0.0) * self.direction
            return amount if amount >= self.threshold else 0.0
        hat_axis, _, hat = self.code.partition(":")  # gamepad_hat code "x:0" / "y:0"
        amount = raw.hats.get(f"{hat_axis}:{hat or '0'}", 0) * self.direction
        return 1.0 if amount > 0 else 0.0

    def to_data(self):
        return {"device": self.device, "code": self.code, "direction": self.direction, "threshold": self.threshold}

    @classmethod
    def from_data(cls, data):
        return cls(data["device"], data["code"], int(data.get("direction", 1)), float(data.get("threshold", 0.5)))


@dataclass(slots=True)
class RawInputState:
    keys: set[str] = field(default_factory=set)
    buttons: set[str] = field(default_factory=set)
    axes: dict[str, float] = field(default_factory=dict)
    hats: dict[str, int] = field(default_factory=dict)


class InputActionMap:
    SCHEMA = "asteria.input_action_map"
    VERSION = 1

    def __init__(self, actions=None):
        self._actions: dict[str, tuple[InputBinding, ...]] = {}
        for action_id, bindings in dict(actions or {}).items():
            self.set_bindings(action_id, bindings)

    def actions(self):
        return tuple(self._actions)

    def bindings(self, action_id):
        return self._actions.get(str(action_id), ())

    def set_bindings(self, action_id, bindings):
        action_id = str(action_id).strip()
        if not action_id:
            raise ValueError("action id is required")
        values = tuple(bindings)
        if any(not isinstance(b, InputBinding) for b in values):
            raise TypeError("bindings must be InputBinding values")
        self._actions[action_id] = tuple(dict.fromkeys(values))

    def rebind(self, action_id, old: InputBinding | None, new: InputBinding, *, exclusive=False):
        """Replace ``old`` (or add ``new`` when ``old`` is None).

        With ``exclusive`` the new input is also removed from every other action.
        """
        action_id = str(action_id)
        if action_id not in self._actions:
            raise KeyError(f"unknown action: {action_id}")
        if exclusive:
            for other, bindings in self._actions.items():
                if other != action_id and new in bindings:
                    self._actions[other] = tuple(b for b in bindings if b != new)
        current = list(self._actions[action_id])
        if old is not None:
            if old not in current:
                raise KeyError(f"{action_id} is not bound to {old}")
            current[current.index(old)] = new
        elif new not in current:
            current.append(new)
        self._actions[action_id] = tuple(dict.fromkeys(current))

    def evaluate(self, raw: RawInputState) -> InputSnapshot:
        return InputSnapshot(
            {
                action_id: max((b.value(raw) for b in bindings), default=0.0)
                for action_id, bindings in self._actions.items()
            }
        )

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "actions": {a: [b.to_data() for b in bs] for a, bs in sorted(self._actions.items())},
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported input action map")
        return cls({a: [InputBinding.from_data(b) for b in bs] for a, bs in data["actions"].items()})

    @classmethod
    def default(cls):
        """Keyboard (arrows/WASD) plus a standard gamepad (left stick, d-pad, A/B/Start)."""
        key = lambda code: InputBinding("key", code)  # noqa: E731
        button = lambda code: InputBinding("gamepad_button", code)  # noqa: E731
        return cls(
            {
                "move_left": (
                    key("left"),
                    key("a"),
                    InputBinding("gamepad_axis", "0", -1),
                    InputBinding("gamepad_hat", "x:0", -1),
                ),
                "move_right": (
                    key("right"),
                    key("d"),
                    InputBinding("gamepad_axis", "0", 1),
                    InputBinding("gamepad_hat", "x:0", 1),
                ),
                "move_up": (
                    key("up"),
                    key("w"),
                    InputBinding("gamepad_axis", "1", -1),
                    InputBinding("gamepad_hat", "y:0", 1),
                ),
                "move_down": (
                    key("down"),
                    key("s"),
                    InputBinding("gamepad_axis", "1", 1),
                    InputBinding("gamepad_hat", "y:0", -1),
                ),
                "interact": (key("e"), key("return"), key("space"), button("0")),
                "confirm": (key("return"), key("space"), button("0")),
                "cancel": (key("escape"), key("backspace"), button("1")),
                "menu": (key("c"), button("7")),
            }
        )


class InputActionTracker:
    """Turns successive snapshots into held / just-pressed / just-released queries."""

    def __init__(self, input_map: InputActionMap):
        self.input_map = input_map
        self.current = InputSnapshot({})
        self.previous = InputSnapshot({})

    def update(self, raw: RawInputState) -> InputSnapshot:
        self.previous = self.current
        self.current = self.input_map.evaluate(raw)
        return self.current

    def held(self, action_id) -> bool:
        return self.current.actions.get(action_id, 0.0) > 0.0

    def just_pressed(self, action_id) -> bool:
        return self.held(action_id) and self.previous.actions.get(action_id, 0.0) <= 0.0

    def just_released(self, action_id) -> bool:
        return not self.held(action_id) and self.previous.actions.get(action_id, 0.0) > 0.0
