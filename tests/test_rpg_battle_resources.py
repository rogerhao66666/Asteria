from asteria.core import LifecycleHookBus
from asteria.gameplay import AbilityRegistry, AbilityRuntime, GameplaySubject, ResourcePool, StatBlock, TagSet
from asteria.rpg import (
    BattleResourceDefinition,
    BattleResourceEndMode,
    BattleResourceRule,
    BattleResourceRuntime,
    BattleResourceStartMode,
    BattleRuntime,
    Party,
    PartyMember,
)


def make_subject(*, hp=100, mp=40):
    resources = ResourcePool()
    resources.define("hp", hp, current=hp)
    resources.define("mp", mp, current=mp)
    return GameplaySubject(StatBlock(), resources, TagSet())


def make_member(member_id="hero", subject=None, initiative=10):
    return PartyMember(member_id, "player", subject or make_subject(), initiative=initiative)


def test_combat_only_gauge_can_start_fixed_regen_decay_and_overflow():
    hero = make_member()
    definition = BattleResourceDefinition(
        "rage",
        minimum=0,
        maximum=100,
        overflow_limit=125,
        start_mode=BattleResourceStartMode.FIXED,
        start_value=20,
        rules=[
            BattleResourceRule("rpg.battle.round_started", 15),
            BattleResourceRule("rpg.battle.turn_ended", -5),
        ],
    )
    runtime = BattleResourceRuntime([definition], [hero])
    assert runtime.current("hero", "rage") == 20
    runtime.apply_trigger("rpg.battle.round_started")
    assert runtime.current("hero", "rage") == 35
    runtime.restore("hero", "rage", 100)
    value = runtime.get("hero", "rage")
    assert value.current == 125
    assert value.overflow == 25
    assert value.normalized == 1
    runtime.apply_trigger("rpg.battle.turn_ended", ["hero"])
    assert value.current == 120


def test_existing_subject_resource_is_bound_and_can_restore_initial_after_battle():
    subject = make_subject(mp=50)
    subject.resources.set_current("mp", 31)
    hero = make_member(subject=subject)
    definition = BattleResourceDefinition(
        "mp",
        start_mode="current",
        end_mode=BattleResourceEndMode.RESTORE_INITIAL,
    )
    runtime = BattleResourceRuntime([definition], [hero])
    assert runtime.current("hero", "mp") == 31
    assert runtime.spend("hero", "mp", 12)
    assert subject.resources.current("mp") == 19
    runtime.finish()
    assert runtime.current("hero", "mp") == 31
    assert subject.resources.current("mp") == 31


def test_reset_to_start_is_distinct_from_restore_initial():
    subject = make_subject(mp=50)
    subject.resources.set_current("mp", 30)
    hero = make_member(subject=subject)
    definition = BattleResourceDefinition(
        "mp",
        start_mode="fixed",
        start_value=10,
        end_mode="reset_to_start",
    )
    runtime = BattleResourceRuntime([definition], [hero])
    assert subject.resources.current("mp") == 10
    runtime.restore("hero", "mp", 20)
    runtime.finish()
    assert subject.resources.current("mp") == 10


def test_spend_is_atomic_when_insufficient():
    hero = make_member()
    definition = BattleResourceDefinition("boost", minimum=0, maximum=5, start_mode="fixed", start_value=2)
    runtime = BattleResourceRuntime([definition], [hero])
    assert runtime.spend("hero", "boost", 3) is False
    assert runtime.current("hero", "boost") == 2


def test_definition_and_runtime_snapshot_round_trip_without_replaying_rules():
    hero = make_member()
    definition = BattleResourceDefinition(
        "combo",
        minimum=0,
        maximum=10,
        start_mode="minimum",
        end_mode="persist",
        rules=[BattleResourceRule("custom.hit", 2)],
    )
    rebuilt_definition = BattleResourceDefinition.from_data(definition.to_data())
    runtime = BattleResourceRuntime([rebuilt_definition], [hero])
    runtime.apply_trigger("custom.hit", ["hero"])
    snapshot = runtime.to_data()
    restored = BattleResourceRuntime([rebuilt_definition], [hero])
    restored.restore_from_data(snapshot)
    assert restored.current("hero", "combo") == 2


def test_resource_lifecycle_hooks_are_generic_and_cross_thresholds_once():
    hooks = LifecycleHookBus()
    seen = []
    hooks.subscribe("*", lambda event: seen.append(event.name))
    hero = make_member()
    definition = BattleResourceDefinition("guard", minimum=0, maximum=10, start_mode="fixed", start_value=5)
    runtime = BattleResourceRuntime([definition], [hero], hooks=hooks)
    runtime.change("hero", "guard", 10)
    runtime.change("hero", "guard", -20)
    assert "rpg.battle_resource.changed" in seen
    assert seen.count("rpg.battle_resource.full") == 1
    assert seen.count("rpg.battle_resource.empty") == 1


def test_battle_runtime_applies_round_and_turn_rules_without_duplicate_next_actor_tick():
    hero = make_member()
    enemy = PartyMember("enemy", "enemy", make_subject(), initiative=1)
    definition = BattleResourceDefinition(
        "focus",
        minimum=0,
        maximum=20,
        start_mode="fixed",
        start_value=0,
        rules=[
            BattleResourceRule("rpg.battle.started", 1),
            BattleResourceRule("rpg.battle.round_started", 2),
            BattleResourceRule("rpg.battle.turn_ready", 3),
            BattleResourceRule("rpg.battle.turn_ended", 4),
        ],
    )
    battle = BattleRuntime(
        [Party("player", [hero]), Party("enemy", [enemy])],
        AbilityRuntime(AbilityRegistry()),
        resource_definitions=[definition],
    )
    # started + round_started
    assert battle.battle_resources.current("hero", "focus") == 3
    assert battle.next_actor().member_id == "hero"
    assert battle.battle_resources.current("hero", "focus") == 6
    # UI/polling may ask again; resource lifecycle must not tick twice.
    assert battle.next_actor().member_id == "hero"
    assert battle.battle_resources.current("hero", "focus") == 6
    battle.advance_turn()
    assert battle.battle_resources.current("hero", "focus") == 10


def test_battle_finish_policy_is_applied_once():
    subject = make_subject(mp=40)
    hero = make_member(subject=subject)
    enemy = PartyMember("enemy", "enemy", make_subject(), initiative=1)
    definition = BattleResourceDefinition(
        "mp",
        start_mode="current",
        end_mode="restore_initial",
        rules=[BattleResourceRule("rpg.battle.finished", -5)],
    )
    battle = BattleRuntime(
        [Party("player", [hero]), Party("enemy", [enemy])],
        AbilityRuntime(AbilityRegistry()),
        resource_definitions=[definition],
        is_active=lambda member: member.member_id == "hero",
    )
    battle.battle_resources.spend("hero", "mp", 10)
    assert subject.resources.current("mp") == 30
    assert battle.resolve_outcome().finished
    assert subject.resources.current("mp") == 40
    # Re-resolving outcome must not apply finish rules a second time.
    assert battle.resolve_outcome().finished
    assert subject.resources.current("mp") == 40


def test_rpg_database_owns_battle_resource_definitions_and_reads_v8_without_inventing_them():
    from asteria.rpg import RpgDatabase

    db = RpgDatabase()
    db.add_battle_resource(
        BattleResourceDefinition(
            "stagger",
            minimum=0,
            maximum=100,
            start_mode="maximum",
            rules=[BattleResourceRule("custom.hit", -20)],
        )
    )
    raw = db.to_data()
    assert raw["version"] == 30
    restored = RpgDatabase.from_data(raw)
    assert restored.battle_resources["stagger"].maximum == 100

    legacy = dict(raw)
    legacy["version"] = 8
    legacy.pop("battle_resources")
    restored_legacy = RpgDatabase.from_data(legacy)
    assert restored_legacy.battle_resources == {}
