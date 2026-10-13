"""Generic world interactions (RPG-07, ASTERIA_SPEC §24).

One record describes an interaction such as talk, inspect, open, buy, steal,
challenge, recruit, persuade, capture, search, gather, fish, craft or a
custom verb, with the parts the SPEC lists:

* actor capability — ``actor_tag`` (some active party actor has it) and/or ``required_item``
* target type — ``target_type`` (informational; an entity's event chooses which interaction to run)
* requirements — ``requirements``: switches / variables (``[{source, name, operator, value}]``)
* cost — ``cost_items`` and ``cost_currencies``, paid when the attempt is made
* check — ``check_stat`` against ``difficulty`` (chance = ``base_chance`` + (best party stat -
  difficulty) x
  ``chance_per_point``, clamped to 0..1); no stat means it always succeeds
* success / failure — rewards (items, currencies), switches set, follow-up event programs
* consequence — reputation changes; ``repeatable`` false makes it a one-time interaction

Events run interactions with the ``INTERACT`` world command; the outcome is
written to the variable ``interaction.<id>`` (success / failure / refused) so the
event can branch on it.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite

VERBS = (
    "talk",
    "inspect",
    "open",
    "buy",
    "steal",
    "challenge",
    "recruit",
    "persuade",
    "capture",
    "search",
    "gather",
    "fish",
    "craft",
    "custom",
)
OPERATORS = ("==", "!=", "<", "<=", ">", ">=")


def _scalar(value):
    """Form text to a comparable value: true/false, numbers, or the text itself."""
    if not isinstance(value, str):
        return value
    text = value.strip()
    if text.lower() in ("true", "false"):
        return text.lower() == "true"
    for kind in (int, float):
        try:
            return kind(text)
        except ValueError:
            pass
    return text


def _amounts(values, label):
    result = {}
    for key, value in dict(values or {}).items():
        number = float(value)
        if not isfinite(number) or number < 0:
            raise ValueError(f"{label} {key} must be a non-negative number")
        result[str(key)] = number
    return result


@dataclass(frozen=True, slots=True)
class WorldInteraction:
    interaction_id: str
    display_name: str = ""
    verb: str = "talk"
    target_type: str = ""
    actor_tag: str = ""
    required_item: str = ""
    requirements: tuple = ()  # ({"source", "name", "operator", "value"}, ...)
    cost_items: dict = None
    cost_currencies: dict = None
    check_stat: str = ""
    difficulty: float = 0.0
    base_chance: float = 0.5
    chance_per_point: float = 0.05
    success_items: dict = None
    success_currencies: dict = None
    success_switch: str = ""
    success_event: str = ""
    failure_switch: str = ""
    failure_event: str = ""
    reputation: dict = None
    repeatable: bool = True

    def __post_init__(self):
        if not str(self.interaction_id).strip():
            raise ValueError("interaction_id is required")
        if self.verb not in VERBS:
            raise ValueError(f"verb must be one of {VERBS}")
        for name in ("cost_items", "cost_currencies", "success_items", "success_currencies"):
            object.__setattr__(self, name, _amounts(getattr(self, name), name))
        object.__setattr__(
            self, "reputation", {str(k): float(v) for k, v in dict(self.reputation or {}).items()}
        )
        reqs = []
        for item in self.requirements or ():
            item = dict(item)
            if (
                item.get("source") not in ("switch", "variable")
                or not str(item.get("name", "")).strip()
            ):
                raise ValueError("requirements need a switch / variable source and a name")
            if item.get("operator", "==") not in OPERATORS:
                raise ValueError(f"requirement operator must be one of {OPERATORS}")
            reqs.append(
                {
                    "source": item["source"],
                    "name": str(item["name"]),
                    "operator": item.get("operator", "=="),
                    "value": _scalar(item.get("value", True)),
                }
            )
        object.__setattr__(self, "requirements", tuple(reqs))
        for name in ("difficulty", "base_chance", "chance_per_point"):
            value = float(getattr(self, name))
            if not isfinite(value):
                raise ValueError(f"{name} must be finite")
            object.__setattr__(self, name, value)
        if not 0.0 <= self.base_chance <= 1.0:
            raise ValueError("base_chance must be between 0 and 1")

    def chance(self, best_stat):
        if not self.check_stat:
            return 1.0
        value = self.base_chance + (float(best_stat) - self.difficulty) * self.chance_per_point
        return max(0.0, min(1.0, value))

    def to_data(self):
        return {
            "schema": "asteria.rpg.world_interaction",
            "version": 1,
            "interaction_id": self.interaction_id,
            "display_name": self.display_name,
            "verb": self.verb,
            "target_type": self.target_type,
            "actor_tag": self.actor_tag,
            "required_item": self.required_item,
            "requirements": [dict(x) for x in self.requirements],
            "cost_items": dict(self.cost_items),
            "cost_currencies": dict(self.cost_currencies),
            "check_stat": self.check_stat,
            "difficulty": self.difficulty,
            "base_chance": self.base_chance,
            "chance_per_point": self.chance_per_point,
            "success_items": dict(self.success_items),
            "success_currencies": dict(self.success_currencies),
            "success_switch": self.success_switch,
            "success_event": self.success_event,
            "failure_switch": self.failure_switch,
            "failure_event": self.failure_event,
            "reputation": dict(self.reputation),
            "repeatable": self.repeatable,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.world_interaction" or data.get("version") != 1:
            raise ValueError("unsupported world interaction")
        values = {k: v for k, v in data.items() if k not in ("schema", "version")}
        values["requirements"] = tuple(values.get("requirements", ()))
        return cls(**values)
