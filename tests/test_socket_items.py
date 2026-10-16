"""Cards / gems / orbs as bag items: an item names the attachment it becomes, socketing spends
one from the bag, and taking it out again either returns it or destroys it (an item option)."""

import dataclasses

import pytest
from test_octopath_style_battle import _project
from test_session_events import _session

from asteria.gameplay.modifiers import ModifierOperation, StatModifier
from asteria.rpg.items import AttachmentDefinition, ItemDefinition, SocketDefinition


def _game(*, destroyed_on_removal=False, accepted=("gem",)):
    project = _project()
    db = project.rpg_database
    for name, power in (("ruby", 7.0), ("opal", 3.0)):
        db.attachments[name] = AttachmentDefinition(
            name,
            name.title(),
            tags=("gem",),
            modifiers=(StatModifier(f"{name}.m", "power", ModifierOperation.ADD, power),),
        )
        db.items[f"{name}_item"] = ItemDefinition(
            f"{name}_item",
            name.title(),
            attachment_id=name,
            destroyed_on_removal=destroyed_on_removal,
        )
    db.items["junk"] = ItemDefinition("junk", "Junk")
    project, game = _session(project)
    hero = game.save.rpg_state.party_active_actor_ids[0]
    item = game.save.rpg_state.loadouts[hero].equipped()[0]
    item.equipment = dataclasses.replace(
        item.equipment, sockets=(SocketDefinition("s1", accepted_tags=accepted),)
    )
    bag = game.save.rpg_state.inventory
    bag.add("ruby_item", 1)
    bag.add("opal_item", 1)
    return game, hero, item, bag


def _power(item):
    return sum(m.value for m in item.modifiers() if m.stat == "power")


def test_socketing_spends_the_item_and_adds_its_stats():
    game, hero, item, bag = _game()
    base = _power(item)
    game.socket_item(hero, item.instance_id, "s1", "ruby_item")
    assert bag.count("ruby_item") == 0
    assert item.attachments["s1"].attachment_id == "ruby"
    assert _power(item) == pytest.approx(base + 7.0)


def test_replacing_returns_the_old_item_by_default():
    game, hero, item, bag = _game()
    game.socket_item(hero, item.instance_id, "s1", "ruby_item")
    game.socket_item(hero, item.instance_id, "s1", "opal_item")
    assert bag.count("ruby_item") == 1 and bag.count("opal_item") == 0
    assert item.attachments["s1"].attachment_id == "opal"


def test_destroyed_on_removal_is_an_item_option():
    game, hero, item, bag = _game(destroyed_on_removal=True)
    game.socket_item(hero, item.instance_id, "s1", "ruby_item")
    game.socket_item(hero, item.instance_id, "s1", "opal_item")
    assert bag.count("ruby_item") == 0  # gone for good


def test_unsocket_returns_or_destroys():
    game, hero, item, bag = _game()
    game.socket_item(hero, item.instance_id, "s1", "ruby_item")
    game.unsocket_item(hero, item.instance_id, "s1")
    assert bag.count("ruby_item") == 1 and "s1" not in item.attachments


def test_refusals_leave_the_bag_untouched():
    game, hero, item, bag = _game(accepted=("rune",))
    with pytest.raises(Exception, match="compatible"):
        game.socket_item(hero, item.instance_id, "s1", "ruby_item")
    assert bag.count("ruby_item") == 1
    with pytest.raises(Exception, match="not socketable"):
        game.socket_item(hero, item.instance_id, "s1", "junk")


def test_socketing_needs_the_item_in_the_bag():
    game, hero, item, bag = _game()
    bag.remove("ruby_item")
    with pytest.raises(Exception, match="no ruby_item"):
        game.socket_item(hero, item.instance_id, "s1", "ruby_item")


def test_item_definition_round_trip_and_defaults():
    plain = ItemDefinition("p", "P").to_data()
    assert "attachment_id" not in plain and "destroyed_on_removal" not in plain
    data = ItemDefinition("g", "G", attachment_id="a", destroyed_on_removal=True)
    again = ItemDefinition.from_data(data.to_data())
    assert again.attachment_id == "a" and again.destroyed_on_removal
