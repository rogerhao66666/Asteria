import pytest

from asteria.rpg import BattleAction
from asteria.validation import PlayableBattleSummonHarness, build_playable_summon_scenario


def test_player_summon_registers_owner_and_generation():
    h = PlayableBattleSummonHarness()
    h.summon_player_spirit()
    state = h.lifecycle("spirit_echo")
    assert state.present and state.active
    assert state.summon_owner_id == "validation_hero"
    assert state.summon_generation == 1


def test_boss_add_uses_same_summon_lifecycle_mechanism():
    h = PlayableBattleSummonHarness()
    h.summon_boss_add()
    state = h.lifecycle("ember_add")
    assert state.present and state.active
    assert state.summon_owner_id == "reference_boss"
    assert state.summon_generation == 1


def test_player_summon_action_uses_same_canonical_battle_action():
    h = PlayableBattleSummonHarness()
    h.summon_player_spirit()
    boss = h.battle.member("reference_boss")
    before = boss.subject.resources.current("vitality")
    h.execute("spirit_echo", "spirit_bolt", "reference_boss")
    assert boss.subject.resources.current("vitality") == before - 16


def test_boss_add_action_uses_same_canonical_battle_action():
    h = PlayableBattleSummonHarness()
    h.summon_boss_add()
    hero = h.battle.member("validation_hero")
    before = hero.subject.resources.current("vitality")
    h.execute("ember_add", "add_bite", "validation_hero")
    assert hero.subject.resources.current("vitality") == before - 10


def test_temporary_combatant_exit_removes_from_active_battle_and_pending_turns():
    h = PlayableBattleSummonHarness()
    h.summon_player_spirit()
    assert "spirit_echo" in h.active_member_ids()
    h.remove("spirit_echo")
    state = h.lifecycle("spirit_echo")
    assert not state.present
    assert "spirit_echo" not in h.active_member_ids()
    with pytest.raises(ValueError):
        h.execute("spirit_echo", "spirit_bolt", "reference_boss")


def test_player_summon_and_multiple_boss_adds_can_coexist():
    h = PlayableBattleSummonHarness()
    h.summon_player_spirit()
    h.summon_boss_add(member_id="ember_add")
    h.summon_boss_add(member_id="ash_add")
    active = set(h.active_member_ids())
    assert {"validation_hero", "reference_boss", "spirit_echo", "ember_add", "ash_add"} <= active
    assert h.lifecycle("spirit_echo").summon_owner_id == "validation_hero"
    assert h.lifecycle("ember_add").summon_owner_id == "reference_boss"
    assert h.lifecycle("ash_add").summon_owner_id == "reference_boss"


def test_duplicate_summon_member_id_is_rejected():
    h = PlayableBattleSummonHarness()
    h.summon_boss_add(member_id="ember_add")
    with pytest.raises(ValueError, match="duplicate battle member id"):
        h.summon_boss_add(member_id="ember_add")


def test_unknown_summon_owner_is_rejected_by_canonical_runtime():
    h = PlayableBattleSummonHarness()
    from asteria.rpg import PartyMember

    member = PartyMember(
        "orphan",
        "side.alpha",
        h.battle.member("validation_hero").subject,
        ability_ids=("hero_strike",),
        initiative=1,
    )
    with pytest.raises(ValueError, match="unknown summon owner"):
        h.battle.summon(member, owner_id="missing.owner")


def test_snapshot_restore_preserves_summon_and_add_topology():
    h = PlayableBattleSummonHarness()
    h.summon_player_spirit()
    h.summon_boss_add()
    snap = h.snapshot()

    fresh = PlayableBattleSummonHarness(build_playable_summon_scenario())
    fresh.battle.restore_snapshot(snap)
    assert fresh.lifecycle("spirit_echo").summon_owner_id == "validation_hero"
    assert fresh.lifecycle("ember_add").summon_owner_id == "reference_boss"
    assert {"spirit_echo", "ember_add"} <= set(fresh.active_member_ids())


def test_removed_summon_stays_in_topology_but_is_not_present():
    h = PlayableBattleSummonHarness()
    h.summon_player_spirit()
    h.remove("spirit_echo")
    snap = h.snapshot()
    fresh = PlayableBattleSummonHarness(build_playable_summon_scenario())
    fresh.battle.restore_snapshot(snap)
    assert "spirit_echo" in fresh.battle.members
    assert not fresh.lifecycle("spirit_echo").present
