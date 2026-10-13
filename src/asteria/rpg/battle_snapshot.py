from __future__ import annotations

import copy
from dataclasses import dataclass

from asteria.gameplay import (
    GameplaySubject,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    TagSet,
)


def _jsonable_state(value):
    if isinstance(value, tuple):
        return {"__tuple__": [_jsonable_state(x) for x in value]}
    if isinstance(value, list):
        return [_jsonable_state(x) for x in value]
    if isinstance(value, dict):
        return {str(k): _jsonable_state(v) for k, v in value.items()}
    return value


def _restore_state(value):
    if isinstance(value, dict) and set(value) == {"__tuple__"}:
        return tuple(_restore_state(x) for x in value["__tuple__"])
    if isinstance(value, list):
        return [_restore_state(x) for x in value]
    if isinstance(value, dict):
        return {k: _restore_state(v) for k, v in value.items()}
    return value


@dataclass(frozen=True, slots=True)
class BattleSnapshot:
    """Serializable checkpoint for deterministic BattleRuntime continuation.

    Project definitions/registries are deliberately not duplicated here.  A
    snapshot captures mutable battle state and is restored into a compatible
    BattleRuntime built from the same authored content.
    """

    data: dict
    SCHEMA = "asteria.rpg.battle_snapshot"
    VERSION = 1

    def to_data(self):
        return copy.deepcopy(self.data)

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != cls.SCHEMA or data.get("version") != cls.VERSION:
            raise ValueError("unsupported battle snapshot")
        return cls(copy.deepcopy(data))


def _pack_member(member):
    states = member.subject.states
    registry = []
    state_snapshot = None
    if states is not None:
        registry = [states.registry.require(x).to_data() for x in states.registry.ids()]
        state_snapshot = states.snapshot()
    return {
        "member_id": member.member_id,
        "side": member.side,
        "ability_ids": list(member.ability_ids),
        "initiative": member.initiative,
        "stats": member.subject.stats.to_data(),
        "resources": member.subject.resources.to_data(),
        "tags": member.subject.tags.to_data(),
        "state_registry": registry,
        "states": state_snapshot,
    }


def _unpack_member(raw):
    from .battle import PartyMember

    stats = StatBlock.from_data(raw["stats"])
    resources = ResourcePool.from_data(raw["resources"])
    tags = TagSet.from_data(raw["tags"])
    states = None
    if raw.get("states") is not None:
        registry = StateRegistry(
            StateDefinition.from_data(x) for x in raw.get("state_registry", ())
        )
        states = StateRuntime(registry, stats, resources, tags)
        states.restore(raw["states"])
    subject = GameplaySubject(stats, resources, tags, states)
    return PartyMember(
        raw["member_id"],
        raw["side"],
        subject,
        ability_ids=raw.get("ability_ids", ()),
        initiative=raw.get("initiative", 0.0),
    )


def capture_battle_snapshot(battle) -> BattleSnapshot:
    members = {
        member_id: _pack_member(battle.members[member_id]) for member_id in sorted(battle.members)
    }
    formations = {side: runtime.to_data() for side, runtime in sorted(battle.formations.items())}
    data = {
        "schema": BattleSnapshot.SCHEMA,
        "version": BattleSnapshot.VERSION,
        "members": members,
        "combatants": battle.combatants.to_data(),
        "turn_runtime": battle.turn_queue.to_data(),
        "turn_kind": "scheduler" if battle.scheduler is not None else "queue",
        "battle_resources": battle.battle_resources.to_data(),
        "action_timing": battle.action_timing.to_data(),
        "enemy_ai": battle.enemy_ai.to_data(),
        "formations": formations,
        "escaped_sides": sorted(battle._escaped_sides),
        "objective_flags": dict(sorted(battle.objectives.flags.items())),
        "resources_finished": bool(battle._resources_finished),
        "rng_state": _jsonable_state(battle.rng.getstate()),
        "transactions": battle.transactions.to_data(),
        "transform_stacks": {
            member_id: [
                {"member": _pack_member(member), "prior_form_id": prior_form_id}
                for member, prior_form_id in stack
            ]
            for member_id, stack in sorted(battle._transform_stacks.items())
        },
    }
    return BattleSnapshot(data)


def restore_battle_snapshot(battle, snapshot):
    snapshot = (
        snapshot if isinstance(snapshot, BattleSnapshot) else BattleSnapshot.from_data(snapshot)
    )
    data = snapshot.data
    snapshot_ids = set(data["members"])
    current_ids = set(battle.members)
    # Restore dynamic topology (summons/removals) without replaying lifecycle hooks.
    for member_id in sorted(current_ids - snapshot_ids):
        member = battle.members.pop(member_id)
        battle.parties[member.side].members = [
            x for x in battle.parties[member.side].members if x.member_id != member_id
        ]
    for member_id in sorted(snapshot_ids):
        raw = data["members"][member_id]
        replacement = _unpack_member(raw)
        if replacement.side not in battle.parties:
            raise ValueError(f"battle snapshot unknown side: {replacement.side}")
        if member_id in battle.members:
            prior = battle.members[member_id]
            if prior.side != replacement.side:
                raise ValueError("battle snapshot member side mismatch")
            party = battle.parties[prior.side]
            party.members = [replacement if x.member_id == member_id else x for x in party.members]
        else:
            battle.parties[replacement.side].members.append(replacement)
        battle.members[member_id] = replacement
    battle.targeting.members = dict(battle.members)
    from .battle import TurnQueue
    from .battle_lifecycle import CombatantLifecycleRuntime
    from .battle_scheduler import BattleScheduler
    from .battle_timing import BattleActionTimingRuntime

    battle.combatants = CombatantLifecycleRuntime.from_data(data["combatants"], hooks=battle.hooks)
    battle.is_active = lambda member: (
        battle.combatants.is_active(member) and battle._base_is_active(member)
    )
    if data["turn_kind"] == "scheduler":
        battle.scheduler = BattleScheduler.from_data(data["turn_runtime"], battle.members.values())
        battle.turn_queue = battle.scheduler
    else:
        battle.scheduler = None
        battle.turn_queue = TurnQueue.from_data(data["turn_runtime"], battle.members.values())
    from .battle_resources import BattleResourceRuntime

    battle.battle_resources = BattleResourceRuntime(
        battle.battle_resources.definitions.values(), battle.members.values(), hooks=battle.hooks
    )
    battle.battle_resources.restore_from_data(data["battle_resources"])
    battle.action_timing = BattleActionTimingRuntime.from_data(data["action_timing"])
    battle.enemy_ai.restore_data(data["enemy_ai"])
    for side, raw in data.get("formations", {}).items():
        if side not in battle.formations:
            raise ValueError(f"snapshot formation missing in runtime: {side}")
        battle.formations[side].restore_from_data(raw)
    battle._escaped_sides = set(data.get("escaped_sides", ()))
    battle.objectives.flags = dict(data.get("objective_flags", {}))
    battle._resources_finished = bool(data.get("resources_finished", False))
    battle.rng.setstate(_restore_state(data["rng_state"]))
    battle.transactions.restore_from_data(data["transactions"])
    battle._transform_stacks = {
        member_id: [(_unpack_member(x["member"]), x.get("prior_form_id")) for x in stack]
        for member_id, stack in data.get("transform_stacks", {}).items()
    }
    return battle
