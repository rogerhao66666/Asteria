"""Disassembly, job points and New Game Plus rules (pure data and carry-over logic)."""

import random
from types import SimpleNamespace

import pytest

from asteria.rpg.disassembly import (
    DisassemblyRecipe,
    DisassemblyYield,
    disassemble,
)
from asteria.rpg.items import Inventory
from asteria.rpg.job_points import JobPointRules
from asteria.rpg.new_game_plus import NewGamePlusRules, carry_over


def _recipe(**extra):
    return DisassemblyRecipe(
        "sword",
        (DisassemblyYield("iron", 1, 3), DisassemblyYield("gem", 1, 1, chance=0.0)),
        **extra,
    )


def test_disassembly_takes_the_item_and_gives_the_rolled_materials():
    bag = Inventory()
    bag.add("sword", 2)
    result = disassemble(_recipe(), bag, {}, random.Random(4))
    assert result.done and bag.count("sword") == 1
    ((item, amount),) = result.gained
    assert item == "iron" and 1 <= amount <= 3 and bag.count("iron") == amount
    assert bag.count("gem") == 0  # a 0% yield never drops


def test_disassembly_needs_the_item_and_the_fee():
    bag, purse = Inventory(), {"gold": 5.0}
    assert disassemble(_recipe(), bag, purse, random.Random(1)).reason == "not_in_inventory"
    bag.add("sword")
    paid = _recipe(fee_currency="gold", fee=10)
    result = disassemble(paid, bag, purse, random.Random(1))
    assert not result.done and result.reason == "cannot_afford" and bag.count("sword") == 1
    purse["gold"] = 25.0
    assert disassemble(paid, bag, purse, random.Random(1)).done and purse["gold"] == 15.0


def test_disassembly_validation_and_round_trip():
    recipe = _recipe(fee_currency="gold", fee=3)
    assert DisassemblyRecipe.from_data(recipe.to_data()) == recipe
    with pytest.raises(ValueError):
        DisassemblyYield("x", 3, 1)
    with pytest.raises(ValueError):
        DisassemblyYield("x", chance=2)
    with pytest.raises(ValueError):
        DisassemblyRecipe("x", fee=-1)


def test_job_points_go_to_each_active_class_with_a_share_for_the_second():
    rules = JobPointRules("jp", per_battle=10, per_enemy=2, secondary=0.5)
    assert rules.award(("knight", "mage"), 3) == {"jp.knight": 16.0, "jp.mage": 8.0}
    assert rules.award((), 5) == {} and JobPointRules("none").award(("knight",), 5) == {}
    assert JobPointRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError):
        JobPointRules("x", prefix="a.b")
    with pytest.raises(ValueError):
        JobPointRules("x", secondary=2)


def _save(level, gold, items, switches=()):
    state = SimpleNamespace(
        actor_progression={},
        inventory=Inventory(),
        equipment_bag=[],
        currencies={"gold": gold},
        loadouts={},
        pets=[],
        active_pet_id="",
        actor_snapshots={},
        progression_allocations={},
        world={"seen": level},
        party_actor_ids=("hero",),
    )
    from asteria.rpg import ActorProgressionState

    state.actor_progression["hero"] = ActorProgressionState(level, 500.0 * level)
    for item_id, count in items.items():
        state.inventory.add(item_id, count)
    context = SimpleNamespace(switches=dict.fromkeys(switches, True))
    context.set_switch = lambda name, value: context.switches.__setitem__(name, value)
    return SimpleNamespace(rpg_state=state, event_context=context)


def test_new_game_plus_carries_only_what_the_rules_name():
    old, new = _save(12, 900.0, {"potion": 4}, ("ending.a", "tmp.x")), _save(1, 50.0, {"map": 1})
    rules = NewGamePlusRules(
        "ngp", carry=("levels", "inventory"), carry_switches=("ending.",), level_cap=10
    )
    result = carry_over(rules, old, new)
    after = result.rpg_state
    assert after.actor_progression["hero"].level == 10  # capped
    assert after.actor_progression["hero"].experience == 0.0  # a cut level restarts its experience
    assert after.inventory.count("potion") == 4 and after.inventory.count("map") == 1
    assert after.currencies["gold"] == 50.0 and after.world == {"seen": 1}  # not carried
    assert result.event_context.switches == {"ending.a": True}
    assert old.rpg_state.actor_progression["hero"].level == 12  # the old save is untouched


def test_new_game_plus_currency_share_and_uncapped_levels():
    old, new = _save(7, 1000.0, {}), _save(1, 100.0, {})
    rules = NewGamePlusRules(
        "ngp", carry=("levels", "currencies", "world"), keep_currency_share=0.25
    )
    after = carry_over(rules, old, new).rpg_state
    assert after.currencies["gold"] == pytest.approx(100.0 + 250.0)
    assert after.actor_progression["hero"].level == 7
    assert after.actor_progression["hero"].experience == 3500.0
    assert after.world == {"seen": 7}


def test_new_game_plus_validation_and_round_trip():
    rules = NewGamePlusRules(
        "n", carry=("pets", "equipment"), carry_switches=("a.", "b."), level_cap=5
    )
    assert NewGamePlusRules.from_data(rules.to_data()) == rules
    with pytest.raises(ValueError):
        NewGamePlusRules("n", carry=("souls",))
    with pytest.raises(ValueError):
        NewGamePlusRules("n", keep_currency_share=2)
    with pytest.raises(TypeError):
        carry_over("rules", _save(1, 0, {}), _save(1, 0, {}))
