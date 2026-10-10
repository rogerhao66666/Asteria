from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import (
    AbilityDefinition,
    AbilityEffect,
    AbilityRegistry,
    AbilityRuntime,
    AbilityTargetMode,
    Effect,
    EffectOperation,
    EffectOperationKind,
    GameplaySubject,
    ResourcePool,
    StateRegistry,
    StateRuntime,
    StatBlock,
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    BattleAction,
    BattleFormationRuntime,
    BattlePlacement,
    BattleRuntime,
    FormationDefinition,
    FormationSlotDefinition,
    Party,
    PartyMember,
)


@dataclass(slots=True)
class PlayablePartyScenario:
    battle: BattleRuntime
    active_ids: tuple[str, ...]
    reserve_ids: tuple[str, ...]
    enemy_id: str


def _subject(*, vitality, power, speed, tag):
    stats = StatBlock({"power": power, "speed": speed})
    resources = ResourcePool()
    resources.define("vitality", vitality, current=vitality)
    tags = TagSet((tag,))
    states = StateRuntime(StateRegistry(()), stats, resources, tags)
    return GameplaySubject(stats, resources, tags, states)


def _ability(ability_id, delta):
    return AbilityDefinition(
        ability_id,
        targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
        effects=(
            AbilityEffect(
                AbilityTargetMode.SELECTED,
                Effect(
                    f"{ability_id}.effect",
                    (EffectOperation(EffectOperationKind.RESOURCE_DELTA, "vitality", float(delta)),),
                ),
            ),
        ),
    )


def build_playable_party_scenario():
    registry = AbilityRegistry()
    members = []
    # 12 project-defined party members; only four start fielded.
    for i in range(12):
        ability_id = f"member_{i:02d}_action"
        registry.register(_ability(ability_id, -(10 + i)))
        members.append(
            PartyMember(
                f"party_{i:02d}",
                "side.alpha",
                _subject(
                    vitality=180 + i * 5,
                    power=18 + i,
                    speed=20 - i,
                    tag=f"archetype.{i:02d}",
                ),
                ability_ids=(ability_id,),
                initiative=20 - i,
            )
        )
    registry.register(_ability("enemy_action", -17))
    enemy = PartyMember(
        "reference_enemy",
        "side.omega",
        _subject(vitality=500, power=30, speed=7, tag="combatant.enemy"),
        ability_ids=("enemy_action",),
        initiative=7,
    )

    slots = tuple(
        FormationSlotDefinition(
            f"slot_{i}",
            x=float(i),
            y=float(i % 2),
            tags=(f"lane.{i}",),
        )
        for i in range(4)
    )
    formation = BattleFormationRuntime(
        FormationDefinition("reference_party_formation", slots),
        tuple(BattlePlacement(f"party_{i:02d}", f"slot_{i}") for i in range(4)),
    )

    battle = BattleRuntime(
        (
            Party("side.alpha", tuple(members)),
            Party("side.omega", (enemy,)),
        ),
        AbilityRuntime(registry),
        formations={"side.alpha": formation},
        rng_seed=124,
    )

    # Reserve is generic inactive participation, not a separate battle subsystem.
    for member in members[4:]:
        battle.incapacitate(
            member.member_id,
            state_id="reserve",
            targetable=False,
            reason="reference.reserve",
        )

    return PlayablePartyScenario(
        battle,
        tuple(m.member_id for m in members[:4]),
        tuple(m.member_id for m in members[4:]),
        enemy.member_id,
    )


class PlayableBattlePartyHarness:
    def __init__(self, scenario=None):
        self.scenario = scenario or build_playable_party_scenario()

    @property
    def battle(self):
        return self.scenario.battle

    def active_ids(self):
        return tuple(
            sorted(
                state.member_id
                for state in self.battle.combatants.states()
                if state.present and state.active and self.battle.member(state.member_id).side == "side.alpha"
            )
        )

    def reserve_ids(self):
        return tuple(
            sorted(
                state.member_id
                for state in self.battle.combatants.states()
                if state.present and not state.active and self.battle.member(state.member_id).side == "side.alpha"
            )
        )

    def formation_snapshot(self):
        runtime = self.battle.formations["side.alpha"]
        return tuple((p.member_id, p.slot_id) for p in runtime.placements())

    def swap(self, outgoing_id, incoming_id):
        if outgoing_id == incoming_id:
            raise ValueError("swap requires distinct members")
        if outgoing_id not in self.active_ids():
            raise ValueError("outgoing member must be active")
        if incoming_id not in self.reserve_ids():
            raise ValueError("incoming member must be reserve")

        formation = self.battle.formations["side.alpha"]
        slot_id = formation.slot_id_for(outgoing_id)
        if slot_id is None:
            raise ValueError("outgoing member has no formation slot")

        formation.remove(outgoing_id)
        self.battle.incapacitate(
            outgoing_id,
            state_id="reserve",
            targetable=False,
            reason="reference.swap.out",
        )
        self.battle.revive(
            incoming_id,
            state_id="active",
            targetable=True,
            reason="reference.swap.in",
        )
        formation.place(incoming_id, slot_id)
        return (outgoing_id, incoming_id, slot_id)

    def execute_member_action(self, member_id):
        ability_id = self.battle.member(member_id).ability_ids[0]
        return self.battle.execute(
            BattleAction(
                member_id,
                ability_id,
                (self.scenario.enemy_id,),
            )
        )

    def snapshot(self):
        return self.battle.snapshot()
