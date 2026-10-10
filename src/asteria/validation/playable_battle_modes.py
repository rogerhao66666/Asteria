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
class PlayableModeScenario:
    battle: BattleRuntime
    actor_id: str
    target_id: str


def _subject(*, power, speed, vitality, momentum, tags=()):
    stats = StatBlock({"power": power, "speed": speed})
    resources = ResourcePool()
    resources.define("vitality", vitality, current=vitality)
    resources.define("momentum", momentum, current=momentum)
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


def build_playable_mode_scenario():
    registry = AbilityRegistry()
    for definition in (
        _ability("steady_strike", -14, "mode.normal"),
        _ability("guard_counter", -18, "mode.guard"),
        _ability("overdrive_arc", -34, "mode.overdrive"),
        _ability("enemy_hit", -11, "enemy.action"),
    ):
        registry.register(definition)

    normal = PartyMember(
        "validation_hero",
        "side.alpha",
        _subject(
            power=24,
            speed=12,
            vitality=240,
            momentum=2,
            tags=("form.normal",),
        ),
        ability_ids=("steady_strike",),
        initiative=12,
    )
    target = PartyMember(
        "reference_enemy",
        "side.omega",
        _subject(
            power=18,
            speed=9,
            vitality=300,
            momentum=0,
            tags=("combatant.enemy",),
        ),
        ability_ids=("enemy_hit",),
        initiative=9,
    )
    battle = BattleRuntime(
        (
            Party("side.alpha", (normal,)),
            Party("side.omega", (target,)),
        ),
        AbilityRuntime(registry),
        rng_seed=122,
    )
    return PlayableModeScenario(battle, normal.member_id, target.member_id)


class PlayableBattleModeHarness:
    """Reference-project mode composition over canonical BattleRuntime.transform.

    A stance and a dramatic transformation are intentionally represented by the
    same generic replacement/form stack. The engine owns no GuardStanceSystem or
    OverdriveSystem; projects author the replacement build and presentation.
    """

    def __init__(self, scenario=None):
        self.scenario = scenario or build_playable_mode_scenario()

    @property
    def battle(self):
        return self.scenario.battle

    @property
    def actor(self):
        return self.battle.member(self.scenario.actor_id)

    def action_surface(self):
        """Current relevant battle actions only; useful for adaptive UI."""
        return tuple(self.actor.ability_ids)

    def current_form(self):
        return self.battle.combatants.state(self.scenario.actor_id).form_id

    def enter_guard_stance(self):
        current = self.actor
        replacement = PartyMember(
            current.member_id,
            current.side,
            _subject(
                power=20,
                speed=10,
                vitality=current.subject.resources.current("vitality"),
                momentum=current.subject.resources.current("momentum"),
                tags=("form.guard", "mode.defensive"),
            ),
            ability_ids=("guard_counter",),
            initiative=10,
        )
        return self.battle.transform(
            current.member_id,
            replacement,
            form_id="guard_stance",
            reason="reference.mode.guard",
        )

    def enter_overdrive(self):
        current = self.actor
        replacement = PartyMember(
            current.member_id,
            current.side,
            _subject(
                power=38,
                speed=18,
                vitality=current.subject.resources.current("vitality"),
                momentum=current.subject.resources.current("momentum") + 3,
                tags=("form.overdrive", "mode.aggressive"),
            ),
            ability_ids=("overdrive_arc",),
            initiative=18,
        )
        return self.battle.transform(
            current.member_id,
            replacement,
            form_id="overdrive",
            reason="reference.mode.overdrive",
        )

    def revert_mode(self):
        return self.battle.revert_transform(
            self.scenario.actor_id,
            reason="reference.mode.revert",
        )

    def execute_current_action(self, ability_id=None):
        ability_id = ability_id or self.action_surface()[0]
        return self.battle.execute(
            BattleAction(
                self.scenario.actor_id,
                ability_id,
                (self.scenario.target_id,),
            )
        )

    def snapshot(self):
        return self.battle.snapshot()
