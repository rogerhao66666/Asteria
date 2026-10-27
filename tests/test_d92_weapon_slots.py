"""D92: main / sub / special weapon slots, carried weapons swapped in battle, two-handed gear."""

import sys
from collections import Counter
from pathlib import Path

import pytest

from asteria.gameplay.modifiers import StatModifier
from asteria.presentation.menu_layout import MenuSlotPlace
from asteria.rpg.items import (
    EquipmentDefinition,
    EquipmentLoadout,
    EquipmentSlotDefinition,
    EquippedItem,
    InventoryRules,
)

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _piece(equipment_id, slot="weapon", tags=("weapon",), power=10.0, blocks=()):
    definition = EquipmentDefinition(
        equipment_id,
        slot=slot,
        tags=tags,
        modifiers=(StatModifier("p", "power", "add", power),),
        granted_abilities=(f"attack_{equipment_id}",),
        blocks_slots=blocks,
    )
    return EquippedItem(definition, instance_id=f"{equipment_id}:1")


def _loadout():
    return EquipmentLoadout(
        (
            EquipmentSlotDefinition("weapon"),
            EquipmentSlotDefinition("sub_weapon", accepted_tags=("weapon",)),
            EquipmentSlotDefinition(
                "arsenal",
                accepted_tags=("weapon",),
                capacity=None,
                stowed=True,
                required_capabilities=("capability.carry_weapons",),
            ),
        )
    )


def test_a_slot_definition_round_trips_and_writes_only_what_is_set():
    plain = EquipmentSlotDefinition("weapon")
    assert plain.to_data() == {"slot_id": "weapon", "accepted_tags": [], "capacity": 1}
    carried = EquipmentSlotDefinition(
        "arsenal", capacity=None, stowed=True, required_capabilities=("Capability.Carry",),
        display_name="Carried", order=9, description="Waits to be swapped in.",
    )  # fmt: skip
    assert EquipmentSlotDefinition.from_data(carried.to_data()) == carried
    assert carried.required_capabilities == ("capability.carry",)
    bow = _piece("bow", blocks=("sub_weapon",))
    assert EquipmentDefinition.from_data(bow.equipment.to_data()).blocks_slots == ("sub_weapon",)
    assert "blocks_slots" not in _piece("sword").equipment.to_data()
    rules = InventoryRules("bag", battle_swap="free", slot_conflict="refuse")
    assert InventoryRules.from_data(rules.to_data()) == rules
    assert "battle_swap" not in InventoryRules("bag").to_data()
    with pytest.raises(ValueError):
        InventoryRules("bag", battle_swap="sometimes")


def test_carried_pieces_give_nothing_until_worn():
    loadout = _loadout()
    sword, dagger, axe = _piece("sword"), _piece("dagger", power=4.0), _piece("axe", power=30.0)
    carry = ("capability.carry_weapons",)
    loadout.equip("weapon", sword)
    loadout.equip("sub_weapon", dagger)
    loadout.equip("arsenal", axe, capabilities=carry)
    assert loadout.carried() == (axe,)
    assert {x.instance_id for x in loadout.working()} == {"sword:1", "dagger:1"}
    total = sum(m.value for m in loadout.modifier_set().modifiers())
    assert total == 14.0  # the sword and the dagger (main and sub), not the carried axe


def test_a_slot_can_ask_for_a_capability():
    loadout = _loadout()
    refused = loadout.check_equip("arsenal", _piece("axe"), capabilities=())
    assert not refused.allowed and "capability.carry_weapons" in refused.reasons[0]


def test_a_two_handed_piece_needs_the_sub_slot_free_and_is_no_sub_weapon():
    loadout = _loadout()
    bow = _piece("bow", blocks=("sub_weapon",))
    dagger = _piece("dagger")
    loadout.equip("sub_weapon", dagger)
    assert loadout.conflicts("weapon", bow) == [("sub_weapon", dagger)]
    assert not loadout.check_equip("weapon", bow).allowed
    assert not loadout.slot("sub_weapon").takes(bow.equipment)  # never the sub weapon
    assert not loadout.check_equip("sub_weapon", _piece("bow2", blocks=("sub_weapon",))).allowed
    assert loadout.slot("arsenal").takes(bow.equipment)  # carried, it is in nobody's way
    loadout.unequip("sub_weapon")
    loadout.equip("weapon", bow)
    assert loadout.conflicts("sub_weapon", dagger) == [("weapon", bow)]


def test_project_slots_replace_and_add_to_every_loadout():
    loadout = EquipmentLoadout((EquipmentSlotDefinition("weapon", capacity=2),))
    loadout.equip("weapon", _piece("sword"))
    loadout.sync_slots(
        (EquipmentSlotDefinition("weapon"), EquipmentSlotDefinition("special", order=3))
    )
    assert loadout.slot("weapon").capacity == 1
    assert loadout.slot_ids() == ("special", "weapon")
    assert loadout.equipped("weapon")[0].instance_id == "sword:1"  # kept


def test_a_doll_place_can_have_a_back_picture():
    place = MenuSlotPlace("arsenal", (0, 0, 40, 40), backdrop="ui/cell.png")
    assert MenuSlotPlace.from_data(place.to_data()) == place
    assert "backdrop" not in MenuSlotPlace("weapon", (0, 0, 8, 8)).to_data()


# -- the Full Verification demo -----------------------------------------------------------------
@pytest.fixture
def game():
    sys.path.insert(0, str(DEMO))
    import run_trial_smoke as smoke

    _project, game = smoke.load()
    smoke.prepare(game, Counter(), "brave")
    return game


def test_the_brave_carries_weapons_and_the_others_do_not(game):
    db = game.project.rpg_database
    assert [db.equipment_slots[s].display_name for s in ("special", "weapon", "sub_weapon")] == [
        "Special",
        "Main Weapon",
        "Sub Weapon",
    ]
    assert db.equipment["w_bow"].blocks_slots == ("sub_weapon",)
    assert "special" in db.equipment["w_demon_ring"].tags
    roger = game.save.rpg_state.loadouts["hero_01"]
    assert [p.equipment.equipment_id for p in roger.carried()] == [
        "w_bow", "w_axe", "w_book_of_prayers", "w_brawler_gloves",
    ]  # fmt: skip
    assert game.swap_options("hero_01")
    assert game.swap_options("hero_02") == []
    assert game.slot_name("arsenal") == "Carried Weapons"


def test_swapping_in_battle_changes_the_fighter_at_once(game):
    from asteria.runtime.battle_commands import BattleCommands

    game.start_encounter("boss_room")
    commands = BattleCommands(game, style="root")
    roots = {r.action_id: r for r in commands.root_rows("hero_01")}
    assert roots["root:Swap"].cost_text == str(len(game.swap_options("hero_01")))
    member = game.battle.member("hero_01")
    power = member.subject.stats.get("power")
    health = member.subject.resources.current(game.rules.knockout_resource_id)
    commands.mode, commands.category, commands.cursor = "command", "Swap", 0
    row = commands.rows("hero_01")[0]
    assert row.action_id == "swap:w_bow:hero_01:weapon" and row.cost_text == "Main Weapon"
    assert commands.press("confirm", "hero_01") is True  # uses the turn (battle_swap "turn")
    loadout = game.save.rpg_state.loadouts["hero_01"]
    assert loadout.equipped("weapon")[0].equipment.equipment_id == "w_bow"
    assert "w_sunbrand" in {p.equipment.equipment_id for p in loadout.carried()}
    assert member.subject.stats.get("power") < power  # the bow hits softer than the Sunbrand
    assert member.subject.resources.current(game.rules.knockout_resource_id) == health
    assert "attack_bow" in member.ability_ids
    assert "attack_sword" in game.battle.blocked_abilities["hero_01"]
    assert member.subject.tags.contains("equip.bow")
    assert not member.subject.tags.contains("equip.sword")
    assert any(e.kind == "swapped" for e in game.drain_battle_log())


def test_a_free_swap_keeps_the_turn_and_off_hides_the_command(game):
    import dataclasses

    from asteria.runtime.battle_commands import BattleCommands

    inventory = game.save.rpg_state.inventory
    inventory.rules = dataclasses.replace(inventory.rules, battle_swap="free")
    game.start_encounter("boss_room")
    assert game.swap_carried("hero_01", "w_axe:hero_01", "weapon") is False
    inventory.rules = dataclasses.replace(inventory.rules, battle_swap="off")
    rows = BattleCommands(game, style="root").root_rows("hero_01")
    assert "root:Swap" not in {r.action_id for r in rows}


def test_a_two_handed_weapon_puts_the_sub_weapon_away_or_is_refused(game):
    import dataclasses

    loadout = game.save.rpg_state.loadouts["hero_01"]
    (dagger,) = game.gain_equipment("w_dagger")
    game.wear_from_bag("hero_01", dagger.instance_id, "sub_weapon")
    (spear,) = game.gain_equipment("w_dragoon_lance")
    inventory = game.save.rpg_state.inventory
    inventory.rules = dataclasses.replace(inventory.rules, slot_conflict="refuse")
    with pytest.raises(Exception, match="first"):
        game.wear_from_bag("hero_01", spear.instance_id, "weapon")
    assert loadout.equipped("sub_weapon") == (dagger,)
    inventory.rules = dataclasses.replace(inventory.rules, slot_conflict="take_off")
    game.wear_from_bag("hero_01", spear.instance_id, "weapon")
    assert loadout.equipped("sub_weapon") == ()
    assert dagger in game.save.rpg_state.equipment_bag
