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
    StatBlock,
    StateRegistry,
    StateRuntime,
    TagSet,
    TargetingRule,
)
from asteria.rpg import BattleAction, BattleRuntime, Party, PartyMember


@dataclass(slots=True)
class PlayableSummonScenario:
    battle: BattleRuntime
    player_id: str
    boss_id: str


def _subject(*, vitality, power, speed, tags=()):
    stats = StatBlock({"power": power, "speed": speed})
    resources = ResourcePool()
    resources.define("vitality", vitality, current=vitality)
    tagset = TagSet(tags)
    states = StateRuntime(StateRegistry(()), stats, resources, tagset)
    return GameplaySubject(stats, resources, tagset, states)


def _ability(ability_id, delta, *tags):
    return AbilityDefinition(
        ability_id,
        tags=tags,
        targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
        effects=(
            AbilityEffect(
                AbilityTargetMode.SELECTED,
                Effect(
                    f"{ability_id}.effect",
                    (
                        EffectOperation(
                            EffectOperationKind.RESOURCE_DELTA,
                            "vitality",
                            float(delta),
                        ),
                    ),
                ),
            ),
        ),
    )


def build_playable_summon_scenario():
    registry = AbilityRegistry()
    for definition in (
        _ability("hero_strike", -18, "player.action"),
        _ability("spirit_bolt", -16, "summon.action"),
        _ability("boss_crush", -24, "boss.action"),
        _ability("add_bite", -10, "add.action"),
    ):
        registry.register(definition)

    hero = PartyMember(
        "validation_hero",
        "side.alpha",
        _subject(vitality=220, power=24, speed=12, tags=("combatant.player",)),
        ability_ids=("hero_strike",),
        initiative=12,
    )
    boss = PartyMember(
        "reference_boss",
        "side.omega",
        _subject(vitality=520, power=35, speed=8, tags=("combatant.boss",)),
        ability_ids=("boss_crush",),
        initiative=8,
    )
    battle = BattleRuntime(
        (
            Party("side.alpha", (hero,)),
            Party("side.omega", (boss,)),
        ),
        AbilityRuntime(registry),
        rng_seed=123,
    )
    return PlayableSummonScenario(battle, hero.member_id, boss.member_id)


class PlayableBattleSummonHarness:
    def __init__(self, scenario=None):
        self.scenario = scenario or build_playable_summon_scenario()

    @property
    def battle(self):
        return self.scenario.battle

    def summon_player_spirit(self, *, join_current_round=True):
        member = PartyMember(
            "spirit_echo",
            "side.alpha",
            _subject(vitality=90, power=20, speed=14, tags=("combatant.summon",)),
            ability_ids=("spirit_bolt",),
            initiative=14,
        )
        return self.battle.summon(
            member,
            owner_id=self.scenario.player_id,
            join_current_round=join_current_round,
        )

    def summon_boss_add(self, *, member_id="ember_add", join_current_round=True):
        member = PartyMember(
            member_id,
            "side.omega",
            _subject(vitality=75, power=14, speed=11, tags=("combatant.add",)),
            ability_ids=("add_bite",),
            initiative=11,
        )
        return self.battle.summon(
            member,
            owner_id=self.scenario.boss_id,
            join_current_round=join_current_round,
        )

    def execute(self, actor_id, ability_id, target_id):
        return self.battle.execute(BattleAction(actor_id, ability_id, (target_id,)))

    def remove(self, member_id, *, reason="reference.temporary.exit"):
        return self.battle.remove_combatant(member_id, reason=reason)

    def lifecycle(self, member_id):
        return self.battle.combatants.state(member_id)

    def active_member_ids(self):
        return tuple(
            sorted(state.member_id for state in self.battle.combatants.states() if state.present and state.active)
        )

    def snapshot(self):
        return self.battle.snapshot()
