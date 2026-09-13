import pytest

from asteria.rpg import BattleAction
from asteria.validation import PlayableBattleModeHarness, build_playable_mode_scenario

def test_normal_form_exposes_only_normal_action_surface():
    h=PlayableBattleModeHarness()
    assert h.current_form() is None
    assert h.action_surface()==("steady_strike",)

def test_guard_stance_replaces_stats_tags_initiative_and_actions():
    h=PlayableBattleModeHarness()
    h.enter_guard_stance()
    actor=h.actor
    assert h.current_form()=="guard_stance"
    assert actor.subject.stats.get("power")==20
    assert actor.subject.tags.contains("mode.defensive")
    assert actor.initiative==10
    assert h.action_surface()==("guard_counter",)

def test_overdrive_can_stack_on_top_of_stance_and_replaces_action_surface():
    h=PlayableBattleModeHarness()
    h.enter_guard_stance()
    h.enter_overdrive()
    actor=h.actor
    assert h.current_form()=="overdrive"
    assert actor.subject.stats.get("power")==38
    assert actor.subject.stats.get("speed")==18
    assert actor.subject.resources.current("momentum")==5
    assert actor.subject.tags.contains("mode.aggressive")
    assert h.action_surface()==("overdrive_arc",)

def test_nested_revert_returns_overdrive_to_guard_then_normal():
    h=PlayableBattleModeHarness()
    h.enter_guard_stance()
    h.enter_overdrive()
    h.revert_mode()
    assert h.current_form()=="guard_stance"
    assert h.action_surface()==("guard_counter",)
    h.revert_mode()
    assert h.current_form() is None
    assert h.action_surface()==("steady_strike",)

def test_current_form_action_executes_through_same_canonical_battle_action():
    h=PlayableBattleModeHarness()
    h.enter_overdrive()
    enemy=h.battle.member("reference_enemy")
    before=enemy.subject.resources.current("vitality")
    h.execute_current_action()
    assert enemy.subject.resources.current("vitality")==before-34

def test_inactive_form_action_is_rejected_by_canonical_ownership_validation():
    h=PlayableBattleModeHarness()
    h.enter_guard_stance()
    with pytest.raises(ValueError, match="does not know ability"):
        h.battle.execute(BattleAction(
            "validation_hero","steady_strike",("reference_enemy",)
        ))

def test_resources_are_explicitly_carried_across_authored_mode_transition():
    h=PlayableBattleModeHarness()
    h.actor.subject.resources.change("vitality",-37)
    before=h.actor.subject.resources.current("vitality")
    h.enter_guard_stance()
    assert h.actor.subject.resources.current("vitality")==before
    h.enter_overdrive()
    assert h.actor.subject.resources.current("vitality")==before

def test_snapshot_restore_preserves_nested_mode_stack_and_revert_capability():
    h=PlayableBattleModeHarness()
    h.enter_guard_stance()
    h.enter_overdrive()
    snap=h.snapshot()

    fresh=PlayableBattleModeHarness(build_playable_mode_scenario())
    fresh.battle.restore_snapshot(snap)
    assert fresh.current_form()=="overdrive"
    assert fresh.action_surface()==("overdrive_arc",)
    fresh.revert_mode()
    assert fresh.current_form()=="guard_stance"
    assert fresh.action_surface()==("guard_counter",)
    fresh.revert_mode()
    assert fresh.current_form() is None
    assert fresh.action_surface()==("steady_strike",)

def test_mode_system_uses_opaque_project_vocabulary_not_engine_taxonomy():
    h=PlayableBattleModeHarness()
    h.enter_guard_stance()
    assert h.current_form()=="guard_stance"
    assert "transform" not in h.action_surface()
    assert "stance" not in h.action_surface()
