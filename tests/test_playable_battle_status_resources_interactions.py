from asteria.rpg import BattleAction
from asteria.validation import PlayableBattleMechanicsHarness, build_playable_mechanics_scenario

def test_status_duration_ticks_and_expires_with_source_preserved():
    h=PlayableBattleMechanicsHarness()
    h.apply_status("scorch")
    snap=h.status_snapshot("reference_enemy")
    assert snap[0][0]=="scorch"
    assert snap[0][1]==3
    assert snap[0][3]=="validation_hero"
    h.tick_turn_statuses("reference_enemy")
    assert h.status_snapshot("reference_enemy")[0][1]==2
    h.tick_turn_statuses("reference_enemy")
    assert h.status_snapshot("reference_enemy")[0][1]==1
    h.tick_turn_statuses("reference_enemy")
    assert h.status_snapshot("reference_enemy")==()

def test_periodic_status_applies_damage_each_tick_before_expiry():
    h=PlayableBattleMechanicsHarness()
    h.apply_status("scorch")
    enemy=h.battle.member("reference_enemy")
    before=enemy.subject.resources.current("vitality")
    h.tick_turn_statuses("reference_enemy")
    assert enemy.subject.resources.current("vitality")==before-5

def test_buff_modifier_is_active_then_removed_on_expiry():
    h=PlayableBattleMechanicsHarness()
    h.apply_status("focus_up", target_id="validation_hero")
    actor=h.battle.member("validation_hero").subject
    assert actor.states.modifiers().evaluate("power", actor.stats.get("power"), tags=actor.tags) == actor.stats.get("power")+4
    h.tick_turn_statuses("validation_hero")
    assert h.status_snapshot("validation_hero")[0][1]==1
    h.tick_turn_statuses("validation_hero")
    assert h.status_snapshot("validation_hero")==()

def test_tag_driven_weakness_like_interaction_is_explainable_and_non_mutating():
    h=PlayableBattleMechanicsHarness()
    enemy=h.battle.member("reference_enemy")
    before=enemy.subject.resources.current("vitality")
    result=h.resolve_flame_interaction(20)
    assert result.value.resolved_value==30
    assert result.outcome_tags==("interaction.exposed",)
    assert result.value.matched_rules==("flame_fragility",)
    assert enemy.subject.resources.current("vitality")==before

def test_break_like_gauge_uses_generic_resource_outcome_and_state_mechanisms():
    h=PlayableBattleMechanicsHarness()
    assert h.battle.battle_resources.current("reference_enemy","resolve_guard")==4
    first=h.apply_resolve_pressure()
    assert h.battle.battle_resources.current("reference_enemy","resolve_guard")==2
    assert first.thresholds==()
    second=h.apply_resolve_pressure()
    assert h.battle.battle_resources.current("reference_enemy","resolve_guard")==0
    assert second.thresholds[0].state_applied
    assert h.status_snapshot("reference_enemy")[0][0]=="staggered"
    assert not h.battle.can_act("reference_enemy") or not h.battle.battle_states.ability_availability(
        h.battle.member("reference_enemy").subject, ()
    ).allowed

def test_multihit_sequence_uses_same_canonical_ability_twice():
    h=PlayableBattleMechanicsHarness()
    before=h.battle.member("reference_enemy").subject.resources.current("vitality")
    plan, results, failures=h.double_flame()
    after=h.battle.member("reference_enemy").subject.resources.current("vitality")
    assert len(results)==2
    assert failures==()
    assert before-after==60  # 2 hits x 20 x 1.5 flame_fragility (F-3: interaction multipliers reach damage)

def test_heal_and_revive_use_generic_resource_and_lifecycle_paths():
    h=PlayableBattleMechanicsHarness()
    actor=h.battle.member("validation_hero")
    actor.subject.resources.change("vitality",-40)
    before=actor.subject.resources.current("vitality")
    h.heal_player()
    assert actor.subject.resources.current("vitality")==before+24
    h.battle.incapacitate("validation_hero")
    assert not h.battle.combatants.state("validation_hero").active
    h.revive_player()
    assert h.battle.combatants.state("validation_hero").active

def test_custom_resource_names_remain_generic():
    s=build_playable_mechanics_scenario()
    assert s.battle.battle_resources.current("reference_enemy","resolve_guard")==4
    assert "hp" not in s.battle.member("validation_hero").subject.resources.to_data()["values"]
