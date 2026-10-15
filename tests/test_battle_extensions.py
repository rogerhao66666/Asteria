"""Optional battle rules: taunt, life steal, overkill, limits, mastery, opening, steal, rows."""

import random

import pytest

from asteria.core.lifecycle import LifecycleHookBus
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
    BattleExtensionRules,
    BattleRuntime,
    Party,
    PartyMember,
    StealEntry,
    StealTable,
)
from asteria.rpg.battle_scheduler import BattleSchedulerDefinition
from asteria.rpg.items import Inventory
from asteria.rpg.targeting import (
    BattleFormationRuntime,
    BattleTargetingDefinition,
    FormationDefinition,
    FormationSlotDefinition,
    TargetSelectionMode,
)


def _ability(ability_id, value, *, mode=AbilityTargetMode.SELECTED, maximum=1):
    return AbilityDefinition(
        ability_id,
        targeting=TargetingRule(minimum_targets=1, maximum_targets=maximum, allow_self=True),
        effects=(
            AbilityEffect(
                mode,
                Effect(
                    f"{ability_id}.fx",
                    (EffectOperation(EffectOperationKind.RESOURCE_DELTA, "hp", value),),
                ),
            ),
        ),
    )


def _subject(hp, tags=(), stats=None):
    resources = ResourcePool()
    resources.define("hp", hp, current=hp)
    return GameplaySubject(StatBlock(stats or {}), resources, TagSet(tags))


def _battle(rules, *, enemies=None, hero_stats=None, formations=None, scheduler=None):
    registry = AbilityRegistry()
    registry.register(_ability("strike", -100))
    registry.register(_ability("nova", -100, maximum=5))
    ids = ("strike", "nova")
    hero = PartyMember(
        "hero", "heroes", _subject(500, stats=hero_stats), ability_ids=ids, initiative=20
    )
    foes = [
        PartyMember(name, "foes", _subject(hp, tags), ability_ids=ids, initiative=1)
        for name, hp, tags in (
            enemies or (("slime", 300, ()), ("guard", 300, ("taunt",)), ("bat", 40, ()))
        )
    ]
    return BattleRuntime(
        (Party("heroes", (hero,)), Party("foes", tuple(foes))),
        AbilityRuntime(registry),
        targeting_definitions=(
            BattleTargetingDefinition("strike"),
            BattleTargetingDefinition(
                "nova",
                selection_mode=TargetSelectionMode.ALL,
                minimum_targets=1,
                maximum_targets=5,
            ),
        ),
        formations=formations,
        scheduler_definition=scheduler,
        extensions=rules,
        rng_seed=3,
    )


def _hp(battle, member_id):
    return battle.member(member_id).subject.resources.current("hp")


def test_taunt_forces_single_targets_but_not_area_attacks():
    battle = _battle(BattleExtensionRules("x", taunt_tag="taunt"))
    assert battle.resolve_targets("hero", "strike").candidate_ids == ("guard",)
    with pytest.raises(ValueError, match="invalid battle targets"):
        battle.execute(BattleAction("hero", "strike", ("slime",)))
    battle.execute(BattleAction("hero", "strike", ("guard",)))
    assert _hp(battle, "guard") == 200
    battle.execute(BattleAction("hero", "nova", ()))
    assert [_hp(battle, x) for x in ("slime", "guard", "bat")] == [200, 100, 0]


def test_taunt_ends_when_the_taunter_loses_the_tag():
    battle = _battle(BattleExtensionRules("x", taunt_tag="taunt"))
    battle.member("guard").subject.tags.remove("taunt")
    assert set(battle.resolve_targets("hero", "strike").candidate_ids) == {"slime", "guard", "bat"}


def test_without_extensions_nothing_changes():
    battle = _battle(None)
    assert set(battle.resolve_targets("hero", "strike").candidate_ids) == {"slime", "guard", "bat"}
    battle.execute(BattleAction("hero", "strike", ("slime",)))
    assert _hp(battle, "slime") == 200


def test_life_steal_returns_a_share_of_damage_dealt():
    rules = BattleExtensionRules("x", damage_resource="hp", lifesteal_stat="leech")
    battle = _battle(rules, hero_stats={"leech": 0.5})
    battle.member("hero").subject.resources.change("hp", -300)
    battle.execute(BattleAction("hero", "strike", ("slime",)))
    assert _hp(battle, "hero") == 250  # 200 + half of 100
    assert battle.extensions.damage_dealt["hero"] == 100
    assert battle.extensions.lifesteal_healed["hero"] == 50


def test_life_steal_is_limited_to_damage_actually_taken():
    rules = BattleExtensionRules("x", damage_resource="hp", lifesteal_stat="leech")
    battle = _battle(rules, hero_stats={"leech": 1.0})
    battle.member("hero").subject.resources.change("hp", -100)
    battle.execute(BattleAction("hero", "strike", ("bat",)))  # bat has only 40 left
    assert _hp(battle, "hero") == 440
    assert battle.extensions.damage_dealt["hero"] == 40


def test_overkill_is_recorded_and_scales_the_reward():
    rules = BattleExtensionRules("x", damage_resource="hp", overkill_rate=2.0, overkill_cap=1.0)
    battle = _battle(rules)
    battle.execute(BattleAction("hero", "strike", ("bat",)))
    assert battle.extensions.overkill["bat"] == 60
    # 60 over a 40 maximum: ratio 1.5 capped at 1.0 -> 1 + 2.0 * 1.0
    assert battle.extensions.overkill_scale(battle, "bat") == pytest.approx(3.0)
    assert battle.extensions.overkill_scale(battle, "slime") == 1.0


def test_exact_kill_is_not_overkill():
    rules = BattleExtensionRules("x", damage_resource="hp", overkill_rate=1.0)
    battle = _battle(rules, enemies=(("imp", 100, ()),))
    battle.execute(BattleAction("hero", "strike", ("imp",)))
    assert "imp" not in battle.extensions.overkill


def test_use_limits_count_per_user_and_per_battle():
    battle = _battle(BattleExtensionRules("x", use_limits={"strike": 2}))
    assert battle.extensions.uses_left("hero", "strike") == 2
    battle.execute(BattleAction("hero", "strike", ("guard",)))
    battle.execute(BattleAction("hero", "strike", ("guard",)))
    assert battle.extensions.uses_left("hero", "strike") == 0
    with pytest.raises(ValueError, match="use limit"):
        battle.execute(BattleAction("hero", "strike", ("guard",)))
    assert battle.extensions.uses_left("hero", "nova") is None


def test_mastery_levels_up_and_tags_the_user():
    battle = _battle(BattleExtensionRules("x", mastery={"strike": (2, 4)}))
    tags = battle.member("hero").subject.tags
    for _ in range(2):
        battle.execute(BattleAction("hero", "strike", ("slime",)))
    assert battle.extensions.mastery_level("hero", "strike") == 1
    assert tags.contains("mastery.strike.1") and tags.contains("mastery.strike")
    for _ in range(2):
        battle.execute(BattleAction("hero", "strike", ("slime",)))
    assert tags.contains("mastery.strike.2") and not tags.contains("mastery.strike.1")


def test_mastery_up_emits_a_hook():
    seen = []
    bus = LifecycleHookBus()
    bus.subscribe("rpg.battle.mastery_up", lambda event: seen.append(event.data["level"]))
    battle = _battle(BattleExtensionRules("x", mastery={"strike": (1,)}))
    battle.hooks = bus
    battle.execute(BattleAction("hero", "strike", ("slime",)))
    assert seen == [1]


def test_opening_roll_follows_the_configured_odds():
    rules = BattleExtensionRules("x", preemptive_chance=0.25, surprise_chance=0.25)
    battle = _battle(rules)
    rolls = [battle.extensions.roll_opening(random.Random(i)) for i in range(400)]
    assert {"normal", "preemptive", "surprise"} == set(rolls)
    assert 70 < rolls.count("preemptive") < 130 and 70 < rolls.count("surprise") < 130
    never = _battle(BattleExtensionRules("x"))
    assert {never.extensions.roll_opening(random.Random(i)) for i in range(50)} == {"normal"}


def test_preemptive_opening_removes_the_foes_first_turns():
    battle = _battle(BattleExtensionRules("x"))
    removed = battle.extensions.apply_opening(battle, "preemptive", "heroes")
    assert set(removed) == {"slime", "guard", "bat"}
    assert [e.member_id for e in battle.turn_queue.pending()] == ["hero"]


def test_surprise_opening_removes_the_players_first_turn():
    battle = _battle(BattleExtensionRules("x"))
    battle.extensions.apply_opening(battle, "surprise", "heroes")
    assert "hero" not in [e.member_id for e in battle.turn_queue.pending()]


def test_row_tags_follow_the_formation_slot():
    formation = FormationDefinition(
        "line",
        (
            FormationSlotDefinition("a", tags=("front",)),
            FormationSlotDefinition("b", tags=("back",)),
        ),
    )
    runtime = BattleFormationRuntime(formation)
    runtime.place("hero", "b")
    rules = BattleExtensionRules("x", row_tag_prefix="row.")
    battle = _battle(rules, formations={"heroes": runtime})
    assert battle.member("hero").subject.tags.contains("row.back")
    runtime.place("hero", "a")
    battle.extensions.sync_row_tags(battle)
    tags = battle.member("hero").subject.tags
    assert tags.contains("row.front") and not tags.contains("row.back")


def test_steal_uses_the_table_once_per_target():
    table = StealTable("guard", (StealEntry("key", 1.0), StealEntry("gem", 1.0)))
    battle = _battle(BattleExtensionRules("x", steal_tables=(table,)))
    bag = Inventory()
    first = battle.extensions.steal(battle, "hero", "guard", bag, random.Random(1))
    assert first.stolen and first.item_id == "key" and bag.count("key") == 1
    again = battle.extensions.steal(battle, "hero", "guard", bag, random.Random(1))
    assert not again.stolen and again.reason == "already_stolen"
    other = battle.extensions.steal(battle, "hero", "slime", bag, random.Random(1))
    assert other.reason == "nothing_to_steal"
    ally = battle.extensions.steal(battle, "hero", "hero", bag, random.Random(1))
    assert ally.reason == "not_an_opponent"


def test_steal_table_matches_a_subject_tag_and_can_fail():
    table = StealTable("beast", (StealEntry("fang", 0.0),), once=False)
    battle = _battle(
        BattleExtensionRules("x", steal_tables=(table,)),
        enemies=(("wolf", 100, ("beast",)),),
    )
    bag = Inventory()
    result = battle.extensions.steal(battle, "hero", "wolf", bag, random.Random(1))
    assert not result.stolen and result.reason == "failed"
    boosted = battle.extensions.steal(
        battle, "hero", "wolf", bag, random.Random(1), chance_bonus=1.0
    )
    assert boosted.stolen and bag.count("fang") == 1


def test_rules_round_trip_through_data_and_validate():
    rules = BattleExtensionRules(
        "x",
        damage_resource="hp",
        taunt_tag="taunt",
        lifesteal_stat="leech",
        overkill_rate=0.5,
        use_limits={"strike": 3},
        mastery={"strike": (2, 5)},
        preemptive_chance=0.1,
        surprise_chance=0.2,
        steal_tables=(StealTable("guard", (StealEntry("key", 0.5, 2),), once=False),),
        row_tag_prefix="row.",
    )
    assert BattleExtensionRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError):
        BattleExtensionRules("x", preemptive_chance=0.7, surprise_chance=0.5)
    with pytest.raises(ValueError):
        BattleExtensionRules("x", mastery={"strike": (5, 2)})
    with pytest.raises(ValueError):
        BattleExtensionRules.from_data({"schema": "nope", "version": 1})


def test_extensions_work_with_a_continuous_scheduler():
    scheduler = BattleSchedulerDefinition("atb", mode="continuous")
    battle = _battle(BattleExtensionRules("x", taunt_tag="taunt"), scheduler=scheduler)
    assert battle.resolve_targets("hero", "strike").candidate_ids == ("guard",)


# ---- resource gains (TP-style modes) ---------------------------------------------------------
from asteria.rpg import ResourceGain  # noqa: E402
from asteria.rpg.battle_resources import BattleResourceDefinition  # noqa: E402


def _gain_battle(*gains):
    rules = BattleExtensionRules("x", damage_resource="hp", gains=gains)
    registry = AbilityRegistry()
    registry.register(_ability("strike", -100))
    hero = PartyMember("hero", "heroes", _subject(500), ability_ids=("strike",), initiative=20)
    foe = PartyMember("foe", "foes", _subject(250), ability_ids=("strike",), initiative=1)
    weak = PartyMember("weak", "foes", _subject(60), ability_ids=("strike",), initiative=1)
    return BattleRuntime(
        (Party("heroes", (hero,)), Party("foes", (foe, weak))),
        AbilityRuntime(registry),
        resource_definitions=(
            BattleResourceDefinition(
                "tp", minimum=0, maximum=100, start_mode="fixed", start_value=0
            ),
        ),
        targeting_definitions=(BattleTargetingDefinition("strike"),),
        extensions=rules,
    )


def _tp(battle, member):
    return battle.battle_resources.current(member, "tp")


def test_gain_per_action_and_per_damage_dealt():
    battle = _gain_battle(
        ResourceGain("action", "tp", flat=5), ResourceGain("dealt", "tp", per_damage=0.1)
    )
    battle.execute(BattleAction("hero", "strike", ("foe",)))
    assert _tp(battle, "hero") == pytest.approx(5 + 10)  # 100 damage dealt
    assert _tp(battle, "foe") == 0  # only the actor gains


def test_gain_when_hurt_scales_with_the_share_of_max_hp_lost():
    battle = _gain_battle(ResourceGain("taken", "tp", per_max_hp=40))
    battle.execute(BattleAction("hero", "strike", ("foe",)))
    assert _tp(battle, "foe") == pytest.approx(40 * 100 / 250)  # lost 100 of 250
    assert _tp(battle, "hero") == 0


def test_a_kill_gain_only_fires_when_the_target_falls():
    battle = _gain_battle(ResourceGain("kill", "tp", flat=30))
    battle.execute(BattleAction("hero", "strike", ("foe",)))
    assert _tp(battle, "hero") == 0
    battle.execute(BattleAction("hero", "strike", ("weak",)))  # 60 hp: 100 damage kills it
    assert _tp(battle, "hero") == 30


def test_a_gain_can_be_limited_to_abilities_with_a_tag():
    battle = _gain_battle(ResourceGain("action", "tp", flat=9, ability_tag="melee"))
    battle.execute(BattleAction("hero", "strike", ("foe",)))
    assert _tp(battle, "hero") == 0  # "strike" carries no melee tag


def test_gains_respect_the_resource_maximum_and_missing_resources():
    battle = _gain_battle(
        ResourceGain("action", "tp", flat=70), ResourceGain("action", "ghost", flat=1)
    )
    battle.execute(BattleAction("hero", "strike", ("foe",)))
    battle.execute(BattleAction("hero", "strike", ("foe",)))
    assert _tp(battle, "hero") == 100  # capped; the unknown resource is skipped silently
    assert battle.extensions.gained[("hero", "tp")] == 100  # only what was really added


def test_gain_rules_round_trip_and_validate():
    rules = BattleExtensionRules(
        "x",
        damage_resource="hp",
        gains=(ResourceGain("dealt", "tp", per_damage=0.5, ability_tag="melee"),),
    )
    assert BattleExtensionRules.from_data(rules.to_data()) == rules
    assert "gains" not in BattleExtensionRules("plain").to_data()
    with pytest.raises(ValueError):
        ResourceGain("sneeze", "tp")
    with pytest.raises(ValueError):
        ResourceGain("action", "tp", flat=float("inf"))
