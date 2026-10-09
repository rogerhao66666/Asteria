import copy

import pytest

from asteria.gameplay import ModifierOperation, StatModifier
from asteria.rpg import (
    AbilityEvolutionRule,
    ActorAbilityState,
    ActorDefinition,
    ClassAssignment,
    ClassDefinition,
    PassiveDefinition,
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RpgActorSnapshot,
    RpgDatabase,
)


def make_db():
    db = RpgDatabase()
    db.add_class(ClassDefinition("warrior", granted_abilities=["power_strike"]))
    db.add_class(ClassDefinition("scholar", granted_abilities=["fireball"]))
    db.add_progression_track(ProgressionTrackDefinition("scholar_rank", milestones=[
        ProgressionMilestone(1, 0),
        ProgressionMilestone(2, 10, granted_abilities=["focus"]),
        ProgressionMilestone(3, 20),
    ]))
    db.add_actor(ActorDefinition("aria", class_assignments=[
        ClassAssignment("warrior", assignment_id="job.warrior"),
        ClassAssignment("scholar", assignment_id="job.scholar", progression_track_ids=["scholar_rank"]),
    ], abilities=["basic_attack"], base_stats={"attack": 10}))
    db.add_passive(PassiveDefinition(
        "battle_instinct", "Battle Instinct",
        tags=["passive.counter_ready"],
        modifiers=[StatModifier("passive.attack", "attack", ModifierOperation.ADD, 5)],
        granted_abilities=["counter_stance"],
    ))
    db.add_ability_evolution(AbilityEvolutionRule(
        "fireball_to_firestorm", "fireball", "firestorm",
        progression_track_id="scholar_rank", minimum_rank=3, priority=10,
    ))
    return db


def test_learned_skill_persists_independently_from_job_grants():
    db = make_db()
    actor = db.build_actor("aria")
    actor.ability_state.learn("heal")
    assert "heal" in actor.effective_abilities()
    # Rebuild a definition without Scholar: learned runtime skill remains when state is restored.
    snap = actor.snapshot()
    changed = ActorDefinition("aria", class_assignments=[ClassAssignment("warrior")], abilities=["basic_attack"])
    runtime = type(actor)(changed, class_definitions={"warrior": db.classes["warrior"]})
    runtime.restore(snap)
    assert "heal" in runtime.effective_abilities()
    assert "fireball" not in runtime.effective_abilities()


def test_passive_loadout_contributes_tags_stats_and_granted_abilities():
    db = make_db()
    runtime = db.build_actor("aria")
    runtime.ability_state.equip_passive("battle_instinct", capacity=1)
    assert runtime.effective_stats(passives=db.passives).get("attack") == 15
    assert runtime.effective_tags(passives=db.passives).contains("passive.counter_ready")
    resolution = runtime.resolve_abilities(passives=db.passives)
    assert "counter_stance" in resolution.abilities
    assert resolution.sources_for("counter_stance")[0].source_kind == "passive"
    with pytest.raises(ValueError, match="full"):
        runtime.ability_state.equip_passive("other", capacity=1)


def test_ability_provenance_distinguishes_intrinsic_class_progression_and_learned():
    db = make_db()
    runtime = db.build_actor("aria")
    runtime.ability_state.learn("heal")
    progression = ProgressionRuntime(db.progression_tracks.values(), totals={"scholar_rank": 10})
    result = runtime.resolve_abilities(progression=progression)
    assert result.sources_for("basic_attack")[0].source_kind == "intrinsic"
    assert {x.source_kind for x in result.sources_for("fireball")} == {"class"}
    assert {x.source_kind for x in result.sources_for("focus")} == {"progression"}
    assert {x.source_kind for x in result.sources_for("heal")} == {"learned"}


def test_evolution_rule_upgrades_skill_when_requirement_is_met():
    db = make_db()
    runtime = db.build_actor("aria")
    low = ProgressionRuntime(db.progression_tracks.values(), totals={"scholar_rank": 10})
    high = ProgressionRuntime(db.progression_tracks.values(), totals={"scholar_rank": 20})
    assert "fireball" in runtime.effective_abilities(progression=low, evolution_rules=db.ability_evolutions.values())
    result = runtime.resolve_abilities(progression=high, evolution_rules=db.ability_evolutions.values())
    assert "fireball" not in result.abilities
    assert "firestorm" in result.abilities
    assert result.sources_for("firestorm")[0].source_kind == "evolution"


def test_selected_evolution_supports_branch_choice_deterministically():
    db = make_db()
    db.add_ability_evolution(AbilityEvolutionRule("fireball_to_inferno", "fireball", "inferno", progression_track_id="scholar_rank", minimum_rank=3, priority=10))
    runtime = db.build_actor("aria")
    runtime.ability_state.select_evolution("fireball", "fireball_to_inferno")
    high = ProgressionRuntime(db.progression_tracks.values(), totals={"scholar_rank": 20})
    assert runtime.effective_abilities(progression=high, evolution_rules=db.ability_evolutions.values())[-1] == "inferno"


def test_actor_ability_state_and_snapshot_roundtrip():
    state = ActorAbilityState(learned_abilities=["heal"], active_passives=["battle_instinct"], selected_evolutions={"fireball": "fireball_to_firestorm"})
    loaded = ActorAbilityState.from_data(copy.deepcopy(state.to_data()))
    assert loaded.learned_abilities == ("heal",)
    db = make_db()
    runtime = db.build_actor("aria")
    runtime.ability_state = loaded
    snap = RpgActorSnapshot.from_data(runtime.snapshot().to_data())
    restored = db.build_actor("aria").restore(snap)
    assert restored.ability_state.active_passives == ("battle_instinct",)


def test_rpg_database_v6_persists_passives_and_evolutions_and_v5_remains_readable():
    db = make_db()
    raw = db.to_data()
    assert raw["version"] == 24
    loaded = RpgDatabase.from_data(copy.deepcopy(raw))
    assert "battle_instinct" in loaded.passives
    assert "fireball_to_firestorm" in loaded.ability_evolutions
    old = copy.deepcopy(raw)
    old["version"] = 5
    del old["passives"]
    del old["ability_evolutions"]
    loaded_old = RpgDatabase.from_data(old)
    assert loaded_old.passives == {}
    assert loaded_old.ability_evolutions == {}
