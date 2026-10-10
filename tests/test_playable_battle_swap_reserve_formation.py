import pytest

from asteria.validation import PlayableBattlePartyHarness, build_playable_party_scenario


def test_large_party_supports_four_active_and_eight_reserve_without_engine_cap():
    h = PlayableBattlePartyHarness()
    assert len(h.active_ids()) == 4
    assert len(h.reserve_ids()) == 8
    assert len(h.battle.parties["side.alpha"].members) == 12


def test_initial_formation_places_only_active_members():
    h = PlayableBattlePartyHarness()
    placements = dict(h.formation_snapshot())
    assert set(placements) == {"party_00", "party_01", "party_02", "party_03"}
    assert set(placements.values()) == {"slot_0", "slot_1", "slot_2", "slot_3"}


def test_swap_moves_reserve_into_same_formation_slot():
    h = PlayableBattlePartyHarness()
    result = h.swap("party_01", "party_08")
    assert result == ("party_01", "party_08", "slot_1")
    placements = dict(h.formation_snapshot())
    assert placements["party_08"] == "slot_1"
    assert "party_01" not in placements


def test_swap_updates_participation_without_mutating_party_membership_order():
    h = PlayableBattlePartyHarness()
    before = tuple(m.member_id for m in h.battle.parties["side.alpha"].members)
    h.swap("party_00", "party_09")
    after = tuple(m.member_id for m in h.battle.parties["side.alpha"].members)
    assert after == before
    assert "party_09" in h.active_ids()
    assert "party_00" in h.reserve_ids()


def test_incoming_member_can_execute_ordinary_battle_action():
    h = PlayableBattlePartyHarness()
    h.swap("party_02", "party_10")
    enemy = h.battle.member("reference_enemy")
    before = enemy.subject.resources.current("vitality")
    h.execute_member_action("party_10")
    assert enemy.subject.resources.current("vitality") == before - 20


def test_outgoing_reserve_member_cannot_act():
    h = PlayableBattlePartyHarness()
    h.swap("party_03", "party_11")
    with pytest.raises(ValueError, match="actor cannot act"):
        h.execute_member_action("party_03")


def test_swap_rejects_invalid_active_and_reserve_roles():
    h = PlayableBattlePartyHarness()
    with pytest.raises(ValueError, match="outgoing member must be active"):
        h.swap("party_08", "party_09")
    with pytest.raises(ValueError, match="incoming member must be reserve"):
        h.swap("party_00", "party_01")


def test_repeated_swaps_reuse_generic_slots_and_preserve_four_active_members():
    h = PlayableBattlePartyHarness()
    h.swap("party_00", "party_04")
    h.swap("party_01", "party_05")
    h.swap("party_04", "party_06")
    assert len(h.active_ids()) == 4
    assert set(h.active_ids()) == {"party_02", "party_03", "party_05", "party_06"}
    assert len(h.formation_snapshot()) == 4


def test_next_round_turn_queue_can_pick_incoming_and_skips_reserves():
    h = PlayableBattlePartyHarness()
    h.swap("party_00", "party_11")
    h.battle.start_next_round()
    pending_ids = tuple(x.member_id for x in h.battle.turn_queue.pending())
    # Queue source still contains the complete party by design; next_actor filters inactive reserves.
    seen = []
    for _ in range(20):
        actor = h.battle.next_actor()
        if actor is None:
            break
        seen.append(actor.member_id)
        h.battle.advance_turn()
    assert "party_11" in seen
    assert "party_00" not in seen
    assert all(mid not in seen for mid in h.reserve_ids())


def test_snapshot_restore_preserves_swap_lifecycle_and_formation():
    h = PlayableBattlePartyHarness()
    h.swap("party_01", "party_07")
    snap = h.snapshot()

    fresh = PlayableBattlePartyHarness(build_playable_party_scenario())
    fresh.battle.restore_snapshot(snap)
    assert "party_07" in fresh.active_ids()
    assert "party_01" in fresh.reserve_ids()
    assert dict(fresh.formation_snapshot())["party_07"] == "slot_1"


def test_formation_slot_tags_are_project_metadata_not_engine_front_back_semantics():
    h = PlayableBattlePartyHarness()
    slot = h.battle.formations["side.alpha"].definition.slot("slot_2")
    assert slot.tags == ("lane.2",)
