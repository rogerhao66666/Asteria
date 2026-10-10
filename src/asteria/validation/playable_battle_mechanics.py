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
    ModifierOperation,
    PeriodicEffect,
    ResourcePool,
    StatBlock,
    StateDefinition,
    StateRegistry,
    StateRuntime,
    StatModifier,
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    ActionSequenceDefinition,
    ActionSequenceStep,
    BattleAction,
    BattleResourceDefinition,
    BattleRuntime,
    BattleStatePolicy,
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
    InteractionRule,
    Party,
    PartyMember,
)

from .playable_rpg import PlayableRpgValidationHarness


@dataclass(slots=True)
class PlayableMechanicsScenario:
    battle: BattleRuntime
    player_id: str
    enemy_id: str


def _state_definitions():
    return (
        StateDefinition(
            "scorch",
            3,
            periodic=(
                PeriodicEffect(
                    1,
                    Effect(
                        "scorch.tick",
                        (
                            EffectOperation(
                                EffectOperationKind.RESOURCE_DELTA,
                                "vitality",
                                -5,
                            ),
                        ),
                    ),
                ),
            ),
            contributed_tags=("state.scorch",),
        ),
        StateDefinition(
            "focus_up",
            2,
            modifiers=(
                StatModifier(
                    "focus_up.power",
                    "power",
                    ModifierOperation.ADD,
                    4,
                ),
            ),
            contributed_tags=("state.focus_up",),
        ),
        StateDefinition(
            "staggered",
            1,
            contributed_tags=("state.staggered",),
        ),
    )


def _subject(stats, resources, tags=()):
    stats = StatBlock(stats)
    pool = ResourcePool()
    for resource_id, value in resources.items():
        pool.define(resource_id, value, current=value)
    tags = TagSet(tags)
    states = StateRuntime(StateRegistry(_state_definitions()), stats, pool, tags)
    return GameplaySubject(stats, pool, tags, states)


def build_playable_mechanics_scenario():
    """Reference battle for status timers, arbitrary gauges and interactions."""
    rpg = PlayableRpgValidationHarness()
    resolved = rpg.scenario.resolve()

    player = _subject(
        {
            "power": resolved.stats.get("power"),
            "focus": resolved.stats.get("focus"),
            "speed": resolved.stats.get("speed"),
        },
        {
            "vitality": resolved.resources.current("vitality"),
            "technique": resolved.resources.current("technique"),
            "momentum": resolved.resources.current("momentum"),
        },
        ("combatant.reference_player",),
    )
    enemy = _subject(
        {"power": 20, "guard": 12, "speed": 8},
        {"vitality": 360, "fury": 6},
        ("combatant.reference_enemy", "trait.flame_fragile"),
    )

    registry = AbilityRegistry()
    registry.register(
        AbilityDefinition(
            "flame_slash",
            tags=("element.flame", "attack.weapon"),
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
            effects=(
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        "flame_slash.damage",
                        (
                            EffectOperation(
                                EffectOperationKind.RESOURCE_DELTA,
                                "vitality",
                                -20,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    registry.register(
        AbilityDefinition(
            "restoration",
            tags=("support.restore",),
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=True),
            effects=(
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        "restoration.heal",
                        (
                            EffectOperation(
                                EffectOperationKind.RESOURCE_DELTA,
                                "vitality",
                                24,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )
    registry.register(
        AbilityDefinition(
            "enemy_claw",
            tags=("attack.physical",),
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
            effects=(
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect(
                        "enemy_claw.damage",
                        (
                            EffectOperation(
                                EffectOperationKind.RESOURCE_DELTA,
                                "vitality",
                                -15,
                            ),
                        ),
                    ),
                ),
            ),
        )
    )

    player_member = PartyMember(
        "validation_hero",
        "side.alpha",
        player,
        ability_ids=("flame_slash", "restoration"),
        initiative=12,
    )
    enemy_member = PartyMember(
        "reference_enemy",
        "side.omega",
        enemy,
        ability_ids=("enemy_claw",),
        initiative=8,
    )

    weakness = InteractionRule(
        "flame_fragility",
        source_tags_all=("element.flame",),
        target_tags_all=("trait.flame_fragile",),
        multiplier=1.5,
        outcome_tags=("interaction.exposed",),
        priority=10,
    )
    pressure = GaugeCompositionDefinition(
        "resolve_pressure",
        impacts=(
            GaugeImpactRule(
                "exposed_pressure",
                "resolve_guard",
                "battle.hit",
                delta=-2,
                required_outcome_tags_all=("interaction.exposed",),
            ),
        ),
        thresholds=(
            GaugeThresholdRule(
                "guard_empty",
                "resolve_guard",
                "at_or_below",
                0,
                state_id="staggered",
            ),
        ),
    )
    sequence = ActionSequenceDefinition(
        "double_flame",
        steps=(ActionSequenceStep("flame_slash", repeat=2),),
    )

    battle = BattleRuntime(
        (
            Party("side.alpha", (player_member,)),
            Party("side.omega", (enemy_member,)),
        ),
        AbilityRuntime(registry),
        resource_definitions=(
            BattleResourceDefinition(
                "resolve_guard",
                minimum=0,
                maximum=4,
                start_mode="maximum",
            ),
        ),
        interaction_rules=(weakness,),
        state_policies=(
            BattleStatePolicy("scorch", tick_trigger="rpg.battle.turn_ended"),
            BattleStatePolicy("focus_up", tick_trigger="rpg.battle.turn_ended"),
            BattleStatePolicy(
                "staggered",
                prevent_action=True,
                tick_trigger="rpg.battle.turn_ended",
            ),
        ),
        gauge_composition_definitions=(pressure,),
        action_sequence_definitions=(sequence,),
        rng_seed=121,
    )
    return PlayableMechanicsScenario(battle, player_member.member_id, enemy_member.member_id)


class PlayableBattleMechanicsHarness:
    def __init__(self, scenario=None):
        self.scenario = scenario or build_playable_mechanics_scenario()

    @property
    def battle(self):
        return self.scenario.battle

    def status_snapshot(self, member_id):
        state_runtime = self.battle.member(member_id).subject.states
        return tuple(
            (state.state_id, state.remaining, state.stacks, state.source_id) for state in state_runtime.active_states()
        )

    def apply_status(self, state_id, source_id=None, target_id=None):
        source_id = source_id or self.scenario.player_id
        target_id = target_id or self.scenario.enemy_id
        return self.battle.apply_state(state_id, source_id, target_id)

    def tick_turn_statuses(self, member_id):
        self.battle.battle_states.apply_trigger(
            "rpg.battle.turn_ended",
            (self.battle.member(member_id),),
        )
        return self.status_snapshot(member_id)

    def resolve_flame_interaction(self, base_value=20):
        action = BattleAction(
            self.scenario.player_id,
            "flame_slash",
            (self.scenario.enemy_id,),
        )
        return self.battle.resolve_interaction(
            action,
            self.scenario.enemy_id,
            base_value,
            rng=self.battle.rng,
        )

    def apply_resolve_pressure(self):
        outcome = self.resolve_flame_interaction()
        return self.battle.apply_gauge_impact(
            "resolve_pressure",
            self.scenario.player_id,
            self.scenario.enemy_id,
            trigger="battle.hit",
            outcome_tags=outcome.outcome_tags,
            value=outcome.value.resolved_value,
            rng=self.battle.rng,
        )

    def heal_player(self):
        return self.battle.execute(
            BattleAction(
                self.scenario.player_id,
                "restoration",
                (self.scenario.player_id,),
            )
        )

    def revive_player(self):
        self.battle.revive(self.scenario.player_id)
        return self.battle.combatants.state(self.scenario.player_id)

    def double_flame(self):
        return self.battle.execute_sequence(
            "double_flame",
            (self.scenario.player_id,),
            (self.scenario.enemy_id,),
        )
