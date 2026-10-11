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
    BattleFormationRuntime,
    BattlePlacement,
    BattleRuntime,
    BattleTargetingDefinition,
    BattleTargetingRuntime,
    FormationDefinition,
    FormationSlotDefinition,
    Party,
    PartyMember,
    RpgDatabase,
    TargetMetricCondition,
    TargetRelation,
)


def subject(hp=100, *, tags=(), stats=None):
    resources = ResourcePool()
    resources.define("hp", 100, current=hp)
    return GameplaySubject(StatBlock(stats or {}), resources, TagSet(tags))


def member(member_id, side, *, hp=100, tags=(), stats=None, abilities=("hit",)):
    return PartyMember(
        member_id,
        side,
        subject(hp, tags=tags, stats=stats),
        ability_ids=abilities,
    )


def ability_runtime():
    registry = AbilityRegistry()
    for ability_id, max_targets in (("hit", 1), ("sweep", 8), ("heal", 1), ("snipe", 1)):
        registry.register(
            AbilityDefinition(
                ability_id,
                targeting=TargetingRule(
                    minimum_targets=1,
                    maximum_targets=max_targets,
                    allow_self=True,
                ),
                effects=[
                    AbilityEffect(
                        AbilityTargetMode.SELECTED,
                        Effect(
                            f"{ability_id}.effect",
                            [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", -1)],
                        ),
                    )
                ],
            )
        )
    return AbilityRuntime(registry)


def formation():
    return FormationDefinition(
        "party.grid",
        [
            FormationSlotDefinition("front.a", x=0, y=0, tags=("row.front",), adjacent_to=("front.b", "back.a")),
            FormationSlotDefinition("front.b", x=1, y=0, tags=("row.front",), adjacent_to=("front.a", "back.b")),
            FormationSlotDefinition("back.a", x=0, y=1, tags=("row.back",), adjacent_to=("front.a", "back.b")),
            FormationSlotDefinition("back.b", x=1, y=1, tags=("row.back",), adjacent_to=("front.b", "back.a")),
        ],
    )


def test_formation_definition_roundtrip_and_adjacency():
    definition = formation()
    restored = FormationDefinition.from_data(definition.to_data())
    assert restored == definition
    runtime = BattleFormationRuntime(
        definition,
        [BattlePlacement("a", "front.a"), BattlePlacement("b", "front.b"), BattlePlacement("c", "back.a")],
    )
    assert runtime.adjacent_member_ids("a") == ("b", "c")


def test_formation_rejects_bad_graph_and_slot_collision():
    with pytest.raises(ValueError):
        FormationDefinition("bad", [FormationSlotDefinition("a", adjacent_to=("missing",))])
    runtime = BattleFormationRuntime(formation())
    runtime.place("a", "front.a")
    with pytest.raises(ValueError):
        runtime.place("b", "front.a")


def test_target_relation_and_subject_tag_filters():
    hero = member("hero", "heroes")
    ally = member("ally", "heroes", tags=("role.healer",))
    goblin = member("goblin", "enemies", tags=("species.goblin",))
    ghost = member("ghost", "enemies", tags=("species.ghost", "untargetable.physical"))
    runtime = BattleTargetingRuntime(
        {x.member_id: x for x in (hero, ally, goblin, ghost)},
        definitions=[
            BattleTargetingDefinition(
                "hit",
                relation=TargetRelation.OPPONENT,
                blocked_subject_tags=("untargetable.physical",),
            )
        ],
    )
    assert runtime.candidates("hero", "hit") == ("goblin",)


def test_slot_tags_enable_front_back_and_boss_parts_without_hardcoding():
    hero = member("hero", "heroes")
    core = member("boss.core", "enemies", tags=("boss.part",))
    shell = member("boss.shell", "enemies", tags=("boss.part",))
    enemy_form = BattleFormationRuntime(
        FormationDefinition(
            "boss.parts",
            [
                FormationSlotDefinition("core.slot", tags=("part.core", "row.back")),
                FormationSlotDefinition("shell.slot", tags=("part.shell", "row.front")),
            ],
        ),
        [BattlePlacement("boss.core", "core.slot"), BattlePlacement("boss.shell", "shell.slot")],
    )
    runtime = BattleTargetingRuntime(
        {x.member_id: x for x in (hero, core, shell)},
        definitions=[
            BattleTargetingDefinition(
                "snipe",
                relation="opponent",
                required_slot_tags=("part.core",),
            )
        ],
        formations={"enemies": enemy_form},
    )
    assert runtime.candidates("hero", "snipe") == ("boss.core",)


def test_metric_conditions_support_low_hp_and_custom_stats():
    hero = member("hero", "heroes")
    low = member("low", "heroes", hp=20, stats={"threat": 7})
    high = member("high", "heroes", hp=90, stats={"threat": 2})
    runtime = BattleTargetingRuntime(
        {x.member_id: x for x in (hero, low, high)},
        definitions=[
            BattleTargetingDefinition(
                "heal",
                relation="ally",
                metric_conditions=(
                    TargetMetricCondition("resource_fraction", "hp", "<=", 0.5),
                    TargetMetricCondition("stat", "threat", ">=", 5),
                ),
            )
        ],
    )
    assert runtime.candidates("hero", "heal") == ("low",)


def test_all_and_random_n_are_resolved_deterministically_with_seeded_rng():
    hero = member("hero", "heroes")
    enemies = [member(f"e{i}", "enemies") for i in range(5)]
    members = {x.member_id: x for x in [hero, *enemies]}
    runtime = BattleTargetingRuntime(
        members,
        definitions=[
            BattleTargetingDefinition(
                "sweep",
                relation="opponent",
                selection_mode="all",
                minimum_targets=1,
                maximum_targets=8,
            ),
            BattleTargetingDefinition(
                "hit",
                relation="opponent",
                selection_mode="random_n",
                minimum_targets=2,
                maximum_targets=2,
                selection_count=2,
            ),
        ],
    )
    assert runtime.resolve("hero", "sweep").selected_ids == tuple(f"e{i}" for i in range(5))
    a = runtime.resolve("hero", "hit", rng=random.Random(42)).selected_ids
    b = runtime.resolve("hero", "hit", rng=random.Random(42)).selected_ids
    assert a == b
    assert len(a) == 2


def test_manual_target_validation_rejects_invalid_candidates():
    hero = member("hero", "heroes")
    ally = member("ally", "heroes")
    enemy = member("enemy", "enemies")
    runtime = BattleTargetingRuntime(
        {x.member_id: x for x in (hero, ally, enemy)},
        definitions=[BattleTargetingDefinition("hit", relation="opponent")],
    )
    result = runtime.resolve("hero", "hit", ("ally",))
    assert not result.valid
    assert result.errors == ("invalid_target:ally",)


def test_active_only_filters_defeated_members():
    hero = member("hero", "heroes")
    alive = member("alive", "enemies", hp=5)
    dead = member("dead", "enemies", hp=0)
    runtime = BattleTargetingRuntime(
        {x.member_id: x for x in (hero, alive, dead)},
        definitions=[BattleTargetingDefinition("hit", relation="opponent")],
        is_active=lambda m: m.subject.resources.current("hp") > 0,
    )
    assert runtime.candidates("hero", "hit") == ("alive",)


def test_battle_runtime_uses_auto_target_selection_and_manual_validation():
    hero = member("hero", "heroes", abilities=("sweep", "hit"))
    e1 = member("e1", "enemies")
    e2 = member("e2", "enemies")
    battle = BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [e1, e2])],
        ability_runtime(),
        targeting_definitions=[
            BattleTargetingDefinition(
                "sweep",
                relation="opponent",
                selection_mode="all",
                minimum_targets=1,
                maximum_targets=8,
            ),
            BattleTargetingDefinition("hit", relation="opponent"),
        ],
    )
    result = battle.execute(BattleAction("hero", "sweep", ()))
    assert result.action.target_ids == ("e1", "e2")
    assert e1.subject.resources.current("hp") == 99
    assert e2.subject.resources.current("hp") == 99
    with pytest.raises(ValueError, match="invalid battle targets"):
        battle.execute(BattleAction("hero", "hit", ("hero",)))


def test_database_v12_roundtrip_and_v11_backward_read():
    db = RpgDatabase()
    db.add_formation(formation())
    db.add_battle_targeting(BattleTargetingDefinition("hit", relation="opponent"))
    data = db.to_data()
    assert data["version"] == 26
    restored = RpgDatabase.from_data(data)
    assert "party.grid" in restored.formations
    assert restored.battle_targeting["hit"].relation is TargetRelation.OPPONENT

    old = db.to_data()
    old["version"] = 11
    old.pop("formations")
    old.pop("battle_targeting")
    restored_old = RpgDatabase.from_data(old)
    assert restored_old.formations == {}
    assert restored_old.battle_targeting == {}


def test_many_slots_and_targets_have_no_engine_hard_cap():
    slots = [FormationSlotDefinition(f"s{i}", x=i) for i in range(256)]
    definition = FormationDefinition("huge", slots)
    placements = [BattlePlacement(f"m{i}", f"s{i}") for i in range(256)]
    runtime = BattleFormationRuntime(definition, placements)
    assert len(runtime.placements()) == 256
