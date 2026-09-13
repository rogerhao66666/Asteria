import json
import random

from asteria.gameplay import (
    AbilityRegistry, AbilityRuntime, GameplaySubject, ResourcePool, StateDefinition,
    StateRegistry, StateRuntime, StatBlock, TagSet,
)
from asteria.rpg import (
    BattleGaugeCompositionRuntime,
    BattleResourceDefinition,
    BattleRuntime,
    BattleSchedulerDefinition,
    GaugeCompositionDefinition,
    GaugeImpactRule,
    GaugeThresholdRule,
    Party,
    PartyMember,
    RpgDatabase,
)


def subject(*, states=(), tags=()):
    stats = StatBlock({"speed": 10})
    resources = ResourcePool()
    resources.define("hp", 100, current=100)
    tagset = TagSet(tags)
    registry = StateRegistry(states)
    state_runtime = StateRuntime(registry, stats, resources, tagset)
    return GameplaySubject(stats, resources, tagset, state_runtime)


def battle_fixture(*, composition=None, state_defs=(), scheduler=False):
    hero = PartyMember("hero", "heroes", subject(states=state_defs), initiative=20)
    enemy = PartyMember("enemy", "enemies", subject(states=state_defs), initiative=10)
    kwargs = {}
    if scheduler:
        kwargs["scheduler_definition"] = BattleSchedulerDefinition(
            "timeline", mode="continuous", timeline_scale=100
        )
    return BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])],
        AbilityRuntime(AbilityRegistry()),
        resource_definitions=[
            BattleResourceDefinition("stagger", minimum=0, maximum=100, start_mode="maximum"),
            BattleResourceDefinition("guard", minimum=0, maximum=50, start_mode="maximum"),
        ],
        gauge_composition_definitions=[composition] if composition else (),
        **kwargs,
    )


def break_composition(**threshold_kwargs):
    return GaugeCompositionDefinition(
        "stagger_break",
        impacts=[
            GaugeImpactRule(
                "weakness_pressure", "stagger", "battle.hit",
                delta=-20, required_outcome_tags_all=("outcome.weak",),
            ),
            GaugeImpactRule(
                "heavy_pressure", "stagger", "battle.hit",
                delta=-10, required_outcome_tags_all=("attack.heavy",),
            ),
        ],
        thresholds=[
            GaugeThresholdRule(
                "broken", "stagger", "at_or_below", 0,
                reset_to=100, **threshold_kwargs,
            )
        ],
    )


def test_definition_round_trip_is_generic_and_not_break_named_by_engine():
    definition = GaugeCompositionDefinition(
        "heat_model",
        impacts=[GaugeImpactRule("fire_heat", "guard", "custom.contact", delta=3)],
        thresholds=[GaugeThresholdRule("overheat", "guard", "at_or_above", 40, emit_trigger="custom.overheat")],
    )
    assert GaugeCompositionDefinition.from_data(definition.to_data()) == definition


def test_outcome_tags_drive_gauge_impact_without_element_or_break_enum():
    battle = battle_fixture(composition=break_composition())
    result = battle.apply_gauge_impact(
        "stagger_break", "hero", "enemy", trigger="battle.hit",
        outcome_tags=("outcome.weak",), value=25,
    )
    assert result.matched_impact_ids == ("weakness_pressure",)
    assert battle.battle_resources.current("enemy", "stagger") == 80
    assert result.thresholds == ()


def test_multiple_matching_rules_aggregate_before_threshold_evaluation():
    battle = battle_fixture(composition=break_composition())
    battle.battle_resources.change("enemy", "stagger", -75)
    result = battle.apply_gauge_impact(
        "stagger_break", "hero", "enemy", trigger="battle.hit",
        outcome_tags=("outcome.weak", "attack.heavy"),
    )
    assert set(result.matched_impact_ids) == {"weakness_pressure", "heavy_pressure"}
    assert len(result.changes) == 1
    assert len(result.thresholds) == 1
    assert battle.battle_resources.current("enemy", "stagger") == 100


def test_threshold_can_apply_state_and_reset_gauge():
    broken = StateDefinition("broken", 2)
    composition = break_composition(state_id="broken")
    battle = battle_fixture(composition=composition, state_defs=[broken])
    battle.battle_resources.change("enemy", "stagger", -90)
    result = battle.apply_gauge_impact(
        "stagger_break", "hero", "enemy", trigger="battle.hit",
        outcome_tags=("outcome.weak",), rng=random.Random(1),
    )
    assert result.thresholds[0].state_applied
    assert battle.member("enemy").subject.states.get("broken") is not None
    assert battle.battle_resources.current("enemy", "stagger") == 100


def test_threshold_can_shift_continuous_timeline():
    composition = break_composition(timeline_shift=7)
    battle = battle_fixture(composition=composition, scheduler=True)
    before = [x.ready_time for x in battle.scheduler.pending() if x.member_id == "enemy"][0]
    battle.battle_resources.change("enemy", "stagger", -90)
    battle.apply_gauge_impact(
        "stagger_break", "hero", "enemy", trigger="battle.hit",
        outcome_tags=("outcome.weak",),
    )
    after = [x.ready_time for x in battle.scheduler.pending() if x.member_id == "enemy"][0]
    assert after == before + 7


def test_threshold_emit_trigger_reuses_existing_resource_trigger_rules():
    composition = break_composition(emit_trigger="custom.break")
    hero = PartyMember("hero", "heroes", subject(), initiative=20)
    enemy = PartyMember("enemy", "enemies", subject(), initiative=10)
    from asteria.rpg import BattleResourceRule
    battle = BattleRuntime(
        [Party("heroes", [hero]), Party("enemies", [enemy])],
        AbilityRuntime(AbilityRegistry()),
        resource_definitions=[
            BattleResourceDefinition("stagger", minimum=0, maximum=100, start_mode="maximum"),
            BattleResourceDefinition(
                "guard", minimum=0, maximum=50, start_mode="minimum",
                rules=[BattleResourceRule("custom.break", 5)],
            ),
        ],
        gauge_composition_definitions=[composition],
    )
    battle.battle_resources.change("enemy", "stagger", -90)
    battle.apply_gauge_impact(
        "stagger_break", "hero", "enemy", trigger="battle.hit",
        outcome_tags=("outcome.weak",),
    )
    assert battle.battle_resources.current("enemy", "guard") == 5


def test_source_recipient_supports_combo_or_heat_gain_without_special_system():
    composition = GaugeCompositionDefinition(
        "combo_gain",
        impacts=[GaugeImpactRule("gain", "guard", "battle.hit", recipient="source", delta=4)],
    )
    battle = battle_fixture(composition=composition)
    battle.apply_gauge_impact("combo_gain", "hero", "enemy", trigger="battle.hit")
    assert battle.battle_resources.current("hero", "guard") == 50  # starts max, clamp proves recipient
    battle.battle_resources.change("hero", "guard", -20)
    battle.apply_gauge_impact("combo_gain", "hero", "enemy", trigger="battle.hit")
    assert battle.battle_resources.current("hero", "guard") == 34
    assert battle.battle_resources.current("enemy", "guard") == 50


def test_value_scaled_pressure_uses_resolved_value_magnitude():
    composition = GaugeCompositionDefinition(
        "poise",
        impacts=[GaugeImpactRule("damage_pressure", "stagger", "damage.applied", value_scale=-0.5)],
    )
    battle = battle_fixture(composition=composition)
    battle.apply_gauge_impact("poise", "hero", "enemy", trigger="damage.applied", value=30)
    assert battle.battle_resources.current("enemy", "stagger") == 85


def test_database_v17_owns_gauge_compositions_and_v16_remains_backward_readable():
    db = RpgDatabase()
    db.add_gauge_composition(break_composition())
    raw = db.to_data()
    assert raw["version"] == 23
    restored = RpgDatabase.from_data(raw)
    assert "stagger_break" in restored.gauge_compositions

    legacy = json.loads(json.dumps(raw))
    legacy["version"] = 16
    legacy.pop("gauge_compositions")
    restored_legacy = RpgDatabase.from_data(legacy)
    assert restored_legacy.gauge_compositions == {}


def test_many_compositions_and_rules_have_no_engine_cap():
    definitions = [
        GaugeCompositionDefinition(
            f"c{i}", impacts=[GaugeImpactRule(f"i{i}", "stagger", f"trigger.{i}", delta=-1)]
        )
        for i in range(256)
    ]
    runtime = BattleGaugeCompositionRuntime(definitions)
    assert len(runtime.definitions) == 256
