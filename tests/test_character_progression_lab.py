import pytest

from asteria.validation import CharacterProgressionLab


def test_lab_starts_with_clean_allocations_and_primary_job():
    lab = CharacterProgressionLab()
    snap = lab.snapshot()
    assert snap.level_rank == 1
    assert snap.experience_total == 0
    assert snap.allocated_nodes == ()
    assert any(role == "primary" and class_id == "vanguard" for _, role, class_id in snap.class_assignments)


def test_award_experience_advances_canonical_progression_rank():
    lab = CharacterProgressionLab()
    result = lab.award_experience(120)
    assert result.old_rank == 1
    assert result.new_rank == 2
    assert lab.level == 2
    assert lab.experience == 120


def test_locked_job_cannot_be_equipped_until_project_unlocks_it():
    lab = CharacterProgressionLab()
    lab.clear_job("secondary")
    with pytest.raises(ValueError, match="job is locked"):
        lab.set_job("secondary", "alchemist")
    lab.unlock_job("alchemist")
    lab.set_job("secondary", "alchemist")
    assert any(x.role == "secondary" and x.class_id == "alchemist" for x in lab.scenario.actor.class_assignments)


def test_switching_primary_job_rebuilds_canonical_actor_contributions():
    lab = CharacterProgressionLab()
    lab.clear_job("secondary")
    lab.unlock_job("alchemist")
    before = lab.resolve()
    assert "power_strike" in before.abilities
    lab.set_job("primary", "alchemist")
    after = lab.resolve()
    assert "quick_mix" in after.abilities
    assert "power_strike" not in after.abilities


def test_multiclass_primary_secondary_both_contribute():
    lab = CharacterProgressionLab()
    lab.clear_job("secondary")
    lab.unlock_job("alchemist")
    lab.set_job("secondary", "alchemist")
    build = lab.resolve()
    assert "power_strike" in build.abilities
    assert "quick_mix" in build.abilities
    assert "capability.weapon.blade" in build.capabilities
    assert "capability.alchemy" in build.capabilities


def test_skill_point_allocation_changes_resolved_build():
    lab = CharacterProgressionLab()
    assert "double_strike" not in lab.resolve().abilities
    preview = lab.allocate_node("hero_mastery", "double_strike_node")
    assert preview.allowed
    build = lab.resolve()
    assert "double_strike" in build.abilities
    assert "capability.combo" in build.capabilities
    assert lab.scenario.allocations.balance("skill_point") == 2


def test_ability_point_allocation_changes_stats_and_resource_capacity():
    lab = CharacterProgressionLab()
    before = lab.resolve()
    before_focus = before.stats.get("focus")
    before_technique = before.resources.maximum("technique")
    lab.allocate_node("hero_mastery", "deep_reserve")
    after = lab.resolve()
    assert after.stats.get("focus") == before_focus + 2
    assert after.resources.maximum("technique") == before_technique + 10
    assert lab.scenario.allocations.balance("ability_point") == 1


def test_refund_node_reverses_progression_contribution():
    lab = CharacterProgressionLab()
    lab.allocate_node("hero_mastery", "double_strike_node")
    assert "double_strike" in lab.resolve().abilities
    refund = lab.refund_node("hero_mastery", "double_strike_node")
    assert refund["skill_point"] == 2
    assert "double_strike" not in lab.resolve().abilities
    assert lab.scenario.allocations.balance("skill_point") == 4


def test_passive_loadout_is_actually_operable():
    lab = CharacterProgressionLab()
    # Baseline reference content already knows/equips this passive; unequip first.
    lab.unequip_passive("counter_formula")
    assert "reactive_tonic" not in lab.resolve().abilities
    lab.equip_passive("counter_formula", capacity=1)
    build = lab.resolve()
    assert "reactive_tonic" in build.abilities
    assert lab.scenario.actor.ability_state.active_passives == ("counter_formula",)


def test_passive_capacity_is_enforced_by_canonical_ability_state():
    lab = CharacterProgressionLab()
    # Existing passive occupies the only slot.
    with pytest.raises(ValueError, match="passive loadout is full"):
        lab.scenario.actor.ability_state.equip_passive("another_passive", capacity=1)


def test_job_change_preserves_learned_ability_and_passive_state():
    lab = CharacterProgressionLab()
    assert "field_mix" in lab.scenario.actor.ability_state.learned_abilities
    assert "counter_formula" in lab.scenario.actor.ability_state.active_passives
    lab.clear_job("secondary")
    lab.unlock_job("alchemist")
    lab.set_job("primary", "alchemist")
    assert "field_mix" in lab.scenario.actor.ability_state.learned_abilities
    assert "counter_formula" in lab.scenario.actor.ability_state.active_passives


def test_snapshot_reports_real_operated_state():
    lab = CharacterProgressionLab()
    lab.award_experience(300)
    lab.allocate_node("hero_mastery", "double_strike_node")
    lab.unlock_job("alchemist")
    snap = lab.snapshot()
    assert snap.level_rank == 3
    assert ("hero_mastery", "double_strike_node", 1) in snap.allocated_nodes
    assert "alchemist" in snap.unlocked_jobs
    assert "double_strike" in snap.resolved_abilities
