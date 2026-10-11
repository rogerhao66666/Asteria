"""Long-lived world state: faction reputation, relationships, achievements and the bestiary (ASTERIA_SPEC §26).

Definitions (factions, achievements) live in the RPG database; the mutable
:class:`WorldRecord` lives in the save.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


@dataclass(frozen=True, slots=True)
class FactionDefinition:
    """A reputation track with a clamp range and named ranks (``(threshold, name)``, ascending)."""

    faction_id: str
    display_name: str
    minimum: float
    maximum: float
    initial: float
    ranks: tuple[tuple[float, str], ...]

    def __init__(self, faction_id, display_name=None, *, minimum=-100.0, maximum=100.0, initial=0.0, ranks=()):
        minimum, maximum, initial = float(minimum), float(maximum), float(initial)
        if not all(isfinite(x) for x in (minimum, maximum, initial)) or minimum > maximum:
            raise ValueError("faction range is invalid")
        if not minimum <= initial <= maximum:
            raise ValueError("initial reputation must be inside the range")
        ranks = tuple(sorted((float(t), _id(n, "rank name")) for t, n in ranks))
        object.__setattr__(self, "faction_id", _id(faction_id, "faction_id"))
        object.__setattr__(self, "display_name", str(display_name or faction_id))
        object.__setattr__(self, "minimum", minimum)
        object.__setattr__(self, "maximum", maximum)
        object.__setattr__(self, "initial", initial)
        object.__setattr__(self, "ranks", ranks)

    def rank(self, value):
        name = ""
        for threshold, rank_name in self.ranks:
            if value >= threshold:
                name = rank_name
        return name

    def to_data(self):
        return {
            "schema": "asteria.rpg.faction",
            "version": 1,
            "faction_id": self.faction_id,
            "display_name": self.display_name,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "initial": self.initial,
            "ranks": [[t, n] for t, n in self.ranks],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.faction" or data.get("version") != 1:
            raise ValueError("unsupported faction")
        return cls(
            data["faction_id"],
            data["display_name"],
            minimum=data["minimum"],
            maximum=data["maximum"],
            initial=data["initial"],
            ranks=data["ranks"],
        )


ACHIEVEMENT_KINDS = ("switch", "counter", "defeated", "reputation", "quest")


@dataclass(frozen=True, slots=True)
class AchievementDefinition:
    """Unlocks when its condition holds.

    kinds: ``switch`` (event switch ``target`` on), ``counter`` (record counter
    ``target`` >= ``value``), ``defeated`` (enemy ``target`` defeated
    ``value`` times), ``reputation`` (faction ``target`` >= ``value``),
    ``quest`` (quest ``target`` completed).
    """

    achievement_id: str
    display_name: str
    description: str
    kind: str
    target: str
    value: float
    hidden: bool

    def __init__(
        self, achievement_id, display_name=None, *, description="", kind="switch", target, value=1.0, hidden=False
    ):
        if kind not in ACHIEVEMENT_KINDS:
            raise ValueError(f"unknown achievement kind: {kind}")
        value = float(value)
        if not isfinite(value):
            raise ValueError("achievement value must be finite")
        object.__setattr__(self, "achievement_id", _id(achievement_id, "achievement_id"))
        object.__setattr__(self, "display_name", str(display_name or achievement_id))
        object.__setattr__(self, "description", str(description))
        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "target", _id(target, "achievement target"))
        object.__setattr__(self, "value", value)
        object.__setattr__(self, "hidden", bool(hidden))

    def to_data(self):
        return {
            "schema": "asteria.rpg.achievement",
            "version": 1,
            "achievement_id": self.achievement_id,
            "display_name": self.display_name,
            "description": self.description,
            "kind": self.kind,
            "target": self.target,
            "value": self.value,
            "hidden": self.hidden,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.achievement" or data.get("version") != 1:
            raise ValueError("unsupported achievement")
        return cls(
            data["achievement_id"],
            data["display_name"],
            description=data["description"],
            kind=data["kind"],
            target=data["target"],
            value=data["value"],
            hidden=data["hidden"],
        )


@dataclass(slots=True)
class WorldRecord:
    """Saved world state; ``bestiary`` maps enemy id -> {"seen": n, "defeated": n, "captured": n}.

    ``known_recipes`` lists discovered recipes that require discovery.
    """

    reputation: dict = field(default_factory=dict)
    relationships: dict = field(default_factory=dict)
    counters: dict = field(default_factory=dict)
    achievements: list = field(default_factory=list)
    bestiary: dict = field(default_factory=dict)
    known_recipes: list = field(default_factory=list)
    # WLD-02: per-NPC saved state, npc_id -> {scene_id, position, facing, visible, alive, mood, stage, flags}
    npcs: dict = field(default_factory=dict)

    SCHEMA = "asteria.rpg.world_record"

    def npc(self, npc_id):
        """The saved state of ``npc_id`` (created with defaults on first use)."""
        return self.npcs.setdefault(
            _id(npc_id, "npc id"),
            {
                "scene_id": None,
                "position": None,
                "facing": None,
                "visible": True,
                "alive": True,
                "mood": "",
                "stage": 0,
                "flags": {},
            },
        )

    def npc_value(self, npc_id, key):
        """``visible``, ``alive``, ``mood``, ``stage``, ``scene_id`` or ``flag.<name>`` of an NPC."""
        state = self.npcs.get(str(npc_id))
        if state is None:
            return {"visible": True, "alive": True, "mood": "", "stage": 0}.get(key)
        if key.startswith("flag."):
            return state["flags"].get(key[5:])
        return state.get(key)

    def change_reputation(self, faction, amount):
        value = self.reputation.get(faction.faction_id, faction.initial) + float(amount)
        self.reputation[faction.faction_id] = min(faction.maximum, max(faction.minimum, value))
        return self.reputation[faction.faction_id]

    def reputation_of(self, faction):
        return self.reputation.get(faction.faction_id, faction.initial)

    def change_relationship(self, subject_id, amount):
        subject_id = _id(subject_id, "relationship subject")
        self.relationships[subject_id] = self.relationships.get(subject_id, 0.0) + float(amount)
        return self.relationships[subject_id]

    def add_counter(self, counter_id, amount=1):
        counter_id = _id(counter_id, "counter id")
        self.counters[counter_id] = self.counters.get(counter_id, 0.0) + float(amount)
        return self.counters[counter_id]

    def note_enemy(self, enemy_id, key, amount=1):
        entry = self.bestiary.setdefault(_id(enemy_id, "enemy id"), {"seen": 0, "defeated": 0, "captured": 0})
        entry[key] = entry.get(key, 0) + int(amount)
        return entry

    def achievement_met(self, achievement, *, factions, switches, quest_status):
        kind, target = achievement.kind, achievement.target
        if kind == "switch":
            return bool(switches(target))
        if kind == "counter":
            return self.counters.get(target, 0.0) >= achievement.value
        if kind == "defeated":
            return self.bestiary.get(target, {}).get("defeated", 0) >= achievement.value
        if kind == "reputation":
            faction = factions.get(target)
            return faction is not None and self.reputation_of(faction) >= achievement.value
        return quest_status(target) == "completed"

    def unlock_ready(self, achievements, *, factions, switches, quest_status):
        """Unlock every achievement whose condition now holds; returns the newly unlocked ids."""
        unlocked = []
        for achievement_id in sorted(achievements):
            if achievement_id in self.achievements:
                continue
            if self.achievement_met(
                achievements[achievement_id], factions=factions, switches=switches, quest_status=quest_status
            ):
                self.achievements.append(achievement_id)
                unlocked.append(achievement_id)
        return tuple(unlocked)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": 2,
            "reputation": dict(sorted(self.reputation.items())),
            "relationships": dict(sorted(self.relationships.items())),
            "counters": dict(sorted(self.counters.items())),
            "achievements": list(self.achievements),
            "bestiary": {k: dict(sorted(v.items())) for k, v in sorted(self.bestiary.items())},
            "known_recipes": sorted(self.known_recipes),
            "npcs": {k: dict(v, flags=dict(sorted(v["flags"].items()))) for k, v in sorted(self.npcs.items())},
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") not in (1, 2):
            raise ValueError("unsupported world record")
        return cls(
            {str(k): float(v) for k, v in data["reputation"].items()},
            {str(k): float(v) for k, v in data["relationships"].items()},
            {str(k): float(v) for k, v in data["counters"].items()},
            [str(x) for x in data["achievements"]],
            {str(k): {str(a): int(b) for a, b in v.items()} for k, v in data["bestiary"].items()},
            [str(x) for x in data.get("known_recipes", ())],
            {str(k): dict(v, flags=dict(v.get("flags", {}))) for k, v in data.get("npcs", {}).items()},
        )
