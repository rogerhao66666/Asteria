import pytest

from asteria.validation import EquipmentLab

def test_lab_starts_with_clean_loadout():
    lab=EquipmentLab()
    snap=lab.snapshot()
    assert dict(snap.equipped)=={"accessory":(),"main_hand":()}
    assert "flame_slash" not in snap.abilities

def test_equip_weapon_changes_resolved_build():
    lab=EquipmentLab()
    before=lab.resolve()
    before_power=before.stats.get("power")
    lab.equip("main_hand","ember_blade:lab")
    after=lab.resolve()
    assert "flame_slash" in after.abilities
    assert after.stats.get("power")==before_power+6

def test_unequip_weapon_reverses_contribution():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    assert "flame_slash" in lab.resolve().abilities
    removed=lab.unequip("main_hand")
    assert removed.instance_id=="ember_blade:lab"
    assert "flame_slash" not in lab.resolve().abilities

def test_multiple_weapons_can_contribute_without_engine_weapon_enum():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    lab.equip("main_hand","frost_blade:lab")
    build=lab.resolve()
    assert "flame_slash" in build.abilities
    assert "ice_arc" in build.abilities
    assert len(lab.scenario.loadout.equipped("main_hand"))==2

def test_accessories_use_same_generic_loadout_mechanism():
    lab=EquipmentLab()
    before=lab.resolve().stats.get("focus")
    lab.equip("accessory","focus_charm:lab")
    build=lab.resolve()
    assert "focus_step" in build.abilities
    assert build.stats.get("focus")==before+2

def test_attachment_adds_ability_to_equipped_item():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    assert "venom_edge" not in lab.resolve().abilities
    lab.attach("ember_blade:lab","rune","venom_rune")
    assert "venom_edge" in lab.resolve().abilities

def test_detach_reverses_attachment_contribution():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    lab.attach("ember_blade:lab","rune","echo_rune")
    assert "echo_edge" in lab.resolve().abilities
    detached=lab.detach("ember_blade:lab","rune")
    assert detached.attachment_id=="echo_rune"
    assert "echo_edge" not in lab.resolve().abilities

def test_growth_requires_authored_progress_before_unlock():
    lab=EquipmentLab()
    item=lab.instances["ember_blade:lab"]
    preview=item.growth.preview_unlock("tempered")
    assert not preview.allowed
    with pytest.raises(ValueError):
        lab.unlock_growth("ember_blade:lab","tempered")

def test_growth_unlock_changes_resolved_ability_and_capability():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    unlocked=lab.add_growth_progress("ember_blade:lab","weapon_xp",10)
    assert ("tempered",1) in unlocked
    build=lab.resolve()
    assert "tempered_arc" in build.abilities
    assert "capability.weapon.tempered" in build.capabilities

def test_growth_bonus_changes_stat_after_unlock():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    before=lab.resolve().stats.get("power")
    unlocked=lab.add_growth_progress("ember_blade:lab","weapon_xp",10)
    assert ("tempered",1) in unlocked
    assert lab.resolve().stats.get("power")==before+4

def test_slot_capacity_is_enforced_canonically():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    lab.equip("main_hand","frost_blade:lab")
    # A third instance authored for the same generic slot exceeds capacity.
    from asteria.rpg import EquippedItem
    lab.instances["frost_blade:02"]=EquippedItem(
        lab.equipment_catalog["frost_blade"],instance_id="frost_blade:02"
    )
    with pytest.raises(ValueError,match="slot is full"):
        lab.equip("main_hand","frost_blade:02")

def test_same_instance_cannot_be_equipped_twice():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    with pytest.raises(ValueError,match="already equipped"):
        lab.equip("main_hand","ember_blade:lab")

def test_snapshot_reports_operated_equipment_state():
    lab=EquipmentLab()
    lab.equip("main_hand","ember_blade:lab")
    lab.equip("accessory","echo_charm:lab")
    lab.attach("ember_blade:lab","rune","venom_rune")
    unlocked=lab.add_growth_progress("ember_blade:lab","weapon_xp",10)
    assert ("tempered",1) in unlocked
    snap=lab.snapshot()
    assert dict(snap.equipped)["main_hand"]==("ember_blade:lab",)
    assert ("rune","venom_rune") in dict(snap.attachments)["ember_blade:lab"]
    assert ("tempered",1) in dict(snap.growth_ranks)["ember_blade:lab"]
    assert "tempered_arc" in snap.abilities
