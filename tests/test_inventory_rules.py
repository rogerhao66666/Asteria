"""RPG-01: inventory rules authored per project - stack limits, unique items, a cap on different items with
exempt key items, and what happens when items do not fit. No rules = the bag is unlimited (as before)."""

import pytest
from test_session_events import BOSS_PROGRAM, _interact, _replace_program, _session

from asteria.events import EventInstruction
from asteria.rpg import ShopDefinition, ShopEntry
from asteria.rpg.actors import RpgDatabase
from asteria.rpg.items import Inventory, InventoryRules, ItemDefinition

ITEMS = {
    "potion": ItemDefinition("potion", "Potion", stack_limit=3),
    "crown": ItemDefinition("crown", "Crown", stack_limit=1),  # unique
    "map": ItemDefinition("map", "Map", tags=("item.key",), stack_limit=1),
    "herb": ItemDefinition("herb", "Herb"),
}


def _bag(**rules):
    return Inventory().configure(InventoryRules("bag", **rules), ITEMS.get)


def test_stack_limits_fill_or_reject_and_unique_items():
    bag = _bag()
    assert bag.add("potion", 2) == 2 and bag.add("potion", 5) == 3  # fill: keeps what fits
    assert bag.overflow == [("potion", 4)]
    assert bag.add("crown") == 1 and bag.add("crown") == 1  # unique: only one
    strict = _bag(overflow="reject")
    strict.add("potion", 2)
    assert strict.add("potion", 2) == 2 and strict.overflow == [("potion", 2)]  # reject: none of it
    free = _bag(stack_limits=False)
    assert free.add("potion", 50) == 50


def test_kind_cap_with_exempt_key_items():
    bag = _bag(max_kinds=2)
    bag.add("potion")
    bag.add("herb")
    assert bag.add("crown") == 0 and bag.overflow[-1] == ("crown", 1)  # a third kind does not fit
    assert bag.add("map") == 1  # key items never take a place
    assert bag.add("herb", 5) == 6  # more of a kind already carried still fits
    bag.remove("potion")
    assert bag.add("crown") == 1  # a place freed up


def test_no_rules_is_unlimited_and_saved_counts_load_exactly():
    plain = Inventory()
    assert plain.add("potion", 500) == 500 and plain.room_for("potion") is None
    loaded = Inventory.from_data(plain.to_data()).configure(InventoryRules("bag"), ITEMS.get)
    assert loaded.count("potion") == 500  # a save is restored as it was, even above a newer limit


def test_rules_round_trip_and_old_databases_have_none():
    rules = InventoryRules("bag", "Bag", stack_limits=False, max_kinds=20, exempt_tags=("item.key", "quest"))
    assert InventoryRules.from_data(rules.to_data()) == rules
    db = RpgDatabase()
    db.add_inventory_rules(rules)
    data = db.to_data()
    assert data["version"] == 30 and RpgDatabase.from_data(data).inventory_rules == {"bag": rules}
    old = dict(data, version=28)
    old.pop("inventory_rules")
    assert RpgDatabase.from_data(old).inventory_rules == {}
    with pytest.raises(ValueError):
        InventoryRules("bad", max_kinds=0)
    with pytest.raises(ValueError):
        InventoryRules("bad", overflow="explode")


def test_the_game_session_applies_the_project_rules_to_events_and_shops():
    project, _ = _session()
    db = project.rpg_database
    item_id = sorted(db.items)[0]
    limit = db.items[item_id].stack_limit
    db.add_inventory_rules(InventoryRules("bag", overflow="fill"))
    db.add_shop(ShopDefinition("rm_bag_shop", "Shop", [ShopEntry(item_id, buy_prices={"gold": 1})]))
    project, game = _session(project)
    state = game.save.rpg_state
    held = state.inventory.count(item_id)
    _replace_program(
        project,
        BOSS_PROGRAM,
        [
            EventInstruction("WORLD", {"command": "GIVE_ITEM", "args": {"item_id": item_id, "quantity": limit + 5}}),
            EventInstruction("END"),
        ],
    )
    _interact(game)
    assert state.inventory.count(item_id) == max(held, limit)  # filled up to the stack limit
    assert game.inventory_overflow and game.inventory_overflow[-1][0] == item_id
    state.currencies["gold"] = 100.0
    game.open_shop("rm_bag_shop")
    if state.inventory.count(item_id) >= limit:
        with pytest.raises(Exception, match="no room"):
            game.buy(item_id, 1)
        assert state.currencies["gold"] == 100.0  # nothing charged for an item the bag cannot hold
    assert state.inventory.count(item_id) == max(held, limit)
