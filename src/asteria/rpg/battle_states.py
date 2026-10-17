from __future__ import annotations

import random
from dataclasses import dataclass
from math import isfinite

from asteria.core.lifecycle import emit_hook
from asteria.gameplay import GameplaySubject, normalize_tag


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _number(value, label):
    value = float(value)
    if not isfinite(value):
        raise ValueError(f"{label} must be finite")
    return value


def _tags(values):
    return tuple(sorted({normalize_tag(x) for x in values}))


def _coeffs(values):
    result = {}
    for key, value in dict(values or {}).items():
        key = _id(key, "stat name")
        result[key] = _number(value, "stat coefficient")
    return result


TARGET_OVERRIDES = ("", "random_any", "random_opponent", "random_ally")


@dataclass(frozen=True, slots=True)
class BattleStatePolicy:
    """Battle-specific application/timing policy for a generic gameplay State.

    State content remains owned by GameplayLibrary/StateDefinition. This policy
    only describes battle admission, action restrictions and lifecycle ticking.
    No poison/stun/silence names are hardcoded by the engine.
    """

    state_id: str
    base_chance: float = 1.0
    source_stat_terms: dict[str, float] = None
    target_stat_terms: dict[str, float] = None
    minimum_chance: float = 0.0
    maximum_chance: float = 1.0
    immune_target_tags: tuple[str, ...] = ()
    duration_multiplier: float = 1.0
    duration_target_stat_terms: dict[str, float] = None
    prevent_action: bool = False
    blocked_ability_tags: tuple[str, ...] = ()
    tick_trigger: str | None = None
    tick_amount: float = 1.0
    remove_triggers: tuple[str, ...] = ()
    # Opt-in: harmful periodic deltas of this state are resolved by the battle's
    # interaction rules with these tags as action tags (e.g. "element.fire").
    # Empty (default): damage-over-time ignores interaction multipliers.
    interaction_tags: tuple[str, ...] = ()
    # only abilities carrying one of these tags may be used (berserk: attacks only); empty = all
    allowed_ability_tags: tuple[str, ...] = ()
    # who the afflicted member's actions hit, whatever was chosen: "" (as aimed),
    # "random_any" (confusion), "random_opponent", "random_ally" (charm)
    target_override: str = ""
    # shown in the editor even when empty (left out of the saved data while empty)
    OPTIONAL_DATA = {"interaction_tags": [], "allowed_ability_tags": [], "target_override": ""}

    SCHEMA = "asteria.rpg.battle_state_policy"
    VERSION = 1

    def __init__(
        self,
        state_id,
        *,
        base_chance=1.0,
        source_stat_terms=None,
        target_stat_terms=None,
        minimum_chance=0.0,
        maximum_chance=1.0,
        immune_target_tags=(),
        duration_multiplier=1.0,
        duration_target_stat_terms=None,
        prevent_action=False,
        blocked_ability_tags=(),
        tick_trigger=None,
        tick_amount=1.0,
        remove_triggers=(),
        interaction_tags=(),
        allowed_ability_tags=(),
        target_override="",
    ):
        if target_override not in TARGET_OVERRIDES:
            raise ValueError(f"target_override must be one of {TARGET_OVERRIDES}")
        minimum_chance = _number(minimum_chance, "minimum_chance")
        maximum_chance = _number(maximum_chance, "maximum_chance")
        if not 0 <= minimum_chance <= maximum_chance <= 1:
            raise ValueError("chance bounds must satisfy 0 <= min <= max <= 1")
        duration_multiplier = _number(duration_multiplier, "duration_multiplier")
        tick_amount = _number(tick_amount, "tick_amount")
        if duration_multiplier < 0:
            raise ValueError("duration_multiplier must be >= 0")
        if tick_amount <= 0:
            raise ValueError("tick_amount must be > 0")
        if tick_trigger is not None:
            tick_trigger = _id(tick_trigger, "tick_trigger")
        remove_triggers = tuple(sorted({_id(x, "remove_trigger") for x in remove_triggers}))
        object.__setattr__(self, "state_id", _id(state_id, "state_id"))
        object.__setattr__(self, "base_chance", _number(base_chance, "base_chance"))
        object.__setattr__(self, "source_stat_terms", _coeffs(source_stat_terms))
        object.__setattr__(self, "target_stat_terms", _coeffs(target_stat_terms))
        object.__setattr__(self, "minimum_chance", minimum_chance)
        object.__setattr__(self, "maximum_chance", maximum_chance)
        object.__setattr__(self, "immune_target_tags", _tags(immune_target_tags))
        object.__setattr__(self, "duration_multiplier", duration_multiplier)
        object.__setattr__(self, "duration_target_stat_terms", _coeffs(duration_target_stat_terms))
        object.__setattr__(self, "prevent_action", bool(prevent_action))
        object.__setattr__(self, "blocked_ability_tags", _tags(blocked_ability_tags))
        object.__setattr__(self, "tick_trigger", tick_trigger)
        object.__setattr__(self, "tick_amount", tick_amount)
        object.__setattr__(self, "remove_triggers", remove_triggers)
        object.__setattr__(self, "interaction_tags", _tags(interaction_tags))
        object.__setattr__(self, "allowed_ability_tags", _tags(allowed_ability_tags))
        object.__setattr__(self, "target_override", target_override)

    def to_data(self):
        return {
            "schema": self.SCHEMA,
            "version": self.VERSION,
            "state_id": self.state_id,
            "base_chance": self.base_chance,
            "source_stat_terms": dict(self.source_stat_terms),
            "target_stat_terms": dict(self.target_stat_terms),
            "minimum_chance": self.minimum_chance,
            "maximum_chance": self.maximum_chance,
            "immune_target_tags": list(self.immune_target_tags),
            "duration_multiplier": self.duration_multiplier,
            "duration_target_stat_terms": dict(self.duration_target_stat_terms),
            "prevent_action": self.prevent_action,
            "blocked_ability_tags": list(self.blocked_ability_tags),
            "tick_trigger": self.tick_trigger,
            "tick_amount": self.tick_amount,
            "remove_triggers": list(self.remove_triggers),
            **({"interaction_tags": list(self.interaction_tags)} if self.interaction_tags else {}),
            **(
                {"allowed_ability_tags": list(self.allowed_ability_tags)}
                if self.allowed_ability_tags
                else {}
            ),
            **({"target_override": self.target_override} if self.target_override else {}),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle state policy")
        return cls(
            data["state_id"],
            base_chance=data.get("base_chance", 1),
            source_stat_terms=data.get("source_stat_terms", {}),
            target_stat_terms=data.get("target_stat_terms", {}),
            minimum_chance=data.get("minimum_chance", 0),
            maximum_chance=data.get("maximum_chance", 1),
            immune_target_tags=data.get("immune_target_tags", ()),
            duration_multiplier=data.get("duration_multiplier", 1),
            duration_target_stat_terms=data.get("duration_target_stat_terms", {}),
            prevent_action=data.get("prevent_action", False),
            blocked_ability_tags=data.get("blocked_ability_tags", ()),
            tick_trigger=data.get("tick_trigger"),
            tick_amount=data.get("tick_amount", 1),
            remove_triggers=data.get("remove_triggers", ()),
            interaction_tags=data.get("interaction_tags", ()),
            allowed_ability_tags=data.get("allowed_ability_tags", ()),
            target_override=data.get("target_override", ""),
        )


@dataclass(frozen=True, slots=True)
class BattleStateApplicationResult:
    state_id: str
    source_id: str
    target_id: str
    applied: bool
    immune: bool
    chance: float
    roll: float | None
    duration: float | None
    reason: str


@dataclass(frozen=True, slots=True)
class AbilityAvailability:
    allowed: bool
    blocking_states: tuple[str, ...] = ()
    reason: str = ""


class BattleStateRuntime:
    def __init__(self, policies=(), *, hooks=None):
        self.policies = {}
        for policy in policies:
            if not isinstance(policy, BattleStatePolicy):
                raise TypeError("policies must contain BattleStatePolicy values")
            if policy.state_id in self.policies:
                raise ValueError(f"duplicate battle state policy: {policy.state_id}")
            self.policies[policy.state_id] = policy
        self.hooks = hooks
        # Set by BattleRuntime: (member, active_state, policy) -> value_transform or None.
        self.periodic_transform = None

    @staticmethod
    def _stat(subject, name):
        try:
            return subject.stats.get(name)
        except KeyError:
            return 0.0

    def _chance(self, policy, source, target):
        value = policy.base_chance
        for name, coefficient in policy.source_stat_terms.items():
            value += self._stat(source, name) * coefficient
        for name, coefficient in policy.target_stat_terms.items():
            value += self._stat(target, name) * coefficient
        return min(policy.maximum_chance, max(policy.minimum_chance, value))

    def _duration(self, policy, target):
        definition = target.states.registry.require(policy.state_id)
        multiplier = policy.duration_multiplier
        for name, coefficient in policy.duration_target_stat_terms.items():
            multiplier += self._stat(target, name) * coefficient
        return max(0.0, definition.duration * max(0.0, multiplier))

    def apply(self, state_id, source_id, source, target_id, target, *, rng=None):
        state_id = str(state_id)
        if not isinstance(source, GameplaySubject) or not isinstance(target, GameplaySubject):
            raise TypeError("source and target must be GameplaySubject")
        if target.states is None:
            raise ValueError("target has no StateRuntime")
        policy = self.policies.get(state_id, BattleStatePolicy(state_id))
        if any(target.tags.contains(tag) for tag in policy.immune_target_tags):
            result = BattleStateApplicationResult(
                state_id, str(source_id), str(target_id), False, True, 0.0, None, None, "immune"
            )
            emit_hook(
                self.hooks,
                "rpg.battle.state_resisted",
                source=str(target_id),
                data={"result": result},
            )
            return result
        chance = self._chance(policy, source, target)
        roller = rng.random if rng is not None else random.random
        roll = float(roller())
        if roll >= chance:
            result = BattleStateApplicationResult(
                state_id,
                str(source_id),
                str(target_id),
                False,
                False,
                chance,
                roll,
                None,
                "resisted",
            )
            emit_hook(
                self.hooks,
                "rpg.battle.state_resisted",
                source=str(target_id),
                data={"result": result},
            )
            return result
        duration = self._duration(policy, target)
        target.states.apply(state_id, duration=duration, source_id=str(source_id))
        result = BattleStateApplicationResult(
            state_id,
            str(source_id),
            str(target_id),
            True,
            False,
            chance,
            roll,
            duration,
            "applied",
        )
        emit_hook(
            self.hooks, "rpg.battle.state_applied", source=str(target_id), data={"result": result}
        )
        return result

    def ability_availability(self, subject, ability_tags=()):
        if subject.states is None:
            return AbilityAvailability(True)
        ability_tags = set(_tags(ability_tags))
        blocked = []
        for active in subject.states.active_states():
            policy = self.policies.get(active.state_id)
            if policy is None:
                continue
            outside = bool(policy.allowed_ability_tags) and not ability_tags.intersection(
                policy.allowed_ability_tags
            )
            if (
                policy.prevent_action
                or outside
                or ability_tags.intersection(policy.blocked_ability_tags)
            ):
                blocked.append(active.state_id)
        blocked = tuple(sorted(blocked))
        return AbilityAvailability(not blocked, blocked, "blocked_by_state" if blocked else "")

    def apply_trigger(self, trigger, members):
        trigger = str(trigger)
        expired = []
        for member in sorted(members, key=lambda x: x.member_id):
            states = member.subject.states
            if states is None:
                continue
            for active in list(states.active_states()):
                policy = self.policies.get(active.state_id)
                if policy is None:
                    continue
                if trigger in policy.remove_triggers:
                    states.remove(active.state_id, run_remove_effects=True)
                    emit_hook(
                        self.hooks,
                        "rpg.battle.state_removed",
                        source=member.member_id,
                        data={"state_id": active.state_id, "trigger": trigger},
                    )
                    continue
                if policy.tick_trigger != trigger:
                    continue
                transform = None
                if self.periodic_transform is not None and policy.interaction_tags:
                    transform = self.periodic_transform(member, active, policy)
                if states.advance(active.state_id, policy.tick_amount, value_transform=transform):
                    expired.append((member.member_id, active.state_id))
                    emit_hook(
                        self.hooks,
                        "rpg.battle.state_expired",
                        source=member.member_id,
                        data={"state_id": active.state_id, "trigger": trigger},
                    )
        return tuple(expired)
