from __future__ import annotations

from dataclasses import dataclass

from .abilities import AbilityDefinition, AbilityRegistry
from .action_timeline import ActionTimeline
from .attacks import AttackDefinition
from .formulas import ValueFormula
from .states import StateDefinition, StateRegistry
from .triggers import GameplayTrigger


@dataclass(slots=True)
class GameplayLibrary:
    """Canonical gameplay definition library.

    Presets create ordinary values stored here; runtime never treats presets
    specially.
    """

    abilities: AbilityRegistry
    states: StateRegistry
    formulas: dict[str, ValueFormula]
    triggers: dict[str, GameplayTrigger]
    timelines: dict[str, ActionTimeline]
    attacks: dict[str, AttackDefinition]

    def __init__(self):
        self.abilities = AbilityRegistry()
        self.states = StateRegistry()
        self.formulas = {}
        self.triggers = {}
        self.timelines = {}
        self.attacks = {}

    def add_formula(self, key, formula):
        key = str(key).strip()
        if not key or key in self.formulas:
            raise ValueError(f"duplicate formula: {key}")
        if not isinstance(formula, ValueFormula):
            raise TypeError("formula must be ValueFormula")
        self.formulas[key] = formula
        return formula

    def add_ability(self, definition):
        return self.abilities.register(definition)

    def add_state(self, definition):
        return self.states.register(definition)

    def add_trigger(self, trigger):
        if not isinstance(trigger, GameplayTrigger):
            raise TypeError("trigger must be GameplayTrigger")
        if trigger.trigger_id in self.triggers:
            raise ValueError(f"duplicate trigger: {trigger.trigger_id}")
        self.triggers[trigger.trigger_id] = trigger
        return trigger

    def add_timeline(self, timeline):
        if not isinstance(timeline, ActionTimeline):
            raise TypeError("timeline must be ActionTimeline")
        if timeline.timeline_id in self.timelines:
            raise ValueError(f"duplicate timeline: {timeline.timeline_id}")
        self.timelines[timeline.timeline_id] = timeline
        return timeline

    def add_attack(self, attack):
        if not isinstance(attack, AttackDefinition):
            raise TypeError("attack must be AttackDefinition")
        if attack.attack_id in self.attacks:
            raise ValueError(f"duplicate attack: {attack.attack_id}")
        self.attacks[attack.attack_id] = attack
        return attack

    def to_data(self):
        return {
            "schema": "asteria.gameplay_library",
            "version": 2,
            "formulas": {k: self.formulas[k].to_data() for k in sorted(self.formulas)},
            "abilities": [self.abilities.require(k).to_data() for k in self.abilities.ids()],
            "states": [self.states.require(k).to_data() for k in self.states.ids()],
            "triggers": [self.triggers[k].to_data() for k in sorted(self.triggers)],
            "timelines": [self.timelines[k].to_data() for k in sorted(self.timelines)],
            "attacks": [self.attacks[k].to_data() for k in sorted(self.attacks)],
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "formulas",
            "abilities",
            "states",
            "triggers",
            "timelines",
        }
        if data.get("schema") != "asteria.gameplay_library" or data.get("version") not in {1, 2}:
            raise ValueError("unsupported gameplay library")
        if data["version"] >= 2:
            expected = expected | {"attacks"}  # v2 adds attacks
        if set(data) != expected:
            raise ValueError("invalid gameplay library")
        result = cls()
        for k, v in data["formulas"].items():
            result.add_formula(k, ValueFormula.from_data(v))
        for x in data["abilities"]:
            result.add_ability(AbilityDefinition.from_data(x))
        for x in data["states"]:
            result.add_state(StateDefinition.from_data(x))
        for x in data["triggers"]:
            result.add_trigger(GameplayTrigger.from_data(x))
        for x in data["timelines"]:
            result.add_timeline(ActionTimeline.from_data(x))
        for x in data.get("attacks", ()):
            result.add_attack(AttackDefinition.from_data(x))
        return result
