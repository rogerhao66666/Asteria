import random

import pytest

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
    TagSet,
    TargetingRule,
)
from asteria.rpg import (
    BattleAction,
    BattleEscapeRule,
    BattleObjectiveCondition,
    BattleObjectiveDefinition,
    BattleRuntime,
    BattleTargetingDefinition,
    CombatantLifecycleRuntime,
    Party,
    PartyMember,
    RpgDatabase,
)


def subject(hp=100, stats=None):
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    return GameplaySubject(StatBlock(stats or {}), resources, TagSet())


def member(member_id, side, hp=100, initiative=0, abilities=("hit",)):
    return PartyMember(
        member_id,
        side,
        subject(hp),
        ability_ids=abilities,
        initiative=initiative,
    )


def runtime():
    registry = AbilityRegistry()
    registry.register(
        AbilityDefinition(
            "hit",
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=False),
            effects=[
                AbilityEffect(
                    AbilityTargetMode.SELECTED,
                    Effect("hit", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -10)]),
                )
            ],
        )
    )
    registry.register(
        AbilityDefinition(
            "revive",
            targeting=TargetingRule(minimum_targets=1, maximum_targets=1, allow_self=True),
            effects=[],
        )
    )
    return AbilityRuntime(registry)


def make_battle(**kwargs):
    hero = member("hero", "heroes", initiative=20, abilities=("hit", "revive"))
    ally = member("ally", "heroes", initiative=10, abilities=("hit",))
    enemy = member("enemy", "enemies", initiative=15, abilities=("hit",))
    return BattleRuntime(
        [Party("heroes", [hero, ally]), Party("enemies", [enemy])],
        runtime(),
        is_active=lambda m: m.subject.resources.current("hp") > 0,
        targeting_definitions=[
            BattleTargetingDefinition("hit", relation="opponent"),
            BattleTargetingDefinition("revive", relation="ally", active_only=False),
        ],
        **kwargs,
    )


def test_lifecycle_state_is_open_vocabulary_and_snapshot_roundtrip():
    m = member("a", "side")
    life = CombatantLifecycleRuntime([m])
    state = life.incapacitate("a", state_id="crystal.prison", reason="script")
    assert state.state_id == "crystal.prison"
    assert state.targetable
    restored = CombatantLifecycleRuntime.from_data(life.to_data())
    assert restored.state("a") == state


def test_incapacitate_removes_current_turn_and_blocks_actions():
    battle = make_battle()
    assert battle.next_actor().member_id == "hero"
    battle.incapacitate("hero", state_id="ko")
    assert battle.next_actor().member_id == "enemy"
    with pytest.raises(ValueError, match="cannot act"):
        battle.execute(BattleAction("hero", "hit", ("enemy",)))


def test_incapacitated_member_can_remain_targetable_for_revival():
    battle = make_battle()
    battle.incapacitate("ally", state_id="ko", targetable=True)
    resolution = battle.resolve_targets("hero", "revive", ("ally",))
    assert resolution.valid
    assert "ally" in resolution.candidate_ids
    battle.revive("ally")
    assert battle.is_active(battle.member("ally"))


def test_removed_member_is_not_targetable_even_when_active_only_false():
    battle = make_battle()
    battle.remove_combatant("ally", state_id="banished")
    resolution = battle.resolve_targets("hero", "revive", ("ally",))
    assert "ally" not in resolution.candidate_ids
    assert not resolution.valid


def test_dynamic_base_active_predicate_still_sees_hp_changes():
    battle = make_battle()
    battle.member("enemy").subject.resources.set_current("hp", 0)
    assert not battle.is_active(battle.member("enemy"))
    outcome = battle.resolve_outcome()
    assert outcome.finished
    assert outcome.winning_sides == ("heroes",)


def test_summon_adds_runtime_member_and_next_round_turn_source():
    battle = make_battle()
    summon = member("wolf", "heroes", initiative=30)
    battle.summon(summon, owner_id="hero")
    assert battle.member("wolf") is summon
    assert battle.combatants.state("wolf").summon_owner_id == "hero"
    assert "wolf" not in [x.member_id for x in battle.turn_queue.pending()]
    battle.start_next_round()
    assert battle.next_actor().member_id == "wolf"


def test_summon_can_join_current_round_explicitly():
    battle = make_battle()
    battle.summon(member("sprite", "heroes", initiative=99), join_current_round=True)
    assert battle.next_actor().member_id == "sprite"


def test_transform_swaps_runtime_form_and_reverts_without_changing_identity():
    battle = make_battle()
    dragon = PartyMember("hero", "heroes", subject(100), ability_ids=("hit",), initiative=99)
    battle.transform("hero", dragon, form_id="dragon")
    assert battle.member("hero") is dragon
    assert battle.combatants.state("hero").form_id == "dragon"
    assert battle.turn_queue.peek().initiative == 99
    original = battle.revert_transform("hero")
    assert original.member_id == "hero"
    assert battle.combatants.state("hero").form_id is None


def test_objective_eliminate_side_finishes_battle():
    objective = BattleObjectiveDefinition(
        "defeat.enemies",
        success_conditions=(BattleObjectiveCondition("side_active_count", "enemies", "==", 0),),
        winning_sides=("heroes",),
        defeated_sides=("enemies",),
    )
    battle = make_battle(objective_definitions=(objective,))
    assert not battle.resolve_outcome().finished
    battle.incapacitate("enemy", state_id="ko")
    outcome = battle.resolve_outcome()
    assert outcome.finished
    assert outcome.objective_ids == ("defeat.enemies",)
    assert outcome.winning_sides == ("heroes",)


def test_objective_survive_rounds_and_protect_member_failure():
    objective = BattleObjectiveDefinition(
        "survive",
        success_conditions=(BattleObjectiveCondition("round_index", "battle", ">=", 3),),
        failure_conditions=(BattleObjectiveCondition("member_active", "hero", "==", False),),
        winning_sides=("heroes",),
        defeated_sides=("enemies",),
    )
    battle = make_battle(objective_definitions=(objective,))
    battle.start_next_round()
    battle.start_next_round()
    outcome = battle.resolve_outcome()
    assert outcome.finished and outcome.objective_ids == ("survive",)

    battle = make_battle(objective_definitions=(objective,))
    battle.incapacitate("hero")
    outcome = battle.resolve_outcome()
    assert outcome.finished
    assert outcome.winning_sides == ("enemies",)


def test_objective_custom_flag_supports_scripted_win_condition():
    objective = BattleObjectiveDefinition(
        "seal.portal",
        success_conditions=(BattleObjectiveCondition("flag", "portal.sealed", "==", True),),
        winning_sides=("heroes",),
    )
    battle = make_battle(objective_definitions=(objective,))
    assert not battle.resolve_outcome().finished
    battle.set_objective_flag("portal.sealed")
    assert battle.resolve_outcome().finished


def test_escape_rule_is_seeded_and_stat_driven():
    hero = member("hero", "heroes")
    hero.subject.stats.set("speed", 20)
    enemy = member("enemy", "enemies")
    enemy.subject.stats.set("pursuit", 10)
    rule = BattleEscapeRule(
        "run",
        "heroes",
        base_chance=0.2,
        source_stat="speed",
        source_scale=0.02,
        opponent_stat="pursuit",
        opponent_scale=0.01,
    )
    battle = BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])],
        runtime(),
        escape_rules=(rule,),
    )
    result = battle.attempt_escape("run", rng=random.Random(1))
    assert result.chance == pytest.approx(0.5)
    assert result.succeeded
    outcome = battle.resolve_outcome()
    assert outcome.finished
    assert outcome.escaped_sides == ("heroes",)


def test_escape_failure_does_not_remove_party():
    rule = BattleEscapeRule("nope", "heroes", base_chance=0.0)
    battle = make_battle(escape_rules=(rule,))
    result = battle.attempt_escape("nope", rng=random.Random(1))
    assert not result.succeeded
    assert battle.combatants.state("hero").present
    assert not battle.resolve_outcome().finished


def test_database_v13_roundtrip_and_v12_backward_read():
    db = RpgDatabase()
    objective = BattleObjectiveDefinition(
        "obj",
        success_conditions=(BattleObjectiveCondition("flag", "done"),),
        winning_sides=("heroes",),
    )
    rule = BattleEscapeRule("escape", "heroes", base_chance=0.5)
    db.add_battle_objective(objective)
    db.add_escape_rule(rule)
    data = db.to_data()
    assert data["version"] == 29
    restored = RpgDatabase.from_data(data)
    assert restored.battle_objectives["obj"] == objective
    assert restored.escape_rules["escape"] == rule

    old = db.to_data()
    old["version"] = 12
    old.pop("battle_objectives")
    old.pop("escape_rules")
    restored_old = RpgDatabase.from_data(old)
    assert restored_old.battle_objectives == {}
    assert restored_old.escape_rules == {}


def test_explicit_objectives_override_legacy_elimination_fallback():
    objective = BattleObjectiveDefinition(
        "survive.until.flag",
        success_conditions=(BattleObjectiveCondition("flag", "done"),),
        winning_sides=("heroes",),
    )
    battle = make_battle(objective_definitions=(objective,))
    battle.incapacitate("enemy")
    assert not battle.resolve_outcome().finished
    battle.set_objective_flag("done")
    assert battle.resolve_outcome().finished


def test_failed_summon_slot_validation_is_atomic():
    from asteria.rpg import BattleFormationRuntime, BattlePlacement, FormationDefinition, FormationSlotDefinition

    base = make_battle()
    formation = BattleFormationRuntime(
        FormationDefinition("heroes.form", [FormationSlotDefinition("only")]),
        [BattlePlacement("hero", "only")],
    )
    # Rebuild with a formation because make_battle intentionally has none.
    battle = BattleRuntime(
        [base.parties["heroes"], base.parties["enemies"]],
        runtime(),
        is_active=lambda m: m.subject.resources.current("hp") > 0,
        formations={"heroes": formation},
    )
    before = tuple(battle.members)
    with pytest.raises(ValueError, match="occupied"):
        battle.summon(member("wolf", "heroes"), slot_id="only")
    assert tuple(battle.members) == before
    assert "wolf" not in battle.parties["heroes"].ids()


def test_objective_priority_is_deterministic_when_multiple_complete():
    low = BattleObjectiveDefinition(
        "low",
        success_conditions=(BattleObjectiveCondition("flag", "done"),),
        winning_sides=("heroes",),
        priority=1,
    )
    high = BattleObjectiveDefinition(
        "high",
        success_conditions=(BattleObjectiveCondition("flag", "done"),),
        winning_sides=("heroes",),
        priority=10,
    )
    battle = make_battle(objective_definitions=(low, high))
    battle.set_objective_flag("done")
    assert battle.resolve_outcome().objective_ids == ("high",)
