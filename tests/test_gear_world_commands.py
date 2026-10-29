"""World commands that let event programs level, refine and socket gear (the hooks a smith or a
shrine NPC needs)."""

import pytest
from test_refine import RULES, _game
from test_socket_items import _game as _socket_game

from asteria.events.world_commands import WorldCommand
from asteria.rpg.refine import RefineRules
from asteria.runtime.world_command_handlers import (
    STANDARD_WORLD_COMMANDS,
    WORLD_COMMAND_ARGUMENTS,
    WorldCommandError,
)

NEW = (
    "GRANT_EXPERIENCE",
    "REFINE_EQUIPMENT",
    "SOCKET_ITEM",
    "UNSOCKET_ITEM",
    "UPGRADE_EQUIPMENT",
    "EQUIP_ITEM",
    "DISASSEMBLE",
)


def test_new_commands_are_standard_and_documented():
    for name in NEW:
        assert name in STANDARD_WORLD_COMMANDS and WORLD_COMMAND_ARGUMENTS[name]


def test_refine_command():
    game, hero, item = _game(RefineRules("r", **RULES))
    game.world_commands.dispatch(
        WorldCommand("REFINE_EQUIPMENT", {"actor_id": hero, "instance_id": item.instance_id})
    )
    assert item.refine_level == 1


def test_socket_and_unsocket_commands():
    game, hero, item, bag = _socket_game()
    args = {"actor_id": hero, "instance_id": item.instance_id}
    game.world_commands.dispatch(
        WorldCommand("SOCKET_ITEM", {**args, "socket_id": "s1", "item_id": "ruby_item"})
    )
    assert item.attachments["s1"].attachment_id == "ruby"
    game.world_commands.dispatch(WorldCommand("UNSOCKET_ITEM", {**args, "socket_id": "s1"}))
    assert bag.count("ruby_item") == 1


def test_grant_experience_command_levels_and_hands_out_points():
    game, hero, _item = _game()
    game.grant_actor_experience(hero, 0)
    before = game.save.rpg_state.actor_progression[hero].level
    game.world_commands.dispatch(
        WorldCommand(
            "GRANT_EXPERIENCE",
            {"actor_id": hero, "amount": 3000, "threshold": 1000, "points": "stat_points=5"},
        )
    )
    state = game.save.rpg_state.actor_progression[hero]
    assert state.level >= before + 2 and state.points["stat_points"] >= 10


def test_bad_arguments_are_reported():
    game, hero, item = _game()
    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(WorldCommand("REFINE_EQUIPMENT", {"actor_id": hero}))


def test_disassemble_command_breaks_an_item_down():
    from test_break_battle import _project
    from test_session_events import _session

    from asteria.rpg.disassembly import DisassemblyRecipe, DisassemblyYield

    project = _project()
    project.rpg_database.add_disassembly_recipe(
        DisassemblyRecipe("healing_herb", (DisassemblyYield("fire_dust", 2, 2, 1.0),))
    )
    _, game = _session(project)
    bag = game.save.rpg_state.inventory
    bag.add("healing_herb", 1)
    herbs, dust = bag.count("healing_herb"), bag.count("fire_dust")
    game.world_commands.dispatch(WorldCommand("DISASSEMBLE", {"item_id": "healing_herb"}))
    assert bag.count("healing_herb") == herbs - 1 and bag.count("fire_dust") == dust + 2
