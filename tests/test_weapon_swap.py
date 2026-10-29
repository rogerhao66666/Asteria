"""Swapping a weapon, in the field or in the middle of a battle: the member's abilities follow."""

import dataclasses

from test_break_battle import _battle, _project

from asteria.events.world_commands import WorldCommand


def _project_with_staff():
    project = _project()
    db = project.rpg_database
    db.equipment["oct_staff_item"] = dataclasses.replace(
        db.equipment["oct_bow_item"],
        equipment_id="oct_staff_item",
        granted_abilities=("oct_fire",),
        tags=("weapon", "equip.staff"),
    )
    return project


def test_swap_in_battle_changes_the_abilities_and_keeps_the_other_weapon():
    game, hero, _boss = _battle(_project_with_staff())
    member = game.battle.member(hero)
    assert {"oct_sword", "oct_bow", "oct_fire"} <= set(member.ability_ids)
    game.world_commands.dispatch(
        WorldCommand(
            "EQUIP_ITEM", {"actor_id": hero, "equipment_id": "oct_staff_item", "index": 1}
        )
    )
    member = game.battle.member(hero)
    assert "oct_bow" not in member.ability_ids  # the bow is gone
    assert {"oct_sword", "oct_fire"} <= set(member.ability_ids)  # the sword stayed
    held = [
        x.equipment.equipment_id for x in game.save.rpg_state.loadouts[hero].equipped("weapon")
    ]
    assert held == ["oct_sword_item", "oct_staff_item"]


def test_swap_needs_an_actor_and_an_item():
    import pytest

    from asteria.runtime.world_command_handlers import WorldCommandError

    game, hero, _boss = _battle(_project_with_staff())
    with pytest.raises(WorldCommandError):
        game.world_commands.dispatch(WorldCommand("EQUIP_ITEM", {"actor_id": hero}))
