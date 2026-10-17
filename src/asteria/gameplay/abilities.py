from __future__ import annotations

import copy
from dataclasses import dataclass
from enum import Enum
from math import isfinite

from .conditions import (
    ConditionGroup,
    GameplayCondition,
    GameplayConditionContext,
    GameplaySubject,
    deserialize_condition,
    serialize_condition,
)
from .effects import Effect, EffectApplicationResult, apply_effect
from .formulas import FormulaContext, ValueFormula
from .stats import ResourcePool, StatBlock
from .tags import TagSet, normalize_tag


def _clean_kill(value):
    """Validate a hit's instant-KO block: chance, the resource to zero, optional immunity."""
    value = dict(value)
    unknown = set(value) - {"chance", "resource", "immune_tags", "immune_fraction"}
    if unknown:
        raise ValueError(f"unknown kill fields: {sorted(unknown)}")
    chance = float(value.get("chance", 1.0))
    fraction = float(value.get("immune_fraction", 0.0))
    if not 0.0 <= chance <= 1.0 or not 0.0 <= fraction <= 1.0:
        raise ValueError("kill chance and immune_fraction must be between 0 and 1")
    resource = str(value.get("resource", "")).strip()
    if not resource:
        raise ValueError("kill needs a resource")
    clean = {"chance": chance, "resource": resource}
    tags = sorted({normalize_tag(t) for t in value.get("immune_tags", ())})
    if tags:
        clean["immune_tags"] = tags
    if fraction:
        clean["immune_fraction"] = fraction
    return clean


class AbilityTargetMode(str, Enum):
    SELF = "self"
    SELECTED = "selected"


@dataclass(frozen=True, slots=True)
class AbilityTarget:
    target_id: str
    subject: GameplaySubject

    def __init__(self, target_id, subject):
        target_id = str(target_id).strip()
        if not target_id:
            raise ValueError("target_id is required")
        if not isinstance(subject, GameplaySubject):
            raise TypeError("subject must be GameplaySubject")
        object.__setattr__(self, "target_id", target_id)
        object.__setattr__(self, "subject", subject)


@dataclass(frozen=True, slots=True)
class TargetingRule:
    minimum_targets: int = 1
    maximum_targets: int = 1
    allow_self: bool = False
    required_tags: tuple[str, ...] = ()
    blocked_tags: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        minimum_targets=1,
        maximum_targets=1,
        allow_self=False,
        required_tags=(),
        blocked_tags=(),
    ):
        minimum_targets = int(minimum_targets)
        maximum_targets = int(maximum_targets)
        if minimum_targets < 0:
            raise ValueError("minimum_targets must be >= 0")
        if maximum_targets < minimum_targets:
            raise ValueError("maximum_targets must be >= minimum_targets")
        object.__setattr__(self, "minimum_targets", minimum_targets)
        object.__setattr__(self, "maximum_targets", maximum_targets)
        object.__setattr__(self, "allow_self", bool(allow_self))
        object.__setattr__(
            self,
            "required_tags",
            tuple(sorted({normalize_tag(x) for x in required_tags})),
        )
        object.__setattr__(
            self,
            "blocked_tags",
            tuple(sorted({normalize_tag(x) for x in blocked_tags})),
        )

    def validate(
        self,
        source: AbilityTarget,
        targets: tuple[AbilityTarget, ...],
    ) -> tuple[str, ...]:
        errors = []
        if len(targets) < self.minimum_targets:
            errors.append("too_few_targets")
        if len(targets) > self.maximum_targets:
            errors.append("too_many_targets")

        seen = set()
        for target in targets:
            if target.target_id in seen:
                errors.append(f"duplicate_target:{target.target_id}")
                continue
            seen.add(target.target_id)

            if not self.allow_self and target.target_id == source.target_id:
                errors.append(f"self_target_not_allowed:{target.target_id}")
            if not target.subject.tags.contains_all(self.required_tags):
                errors.append(f"missing_required_tags:{target.target_id}")
            if target.subject.tags.contains_any(self.blocked_tags):
                errors.append(f"blocked_tags:{target.target_id}")
        return tuple(errors)

    def to_data(self):
        return {
            "minimum_targets": self.minimum_targets,
            "maximum_targets": self.maximum_targets,
            "allow_self": self.allow_self,
            "required_tags": list(self.required_tags),
            "blocked_tags": list(self.blocked_tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "minimum_targets",
            "maximum_targets",
            "allow_self",
            "required_tags",
            "blocked_tags",
        }
        if set(data) != expected:
            raise ValueError("invalid targeting rule")
        return cls(**data)


@dataclass(frozen=True, slots=True)
class AbilityCost:
    resource: str
    amount: ValueFormula

    def __init__(self, resource, amount):
        resource = str(resource).strip()
        if not resource:
            raise ValueError("cost resource is required")
        if isinstance(amount, (int, float)):
            amount = ValueFormula.constant(amount)
        if not isinstance(amount, ValueFormula):
            raise TypeError("amount must be ValueFormula or number")
        object.__setattr__(self, "resource", resource)
        object.__setattr__(self, "amount", amount)

    def to_data(self):
        return {
            "resource": self.resource,
            "amount": self.amount.to_data(),
        }

    @classmethod
    def from_data(cls, data):
        if set(data) != {"resource", "amount"}:
            raise ValueError("invalid ability cost")
        return cls(data["resource"], ValueFormula.from_data(data["amount"]))


@dataclass(frozen=True, slots=True)
class AbilityEffect:
    mode: AbilityTargetMode
    effect: Effect

    def __init__(self, mode, effect):
        if not isinstance(effect, Effect):
            raise TypeError("effect must be Effect")
        object.__setattr__(self, "mode", AbilityTargetMode(mode))
        object.__setattr__(self, "effect", effect)

    def to_data(self):
        return {"mode": self.mode.value, "effect": self.effect.to_data()}

    @classmethod
    def from_data(cls, data):
        if set(data) != {"mode", "effect"}:
            raise ValueError("invalid ability effect")
        return cls(data["mode"], Effect.from_data(data["effect"]))


def _clean_forms(forms):
    """Validate and normalise the casting forms of a skill."""
    clean, seen = [], set()
    for raw in forms or ():
        raw = dict(raw)
        unknown = set(raw) - {
            "form_id",
            "label",
            "tags",
            "power",
            "resource_costs",
            "battle_costs",
            "apply_states",
        }
        if unknown:
            raise ValueError(f"unknown form fields: {sorted(unknown)}")
        form_id = str(raw.get("form_id", "")).strip()
        if not form_id or form_id in seen:
            raise ValueError("each form needs its own form_id")
        seen.add(form_id)
        power = float(raw.get("power", 1.0))
        if not isfinite(power) or power <= 0:
            raise ValueError("form power must be > 0")
        entry = {"form_id": form_id, "label": str(raw.get("label") or form_id)}
        tags = sorted({normalize_tag(t) for t in raw.get("tags", ()) if str(t).strip()})
        if tags:
            entry["tags"] = tags
        if power != 1.0:
            entry["power"] = power
        for key in ("resource_costs", "battle_costs"):
            costs = {str(k).strip(): float(v) for k, v in dict(raw.get(key) or {}).items()}
            if any(not k or v < 0 or not isfinite(v) for k, v in costs.items()):
                raise ValueError(f"form {key} needs resource ids and amounts >= 0")
            if costs:
                entry[key] = costs
        if raw.get("apply_states"):
            entry["apply_states"] = [dict(x) for x in raw["apply_states"]]
        clean.append(entry)
    return tuple(clean)


@dataclass(frozen=True, slots=True)
class AbilityDefinition:
    ability_id: str
    targeting: TargetingRule
    costs: tuple[AbilityCost, ...] = ()
    conditions: GameplayCondition | None = None
    effects: tuple[AbilityEffect, ...] = ()
    tags: tuple[str, ...] = ()
    # Turns of its user before the ability can be used again (0 = none). Left out of the data while
    # 0.
    cooldown_turns: int = 0
    # Battle extras, all optional and left out of the data while empty:
    # battle_costs           {resource: amount} paid from battle resources (e.g. boost points)
    # hits                   [{"tags": [...], "power": 1.0}] - the action lands once per hit; each
    # hit adds its
    # tags (damage types) for the interaction rules and scales the damage by its power
    # battle_resource_gains  [{"to": "self" | "targets" | "allies", "resource": id, "amount": n}]
    # after the action
    # commands               [{"command": "SUMMON", "args": {...}}] world commands run after the
    # action;
    #                        "@actor" / "@target" in string args are replaced by member ids
    # concoct_station        the action combines ingredients the player picks (recipes of that
    # station)
    # apply_states           [{"state": id, "to": "targets" | "self" | "allies", "remove": false}]
    # after the
    # action: states go through the battle's state policies (chance, immunity, duration)
    battle_costs: dict = None
    hits: tuple = ()
    battle_resource_gains: tuple = ()
    commands: tuple = ()
    concoct_station: str = ""
    apply_states: tuple = ()
    # real-time use (ASTERIA_SPEC §20; runtime.action_combat):
    # timeline_id            action timeline played when the ability is used in real time
    # cooldown_seconds       seconds before it can be used again (turn-based battles use
    # cooldown_turns)
    # move_while_acting      movement speed kept while its action runs: 0 rooted, 1 free, between =
    # slowed
    # interrupts_actions     it may cut the user's running action at any moment (dodges), not only
    # in cancel windows
    timeline_id: str = ""
    cooldown_seconds: float = 0.0
    move_while_acting: float = 0.0
    interrupts_actions: bool = False
    cooldown_formula: object = (
        None  # ValueFormula over the user's stats; replaces cooldown_seconds when set
    )
    # shown on action bars and menus; written to the data only when set
    display_name: str = ""
    icon_id: str = ""
    # items the user must own (not spent) for the ability to be usable, {item id: count} - a
    # captured pet an action sends out, a key that opens a technique. Written only when set.
    requires_items: dict = None
    # what a cast spends besides resources: items {item id: count} and currency {id: amount},
    # taken once per cast (not per hit); the ability is unusable without them. Written only
    # when set.
    item_costs: dict = None
    currency_costs: dict = None
    # party-wide gauges a cast spends ({gauge id: amount}, see Battle Extras shared gauges)
    gauge_costs: dict = None
    # the damage type follows what the user carries: {tag the user has: tag the hits deal while
    # it is there}, e.g. {"equip.sword": "weapon.sword", "equip.bow": "weapon.bow"} makes one
    # skill hit as whichever weapon is wielded. Written only when set.
    follow_tags: dict = None
    # ways to cast the skill, chosen when it is used: [{"form_id", "label", "tags": [...] added
    # to every hit, "power": strength factor, "resource_costs": {resource: amount} and
    # "battle_costs": {resource: amount} on top of the skill's own, "apply_states": [...]}].
    # Written only when set.
    forms: tuple = ()
    # a pet the user must own and send out: "any" (the active pet, whatever its species) or a
    # species id. The pet's stats are read in formulas as pet_<stat> and pet_level.
    requires_pet: str = ""
    # the battle menu group the ability is listed under ("" = the default Skills group): a
    # project's Magic / Special / Tech groups, each shown as one more command category
    menu_category: str = ""
    OPTIONAL_DATA = {
        "menu_category": "",
        "requires_pet": "",
        "requires_items": {},
        "item_costs": {},
        "currency_costs": {},
        "gauge_costs": {},
        "follow_tags": {},
        "forms": [],
        "display_name": "",
        "icon_id": "",
        "cooldown_turns": 0,
        "battle_costs": {},
        "hits": [],
        "battle_resource_gains": [],
        "commands": [],
        "concoct_station": "",
        "apply_states": [],
        "timeline_id": "",
        "cooldown_seconds": 0.0,
        "move_while_acting": 0.0,
        "interrupts_actions": False,
        "cooldown_formula": None,
    }

    def __init__(
        self,
        ability_id,
        *,
        targeting=None,
        costs=(),
        conditions=None,
        effects=(),
        tags=(),
        cooldown_turns=0,
        battle_costs=None,
        hits=(),
        battle_resource_gains=(),
        commands=(),
        concoct_station="",
        apply_states=(),
        timeline_id="",
        cooldown_seconds=0.0,
        move_while_acting=0.0,
        interrupts_actions=False,
        cooldown_formula=None,
        display_name="",
        icon_id="",
        requires_items=None,
        item_costs=None,
        currency_costs=None,
        gauge_costs=None,
        follow_tags=None,
        forms=(),
        requires_pet="",
        menu_category="",
    ):
        ability_id = str(ability_id).strip()
        if not ability_id:
            raise ValueError("ability_id is required")
        if targeting is None:
            targeting = TargetingRule()
        if not isinstance(targeting, TargetingRule):
            raise TypeError("targeting must be TargetingRule")
        costs = tuple(costs)
        effects = tuple(effects)
        if any(not isinstance(x, AbilityCost) for x in costs):
            raise TypeError("costs must be AbilityCost values")
        if any(not isinstance(x, AbilityEffect) for x in effects):
            raise TypeError("effects must be AbilityEffect values")
        if conditions is None:
            conditions = ConditionGroup(())
        if not isinstance(conditions, GameplayCondition):
            raise TypeError("conditions must be GameplayCondition")
        object.__setattr__(self, "ability_id", ability_id)
        object.__setattr__(self, "targeting", targeting)
        object.__setattr__(self, "costs", costs)
        object.__setattr__(self, "conditions", conditions)
        object.__setattr__(self, "effects", effects)
        object.__setattr__(self, "tags", tuple(sorted({normalize_tag(x) for x in tags})))
        cooldown_turns = int(cooldown_turns)
        if cooldown_turns < 0:
            raise ValueError("cooldown_turns must be >= 0")
        object.__setattr__(self, "cooldown_turns", cooldown_turns)
        battle_costs = {str(k): float(v) for k, v in dict(battle_costs or {}).items()}
        if any(v < 0 for v in battle_costs.values()):
            raise ValueError("battle_costs must be >= 0")
        object.__setattr__(self, "battle_costs", battle_costs)
        clean_hits = []
        for hit in hits:
            hit = dict(hit)
            unknown = set(hit) - {"tags", "power", "checks", "kill"}
            if unknown:
                raise ValueError(f"unknown hit fields: {sorted(unknown)}")
            clean = {
                "tags": sorted({normalize_tag(t) for t in hit.get("tags", ())}),
                "power": float(hit.get("power", 1.0)),
            }
            checks = [str(c).strip() for c in hit.get("checks", ()) if str(c).strip()]
            if checks:
                clean["checks"] = checks
            kill = dict(hit.get("kill") or {})
            if kill and (kill.get("resource") or float(kill.get("chance", 1.0)) > 0):
                clean["kill"] = _clean_kill(kill)  # a blank editor template stays out
            clean_hits.append(clean)
        object.__setattr__(self, "hits", tuple(clean_hits))
        gains = []
        for gain in battle_resource_gains:
            gain = dict(gain)
            if gain.get("to", "self") not in ("self", "targets", "allies"):
                raise ValueError('battle_resource_gains "to" must be self, targets or allies')
            if not str(gain.get("resource", "")).strip():
                raise ValueError("battle_resource_gains need a resource")
            gains.append(
                {
                    "to": gain.get("to", "self"),
                    "resource": str(gain["resource"]),
                    "amount": float(gain.get("amount", 1)),
                }
            )
        object.__setattr__(self, "battle_resource_gains", tuple(gains))
        clean_commands = []
        for command in commands:
            command = dict(command)
            if not str(command.get("command", "")).strip():
                raise ValueError("commands need a command name")
            clean_commands.append(
                {
                    "command": str(command["command"]).strip().upper(),
                    "args": dict(command.get("args", {})),
                }
            )
        object.__setattr__(self, "commands", tuple(clean_commands))
        object.__setattr__(self, "concoct_station", str(concoct_station or "").strip())
        states = []
        for entry in apply_states:
            entry = dict(entry)
            if not str(entry.get("state", "")).strip():
                raise ValueError("apply_states entries need a state")
            if entry.get("to", "targets") not in ("self", "targets", "allies"):
                raise ValueError('apply_states "to" must be self, targets or allies')
            states.append(
                {
                    "state": str(entry["state"]),
                    "to": entry.get("to", "targets"),
                    "remove": bool(entry.get("remove", False)),
                }
            )
        object.__setattr__(self, "apply_states", tuple(states))
        object.__setattr__(self, "timeline_id", str(timeline_id or "").strip())
        cooldown_seconds = float(cooldown_seconds)
        if not cooldown_seconds >= 0.0 or cooldown_seconds == float("inf"):
            raise ValueError("cooldown_seconds must be finite and >= 0")
        object.__setattr__(self, "cooldown_seconds", cooldown_seconds)
        move_while_acting = float(move_while_acting)
        if not move_while_acting >= 0.0 or move_while_acting == float("inf"):
            raise ValueError("move_while_acting must be finite and >= 0")
        object.__setattr__(self, "move_while_acting", move_while_acting)
        object.__setattr__(self, "interrupts_actions", bool(interrupts_actions))
        if cooldown_formula is not None and not isinstance(cooldown_formula, ValueFormula):
            raise TypeError("cooldown_formula must be ValueFormula")
        object.__setattr__(self, "cooldown_formula", cooldown_formula)
        object.__setattr__(self, "display_name", str(display_name or "").strip())
        object.__setattr__(self, "icon_id", str(icon_id or "").strip())
        needs = {str(k).strip(): int(v) for k, v in dict(requires_items or {}).items()}
        if any(not k or v < 1 for k, v in needs.items()):
            raise ValueError("requires_items needs item ids and counts >= 1")
        object.__setattr__(self, "requires_items", needs)
        follow = {normalize_tag(k): normalize_tag(v) for k, v in dict(follow_tags or {}).items()}
        object.__setattr__(self, "follow_tags", follow)
        object.__setattr__(self, "forms", _clean_forms(forms))
        for label, raw in (("item_costs", item_costs), ("currency_costs", currency_costs)):
            spent = {str(k).strip(): float(v) for k, v in dict(raw or {}).items()}
            if any(not k or v <= 0 or not isfinite(v) for k, v in spent.items()):
                raise ValueError(f"{label} needs ids and amounts > 0")
            if label == "item_costs":
                spent = {k: int(v) for k, v in spent.items()}
            object.__setattr__(self, label, spent)
        gauges = {str(k).strip(): float(v) for k, v in dict(gauge_costs or {}).items()}
        if any(not k or v <= 0 or not isfinite(v) for k, v in gauges.items()):
            raise ValueError("gauge_costs needs ids and amounts > 0")
        object.__setattr__(self, "gauge_costs", gauges)
        object.__setattr__(self, "requires_pet", str(requires_pet or "").strip())
        object.__setattr__(self, "menu_category", str(menu_category or "").strip())

    def to_data(self):
        return {
            "schema": "asteria.ability_definition",
            "version": 1,
            "ability_id": self.ability_id,
            "targeting": self.targeting.to_data(),
            "costs": [x.to_data() for x in self.costs],
            "conditions": serialize_condition(self.conditions),
            "effects": [x.to_data() for x in self.effects],
            "tags": list(self.tags),
            **({"cooldown_turns": self.cooldown_turns} if self.cooldown_turns else {}),
            **({"battle_costs": dict(self.battle_costs)} if self.battle_costs else {}),
            **({"hits": [dict(h) for h in self.hits]} if self.hits else {}),
            **(
                {"battle_resource_gains": [dict(g) for g in self.battle_resource_gains]}
                if self.battle_resource_gains
                else {}
            ),
            **({"commands": [dict(c) for c in self.commands]} if self.commands else {}),
            **({"concoct_station": self.concoct_station} if self.concoct_station else {}),
            **(
                {"apply_states": [dict(x) for x in self.apply_states]} if self.apply_states else {}
            ),
            **({"timeline_id": self.timeline_id} if self.timeline_id else {}),
            **({"cooldown_seconds": self.cooldown_seconds} if self.cooldown_seconds else {}),
            **({"move_while_acting": self.move_while_acting} if self.move_while_acting else {}),
            **({"interrupts_actions": True} if self.interrupts_actions else {}),
            **(
                {"cooldown_formula": self.cooldown_formula.to_data()}
                if self.cooldown_formula is not None
                else {}
            ),
            **({"display_name": self.display_name} if self.display_name else {}),
            **({"icon_id": self.icon_id} if self.icon_id else {}),
            **({"requires_items": dict(self.requires_items)} if self.requires_items else {}),
            **({"item_costs": dict(self.item_costs)} if self.item_costs else {}),
            **({"follow_tags": dict(self.follow_tags)} if self.follow_tags else {}),
            **({"forms": [copy.deepcopy(f) for f in self.forms]} if self.forms else {}),
            **({"currency_costs": dict(self.currency_costs)} if self.currency_costs else {}),
            **({"gauge_costs": dict(self.gauge_costs)} if self.gauge_costs else {}),
            **({"requires_pet": self.requires_pet} if self.requires_pet else {}),
            **({"menu_category": self.menu_category} if self.menu_category else {}),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "ability_id",
            "targeting",
            "costs",
            "conditions",
            "effects",
            "tags",
        }
        if set(data) - set(cls.OPTIONAL_DATA) != expected:
            raise ValueError("invalid ability definition")
        if data["schema"] != "asteria.ability_definition" or data["version"] != 1:
            raise ValueError("unsupported ability definition")
        return cls(
            data["ability_id"],
            targeting=TargetingRule.from_data(data["targeting"]),
            costs=[AbilityCost.from_data(x) for x in data["costs"]],
            conditions=deserialize_condition(data["conditions"]),
            effects=[AbilityEffect.from_data(x) for x in data["effects"]],
            tags=data["tags"],
            cooldown_turns=data.get("cooldown_turns", 0),
            battle_costs=data.get("battle_costs"),
            hits=data.get("hits", ()),
            battle_resource_gains=data.get("battle_resource_gains", ()),
            commands=data.get("commands", ()),
            concoct_station=data.get("concoct_station", ""),
            apply_states=data.get("apply_states", ()),
            timeline_id=data.get("timeline_id", ""),
            cooldown_seconds=data.get("cooldown_seconds", 0.0),
            move_while_acting=data.get("move_while_acting", 0.0),
            interrupts_actions=data.get("interrupts_actions", False),
            cooldown_formula=(
                ValueFormula.from_data(data["cooldown_formula"])
                if data.get("cooldown_formula") is not None
                else None
            ),
            display_name=data.get("display_name", ""),
            icon_id=data.get("icon_id", ""),
            requires_items=data.get("requires_items"),
            item_costs=data.get("item_costs"),
            follow_tags=data.get("follow_tags"),
            forms=data.get("forms", ()),
            currency_costs=data.get("currency_costs"),
            gauge_costs=data.get("gauge_costs"),
            requires_pet=data.get("requires_pet", ""),
            menu_category=data.get("menu_category", ""),
        )


class AbilityRegistry:
    def __init__(self, definitions=()):
        self._definitions = {}
        for definition in definitions:
            self.register(definition)

    def register(self, definition):
        if not isinstance(definition, AbilityDefinition):
            raise TypeError("definition must be AbilityDefinition")
        if definition.ability_id in self._definitions:
            raise ValueError(f"duplicate ability: {definition.ability_id}")
        self._definitions[definition.ability_id] = definition
        return definition

    def get(self, ability_id):
        return self._definitions.get(str(ability_id))

    def require(self, ability_id):
        try:
            return self._definitions[str(ability_id)]
        except KeyError as exc:
            raise KeyError(f"unknown ability: {ability_id}") from exc

    def ids(self):
        return tuple(sorted(self._definitions))


@dataclass(frozen=True, slots=True)
class AbilityExecutionResult:
    ability_id: str
    executed: bool
    errors: tuple[str, ...] = ()
    spent_resources: tuple[tuple[str, float], ...] = ()
    effect_results: tuple[tuple[str, EffectApplicationResult], ...] = ()


def _effective_stats(subject: GameplaySubject):
    """The subject's stats with its active states' modifiers applied (attack up, defence
    down...)."""
    states = subject.states
    modifiers = states.modifiers() if states is not None else None
    if not modifiers or not modifiers.modifiers():
        return subject.stats
    values = {
        name: modifiers.evaluate(name, subject.stats.get(name), tags=subject.tags)
        for name in subject.stats.names()
    }
    return StatBlock(values)


def _formula_context(source: GameplaySubject, target: GameplaySubject | None):
    if target is None:
        target = source
    return FormulaContext(
        _effective_stats(source),
        source.resources,
        source.tags,
        _effective_stats(target),
        target.resources,
        target.tags,
    )


def _clone_subject(subject: GameplaySubject):
    return GameplaySubject(
        StatBlock.from_data(subject.stats.to_data()),
        ResourcePool.from_data(subject.resources.to_data()),
        TagSet.from_data(subject.tags.to_data()),
        subject.states,
    )


def _commit_subject(staged: GameplaySubject, actual: GameplaySubject):
    actual.stats._values = dict(staged.stats._values)
    actual.resources._values = {
        key: type(value).from_data(value.to_data())
        for key, value in staged.resources._values.items()
    }
    actual.tags._tags = set(staged.tags._tags)


class AbilityRuntime:
    """Turn/realtime-neutral ability validation and atomic execution.

    Spatial queries, animation timing, cooldown scheduling and input are
    intentionally outside this foundation.
    """

    def __init__(self, registry: AbilityRegistry):
        if not isinstance(registry, AbilityRegistry):
            raise TypeError("registry must be AbilityRegistry")
        self.registry = registry

    def execute(
        self,
        ability_id,
        source: AbilityTarget,
        targets=(),
        *,
        prepaid_costs=None,
        value_transform=None,
        waive_costs=False,
        skip_targeting=False,
    ):
        """Validate, pay costs and apply effects atomically.

        ``skip_targeting`` accepts targets the ability's own rule would refuse (a state forced
        them).
        ``waive_costs`` runs the ability without charging its costs (the later hits of a
        multi-hit action, whose cost was paid with the first).

        ``value_transform(target_id, operation, value)`` (optional) adjusts each
        operation value an effect applies to a selected target. It returns the
        value for the target, or ``(target_value, source_value)`` to route part
        of it back to the source as a delta of the same resource (reflection).
        """
        definition = self.registry.require(ability_id)
        targets = tuple(targets)
        if any(not isinstance(x, AbilityTarget) for x in targets):
            raise TypeError("targets must be AbilityTarget values")

        errors = [] if skip_targeting else list(definition.targeting.validate(source, targets))
        condition_target = targets[0].subject if targets else None
        if not definition.conditions.evaluate(
            GameplayConditionContext(source.subject, condition_target)
        ):
            errors.append("conditions_failed")

        evaluated_costs = []
        formula_context = _formula_context(source.subject, condition_target)
        for cost in () if waive_costs else definition.costs:
            try:
                amount = float(cost.amount.evaluate(formula_context))
            except (KeyError, ValueError) as exc:
                errors.append(f"cost_formula_failed:{cost.resource}:{exc}")
                continue
            if not isfinite(amount) or amount < 0.0:
                errors.append(f"invalid_cost:{cost.resource}")
                continue
            if not source.subject.resources.contains(cost.resource):
                errors.append(f"missing_resource:{cost.resource}")
                continue
            available = (
                source.subject.resources.current(cost.resource)
                - source.subject.resources.get(cost.resource).minimum
            )
            if prepaid_costs is None and available < amount:
                errors.append(f"insufficient_resource:{cost.resource}")
            evaluated_costs.append((cost.resource, amount))

        if errors:
            return AbilityExecutionResult(definition.ability_id, False, tuple(errors))

        # One staged subject per stable target ID so cost/effects are atomic.
        actual_by_id = {source.target_id: source.subject}
        for target in targets:
            actual_by_id[target.target_id] = target.subject
        staged_by_id = {
            target_id: _clone_subject(subject) for target_id, subject in actual_by_id.items()
        }

        staged_source = staged_by_id[source.target_id]
        if prepaid_costs is None:
            for resource, amount in evaluated_costs:
                if not staged_source.resources.spend(resource, amount):
                    return AbilityExecutionResult(
                        definition.ability_id,
                        False,
                        (f"insufficient_resource:{resource}",),
                    )
        else:
            normalized_prepaid = tuple((str(r), float(a)) for r, a in prepaid_costs)
            if normalized_prepaid != tuple(evaluated_costs):
                return AbilityExecutionResult(
                    definition.ability_id, False, ("prepaid_cost_mismatch",)
                )

        effect_results = []
        for ability_effect in definition.effects:
            if ability_effect.mode == AbilityTargetMode.SELF:
                result = apply_effect(
                    ability_effect.effect,
                    staged_source.stats,
                    staged_source.resources,
                    staged_source.tags,
                    formula_context=_formula_context(staged_source, staged_source),
                )
                effect_results.append((source.target_id, result))
            else:
                for target in targets:
                    staged_target = staged_by_id[target.target_id]
                    reflected = []
                    transform = None
                    if value_transform is not None:

                        def transform(
                            operation, value, _target_id=target.target_id, _reflected=reflected
                        ):
                            routed = value_transform(_target_id, operation, value)
                            if isinstance(routed, tuple):
                                routed, back = routed
                                if back:
                                    _reflected.append((operation.target, float(back)))
                            return routed

                    result = apply_effect(
                        ability_effect.effect,
                        staged_target.stats,
                        staged_target.resources,
                        staged_target.tags,
                        formula_context=_formula_context(staged_source, staged_target),
                        value_transform=transform,
                    )
                    effect_results.append((target.target_id, result))
                    for resource, amount in reflected:
                        if staged_source.resources.contains(resource):
                            staged_source.resources.change(resource, amount)
        for target_id in sorted(staged_by_id):
            _commit_subject(staged_by_id[target_id], actual_by_id[target_id])

        return AbilityExecutionResult(
            definition.ability_id,
            True,
            spent_resources=tuple(evaluated_costs),
            effect_results=tuple(effect_results),
        )
