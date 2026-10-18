"""Ability slots: only some of an actor's learned abilities can be used at once.

``AbilityLoadoutRules`` limits abilities that come from the listed grant sources (``learned`` by
default - a skill the actor learned, as opposed to a class or equipment grant) to the ones the
actor has *equipped*, up to ``capacity`` (growing with level through ``capacity_by_level``). It is
project data; without rules every learned ability is usable as before.
"""

from __future__ import annotations

from dataclasses import dataclass


def _text(value):
    return str(value or "").strip()


@dataclass(frozen=True, slots=True)
class AbilityLoadoutRules:
    rules_id: str
    capacity: int = 4
    capacity_by_level: tuple[tuple[int, int], ...] = ()
    limited_sources: tuple[str, ...] = ("learned",)
    always_usable: tuple[str, ...] = ()

    def __init__(
        self,
        rules_id,
        capacity=4,
        *,
        capacity_by_level=None,
        limited_sources=("learned",),
        always_usable=(),
    ):
        rules_id = _text(rules_id)
        if not rules_id:
            raise ValueError("rules_id is required")
        capacity = int(capacity)
        if capacity < 0:
            raise ValueError("capacity must be >= 0")
        steps = []
        for level, slots in dict(capacity_by_level or {}).items():
            level, slots = int(level), int(slots)
            if level < 1 or slots < 0:
                raise ValueError("capacity_by_level needs levels >= 1 and slots >= 0")
            steps.append((level, slots))
        s = object.__setattr__
        s(self, "rules_id", rules_id)
        s(self, "capacity", capacity)
        s(self, "capacity_by_level", tuple(sorted(steps)))
        s(self, "limited_sources", tuple(dict.fromkeys(_text(x) for x in limited_sources if x)))
        s(self, "always_usable", tuple(dict.fromkeys(_text(x) for x in always_usable if x)))

    def capacity_at(self, level):
        """Slots at ``level``: the base capacity, or the highest level step reached."""
        slots = self.capacity
        for threshold, value in self.capacity_by_level:
            if int(level) >= threshold:
                slots = value
        return slots

    def usable(self, grants, equipped):
        """Ability ids (in grant order) that stay usable: unlimited sources, ``always_usable``,
        and limited ones that are equipped. ``grants`` are ``AbilityGrant`` values."""
        kept = []
        limited = set(self.limited_sources)
        for grant in grants:
            ability_id = grant.ability_id
            if ability_id in kept:
                continue
            if (
                grant.source_kind not in limited
                or ability_id in self.always_usable
                or ability_id in equipped
            ):
                kept.append(ability_id)
        return tuple(kept)

    def filter(self, abilities, grants, equipped):
        """``abilities`` (a build's final list: evolutions already replaced their bases) without
        the slot-limited ones that are not equipped. An ability some unlimited source also grants
        stays."""
        allowed = set(self.usable(grants, equipped))
        limited = {g.ability_id for g in grants} - allowed
        return tuple(a for a in abilities if a not in limited)

    def to_data(self):
        return {
            "schema": "asteria.rpg.ability_loadout_rules",
            "version": 1,
            "rules_id": self.rules_id,
            "capacity": self.capacity,
            **(
                {"capacity_by_level": {str(k): v for k, v in self.capacity_by_level}}
                if self.capacity_by_level
                else {}
            ),
            "limited_sources": list(self.limited_sources),
            **({"always_usable": list(self.always_usable)} if self.always_usable else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.ability_loadout_rules" or data.get("version") != 1:
            raise ValueError("unsupported ability loadout rules")
        return cls(
            data["rules_id"],
            data.get("capacity", 4),
            capacity_by_level=data.get("capacity_by_level"),
            limited_sources=data.get("limited_sources", ("learned",)),
            always_usable=data.get("always_usable", ()),
        )
