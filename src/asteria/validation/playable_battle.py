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
from asteria.rpg import (
    AIDecisionRule,
    BattleAction,
    BattleRuntime,
    EnemyAIDefinition,
    Party,
    PartyMember,
)

from .playable_rpg import PlayableRpgValidationHarness


@dataclass(frozen=True, slots=True)
class BattleTraceEntry:
    actor_id: str
    ability_id: str
    target_ids: tuple[str, ...]
    target_vitality_before: tuple[float, ...]
    target_vitality_after: tuple[float, ...]
    source: str


@dataclass(slots=True)
class PlayableBattleScenario:
    battle: BattleRuntime
    player_member_id: str
    enemy_member_id: str
    enemy_ai_id: str
    trace: list[BattleTraceEntry]


def _subject_from_resolved_build(build):
    stats = StatBlock.from_data(build.stats.to_data())
    resources = ResourcePool.from_data(build.resources.to_data())
    tags = TagSet(build.tags.values())
    states = StateRuntime(StateRegistry(()), stats, resources, tags)
    return GameplaySubject(stats, resources, tags, states)


def _reference_enemy_subject():
    stats = StatBlock({"power": 24, "guard": 10, "speed": 8})
    resources = ResourcePool()
    resources.define("vitality", 320, current=320)
    resources.define("fury", 5, current=5)
    tags = TagSet(("combatant.reference_enemy",))
    states = StateRuntime(StateRegistry(()), stats, resources, tags)
    return GameplaySubject(stats, resources, tags, states)


def _damage_ability(ability_id, amount):
    return AbilityDefinition(
        ability_id,
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
                            -abs(float(amount)),
                        ),
                    ),
                ),
            ),
        ),
    )


def build_reference_battle_scenario():
    """Connect Batch 119's resolved actor to the frozen canonical battle runtime.

    Player and enemy actions are registered in the same AbilityRegistry and are
    executed by the same BattleRuntime. AI only chooses an action; it does not
    own a second enemy-only execution path.
    """
    rpg = PlayableRpgValidationHarness()
    build = rpg.scenario.resolve()

    registry = AbilityRegistry()
    # Reference-project authored effects. The ability IDs can originate from any
    # resolved source; BattleRuntime does not care whether they came from class,
    # equipment, progression, attachment, passive, or learned state.
    authored_damage = {
        "basic_attack": 12,
        "power_strike": 28,
        "double_strike": 18,
        "flame_slash": 22,
        "venom_edge": 16,
        "tempered_arc": 30,
        "enemy_claw": 17,
        "enemy_crush": 26,
    }
    for ability_id, amount in authored_damage.items():
        registry.register(_damage_ability(ability_id, amount))
    abilities = AbilityRuntime(registry)

    player_ability_ids = tuple(x for x in build.abilities if x in authored_damage)
    enemy_ability_ids = ("enemy_claw", "enemy_crush")
    player = PartyMember(
        "validation_hero",
        "side.alpha",
        _subject_from_resolved_build(build),
        ability_ids=player_ability_ids,
        initiative=12,
    )
    enemy = PartyMember(
        "reference_enemy",
        "side.omega",
        _reference_enemy_subject(),
        ability_ids=enemy_ability_ids,
        initiative=8,
    )

    ai = EnemyAIDefinition(
        "reference_enemy_ai",
        rules=(
            AIDecisionRule(
                "heavy",
                "ability",
                payload={"ability_id": "enemy_crush"},
                target_selector="first_opponent",
                priority=20,
            ),
            AIDecisionRule(
                "light",
                "ability",
                payload={"ability_id": "enemy_claw"},
                target_selector="first_opponent",
                priority=10,
            ),
        ),
    )
    battle = BattleRuntime(
        (
            Party("side.alpha", (player,)),
            Party("side.omega", (enemy,)),
        ),
        abilities,
        enemy_ai_definitions=(ai,),
        rng_seed=120,
    )
    return PlayableBattleScenario(
        battle=battle,
        player_member_id=player.member_id,
        enemy_member_id=enemy.member_id,
        enemy_ai_id=ai.ai_id,
        trace=[],
    )


class PlayableBattleValidationHarness:
    def __init__(self, scenario=None):
        self.scenario = scenario or build_reference_battle_scenario()

    def _vitalities(self, target_ids):
        return tuple(
            self.scenario.battle.member(x).subject.resources.current("vitality")
            for x in target_ids
        )

    def player_action(self, ability_id, target_ids=None):
        target_ids = tuple(target_ids or (self.scenario.enemy_member_id,))
        before = self._vitalities(target_ids)
        result = self.scenario.battle.execute(
            BattleAction(self.scenario.player_member_id, ability_id, target_ids)
        )
        after = self._vitalities(target_ids)
        self.scenario.trace.append(
            BattleTraceEntry(
                self.scenario.player_member_id,
                ability_id,
                target_ids,
                before,
                after,
                "player_input",
            )
        )
        return result

    def enemy_action(self):
        battle = self.scenario.battle
        decision = battle.enemy_ai.decide(
            battle,
            self.scenario.enemy_ai_id,
            self.scenario.enemy_member_id,
            rng=battle.rng,
        )
        if decision is None:
            return None
        before = self._vitalities(decision.target_ids)
        result = battle.enemy_ai.execute_decision(battle, decision, rng=battle.rng)
        after = self._vitalities(decision.target_ids)
        self.scenario.trace.append(
            BattleTraceEntry(
                decision.actor_id,
                str(decision.payload.get("ability_id", decision.action_kind)),
                decision.target_ids,
                before,
                after,
                "enemy_ai",
            )
        )
        return result

    def run_exchange(self, player_ability_id="power_strike"):
        self.player_action(player_ability_id)
        self.enemy_action()
        return tuple(self.scenario.trace)
