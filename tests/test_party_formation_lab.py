import pytest

from asteria.validation import PartyFormationLab

def test_default_lab_has_12_member_roster_4_active_8_reserve():
    lab=PartyFormationLab()
    assert len(lab.roster_ids())==12
    assert len(lab.active_ids())==4
    assert len(lab.reserve_ids())==8

def test_default_active_members_have_canonical_formation_slots():
    lab=PartyFormationLab()
    snap=lab.snapshot()
    assert len(snap.placements)==4
    assert dict(snap.placements)=={
        "party_00":"slot_0",
        "party_01":"slot_1",
        "party_02":"slot_2",
        "party_03":"slot_3",
    }

def test_swap_active_with_reserve_preserves_roster_size_and_slot():
    lab=PartyFormationLab()
    result=lab.swap_active_with_reserve("party_01","party_08")
    assert result==("party_01","party_08","slot_1")
    assert "party_08" in lab.active_ids()
    assert "party_01" in lab.reserve_ids()
    assert lab.formation.slot_id_for("party_08")=="slot_1"
    assert len(lab.roster_ids())==12

def test_invalid_swap_roles_are_rejected():
    lab=PartyFormationLab()
    with pytest.raises(ValueError,match="outgoing"):
        lab.swap_active_with_reserve("party_09","party_08")
    with pytest.raises(ValueError,match="incoming"):
        lab.swap_active_with_reserve("party_00","party_01")

def test_move_active_member_swaps_occupied_formation_slots():
    lab=PartyFormationLab()
    lab.move("party_00","slot_2")
    assert lab.formation.slot_id_for("party_00")=="slot_2"
    assert lab.formation.slot_id_for("party_02")=="slot_0"

def test_reserve_member_cannot_be_placed_directly():
    lab=PartyFormationLab()
    with pytest.raises(ValueError,match="only active"):
        lab.move("party_08","slot_0")

def test_set_active_members_is_project_policy_and_rebuilds_formation():
    lab=PartyFormationLab()
    active=("party_02","party_05","party_07")
    assert lab.set_active_members(active)==active
    assert lab.active_ids()==active
    assert len(lab.reserve_ids())==9
    assert lab.formation.slot_id_for("party_02")=="slot_0"
    assert lab.formation.slot_id_for("party_05")=="slot_1"
    assert lab.formation.slot_id_for("party_07")=="slot_2"

def test_project_active_capacity_is_not_engine_fixed_to_four():
    lab=PartyFormationLab(active_capacity=6)
    assert len(lab.active_ids())==6
    assert len(lab.reserve_ids())==6
    assert len(lab.formation.placements())==6

def test_active_capacity_rejects_only_controller_policy_overflow():
    lab=PartyFormationLab(active_capacity=3)
    with pytest.raises(ValueError,match="active_capacity"):
        lab.set_active_members(("party_00","party_01","party_02","party_03"))
    assert len(lab.roster_ids())==12

def test_roster_reorder_does_not_change_active_members():
    lab=PartyFormationLab()
    original_active=lab.active_ids()
    order=tuple(reversed(lab.roster_ids()))
    assert lab.reorder_roster(order)==order
    assert lab.active_ids()==original_active
    assert lab.reserve_ids()==tuple(x for x in order if x not in original_active)

def test_remove_reserve_member_updates_canonical_party():
    lab=PartyFormationLab()
    removed=lab.remove_member("party_11")
    assert removed.member_id=="party_11"
    assert "party_11" not in lab.roster_ids()
    assert "party_11" not in lab.reserve_ids()

def test_remove_active_member_clears_formation_slot():
    lab=PartyFormationLab()
    removed=lab.remove_member("party_02")
    assert removed.member_id=="party_02"
    assert "party_02" not in lab.active_ids()
    assert lab.formation.slot_id_for("party_02") is None

def test_snapshot_reports_operated_party_state():
    lab=PartyFormationLab()
    lab.swap_active_with_reserve("party_03","party_10")
    lab.move("party_10","slot_0")
    snap=lab.snapshot()
    assert "party_10" in snap.active_ids
    assert "party_03" in snap.reserve_ids
    placements=dict(snap.placements)
    assert placements["party_10"]=="slot_0"
    assert placements["party_00"]=="slot_3"
