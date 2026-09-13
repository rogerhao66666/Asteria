from __future__ import annotations

from dataclasses import dataclass, field

from asteria.gameplay import GameplayTrigger, StatModifier


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _ids(values, label):
    return tuple(dict.fromkeys(_id(x, label) for x in values))


@dataclass(frozen=True, slots=True)
class PassiveDefinition:
    passive_id: str
    display_name: str
    tags: tuple[str, ...] = ()
    modifiers: tuple[StatModifier, ...] = ()
    granted_abilities: tuple[str, ...] = ()
    triggers: tuple[GameplayTrigger, ...] = ()

    def __init__(self, passive_id, display_name=None, *, tags=(), modifiers=(), granted_abilities=(), triggers=()):
        passive_id = _id(passive_id, "passive_id")
        modifiers = tuple(modifiers)
        triggers = tuple(triggers)
        if any(not isinstance(x, StatModifier) for x in modifiers):
            raise TypeError("modifiers must be StatModifier values")
        if any(not isinstance(x, GameplayTrigger) for x in triggers):
            raise TypeError("triggers must be GameplayTrigger values")
        object.__setattr__(self, "passive_id", passive_id)
        object.__setattr__(self, "display_name", str(display_name or passive_id))
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags})))
        object.__setattr__(self, "modifiers", modifiers)
        object.__setattr__(self, "granted_abilities", _ids(granted_abilities, "ability_id"))
        object.__setattr__(self, "triggers", triggers)

    def to_data(self):
        return {
            "schema": "asteria.rpg.passive",
            "version": 1,
            "passive_id": self.passive_id,
            "display_name": self.display_name,
            "tags": list(self.tags),
            "modifiers": [x.to_data() for x in self.modifiers],
            "granted_abilities": list(self.granted_abilities),
            "triggers": [x.to_data() for x in self.triggers],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.passive" or data.get("version") != 1:
            raise ValueError("unsupported passive definition")
        return cls(
            data["passive_id"], data["display_name"], tags=data["tags"],
            modifiers=[StatModifier.from_data(x) for x in data["modifiers"]],
            granted_abilities=data["granted_abilities"],
            triggers=[GameplayTrigger.from_data(x) for x in data["triggers"]],
        )


@dataclass(frozen=True, slots=True)
class AbilityEvolutionRule:
    rule_id: str
    source_ability_id: str
    result_ability_id: str
    progression_track_id: str | None = None
    minimum_rank: int = 1
    priority: int = 0
    retain_source: bool = False

    def __init__(self, rule_id, source_ability_id, result_ability_id, *, progression_track_id=None, minimum_rank=1, priority=0, retain_source=False):
        object.__setattr__(self, "rule_id", _id(rule_id, "rule_id"))
        object.__setattr__(self, "source_ability_id", _id(source_ability_id, "source_ability_id"))
        object.__setattr__(self, "result_ability_id", _id(result_ability_id, "result_ability_id"))
        object.__setattr__(self, "progression_track_id", None if progression_track_id is None else _id(progression_track_id, "progression_track_id"))
        minimum_rank = int(minimum_rank)
        if minimum_rank < 1:
            raise ValueError("minimum_rank must be >= 1")
        object.__setattr__(self, "minimum_rank", minimum_rank)
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(self, "retain_source", bool(retain_source))

    def matches(self, progression):
        if self.progression_track_id is None:
            return True
        if progression is None or self.progression_track_id not in progression.definitions:
            return False
        return progression.rank(self.progression_track_id) >= self.minimum_rank

    def to_data(self):
        return {
            "schema": "asteria.rpg.ability_evolution",
            "version": 1,
            "rule_id": self.rule_id,
            "source_ability_id": self.source_ability_id,
            "result_ability_id": self.result_ability_id,
            "progression_track_id": self.progression_track_id,
            "minimum_rank": self.minimum_rank,
            "priority": self.priority,
            "retain_source": self.retain_source,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.ability_evolution" or data.get("version") != 1:
            raise ValueError("unsupported ability evolution rule")
        return cls(
            data["rule_id"], data["source_ability_id"], data["result_ability_id"],
            progression_track_id=data["progression_track_id"], minimum_rank=data["minimum_rank"],
            priority=data["priority"], retain_source=data["retain_source"],
        )


@dataclass(slots=True)
class ActorAbilityState:
    learned_abilities: tuple[str, ...] = ()
    active_passives: tuple[str, ...] = ()
    selected_evolutions: dict[str, str] = field(default_factory=dict)

    def __init__(self, *, learned_abilities=(), active_passives=(), selected_evolutions=None):
        self.learned_abilities = _ids(learned_abilities, "ability_id")
        self.active_passives = _ids(active_passives, "passive_id")
        selected = {}
        for source, rule in dict(selected_evolutions or {}).items():
            selected[_id(source, "source_ability_id")] = _id(rule, "evolution rule_id")
        self.selected_evolutions = selected

    def learn(self, ability_id):
        ability_id = _id(ability_id, "ability_id")
        if ability_id not in self.learned_abilities:
            self.learned_abilities = self.learned_abilities + (ability_id,)
        return ability_id

    def forget(self, ability_id):
        ability_id = str(ability_id)
        self.learned_abilities = tuple(x for x in self.learned_abilities if x != ability_id)

    def equip_passive(self, passive_id, *, capacity=None):
        passive_id = _id(passive_id, "passive_id")
        if passive_id in self.active_passives:
            return passive_id
        if capacity is not None and len(self.active_passives) >= int(capacity):
            raise ValueError("passive loadout is full")
        self.active_passives = self.active_passives + (passive_id,)
        return passive_id

    def unequip_passive(self, passive_id):
        passive_id = str(passive_id)
        self.active_passives = tuple(x for x in self.active_passives if x != passive_id)

    def select_evolution(self, source_ability_id, rule_id):
        self.selected_evolutions[_id(source_ability_id, "source_ability_id")] = _id(rule_id, "rule_id")

    def to_data(self):
        return {
            "schema": "asteria.rpg.actor_ability_state",
            "version": 1,
            "learned_abilities": list(self.learned_abilities),
            "active_passives": list(self.active_passives),
            "selected_evolutions": dict(sorted(self.selected_evolutions.items())),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.actor_ability_state" or data.get("version") != 1:
            raise ValueError("unsupported actor ability state")
        return cls(
            learned_abilities=data["learned_abilities"],
            active_passives=data["active_passives"],
            selected_evolutions=data["selected_evolutions"],
        )


@dataclass(frozen=True, slots=True)
class AbilityGrant:
    ability_id: str
    source_kind: str
    source_id: str


@dataclass(frozen=True, slots=True)
class AbilityResolution:
    abilities: tuple[str, ...]
    grants: tuple[AbilityGrant, ...]

    def sources_for(self, ability_id):
        return tuple(x for x in self.grants if x.ability_id == ability_id)
