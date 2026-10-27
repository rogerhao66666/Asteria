"""New gear asks before it is worn (InventoryRules.equip_offer): never, when a place is free, or
always (offering a swap). It waits in the equipment bag until the player answers."""

import dataclasses
import sys
from pathlib import Path

import pytest

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"
sys.path.insert(0, str(DEMO))

import run_trial_smoke as smoke  # noqa: E402

from asteria.rpg.items import InventoryRules  # noqa: E402
from asteria.runtime.game_session import GameSessionError  # noqa: E402

HERO = smoke.HERO


def _game(mode):
    _project, game = smoke.load()
    inventory = game.save.rpg_state.inventory
    inventory.rules = dataclasses.replace(inventory.rules, equip_offer=mode)
    game.save.rpg_state.equipment_bag.clear()  # D98: the demo starts with spare gear
    return game


def _weapons(game):
    """The main and the sub weapon (D92: one slot each)."""
    loadout = game.save.rpg_state.loadouts[HERO]
    worn = loadout.equipped("weapon") + loadout.equipped("sub_weapon")
    return [w.equipment.equipment_id for w in worn]


def test_never_asks_and_the_gear_waits_in_the_bag():
    game = _game("never")
    (axe,) = game.gain_equipment("w_axe")
    assert not game.equip_offers and axe in game.save.rpg_state.equipment_bag


def test_a_free_hand_is_offered_the_new_weapon():
    game = _game("empty_slot")
    assert _weapons(game) == ["w_sunbrand"]  # the sub-weapon hand is free
    game.gain_equipment("w_dagger")
    (offer,) = game.equip_offers
    assert offer.actor_id == HERO and offer.slot_id == "sub_weapon" and not offer.replaces
    game.answer_equip_offer(True)
    assert _weapons(game) == ["w_sunbrand", "w_dagger"] and not game.equip_offers
    bag = game.save.rpg_state.equipment_bag
    assert not any(g.equipment.equipment_id == "w_dagger" for g in bag)
    game.gain_equipment("w_spear")  # both hands full: only the Brave's carried slot is free
    (offer,) = game.equip_offers
    assert offer.slot_id == "arsenal"
    game.answer_equip_offer(False)
    with pytest.raises(GameSessionError):
        game.answer_equip_offer(True)


def test_keeping_it_leaves_the_gear_in_the_bag():
    game = _game("empty_slot")
    game.gain_equipment("w_bow")
    game.answer_equip_offer(False)
    assert _weapons(game) == ["w_sunbrand"]
    assert any(g.equipment.equipment_id == "w_bow" for g in game.save.rpg_state.equipment_bag)


def test_always_offers_a_swap_when_the_places_are_full():
    game = _game("always")
    game.gain_equipment("w_dagger")
    game.answer_equip_offer(True)  # the free hand first
    game.gain_equipment("w_spear")  # two-handed: no hand is free for it
    (offer,) = game.equip_offers
    assert offer.replaces.startswith("w_sunbrand")  # the main weapon would go
    game.answer_equip_offer(True)
    assert _weapons(game) == ["w_spear"]  # and the dagger, in the spear's way
    bag = {g.equipment.equipment_id for g in game.save.rpg_state.equipment_bag}
    assert {"w_sunbrand", "w_dagger"} <= bag


def test_the_rule_is_project_data():
    rules = InventoryRules("bag", equip_offer="empty_slot")
    assert InventoryRules.from_data(rules.to_data()).equip_offer == "empty_slot"
    assert "equip_offer" not in InventoryRules("bag").to_data()  # left out at its default
    with pytest.raises(ValueError):
        InventoryRules("bag", equip_offer="sometimes")
