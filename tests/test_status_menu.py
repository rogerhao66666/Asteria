"""UI-01: Status / Items / Equipment / Skills screens in the playable runtime, projected through the
canonical presentation screen runtimes; item use and equipment changes go through the game session."""

import pygame


def _key(rt, key):
    rt._frame([pygame.event.Event(pygame.KEYDOWN, key=key, mod=0)], 0.016)


def test_status_menu_opens_from_the_field_and_shows_every_tab(runtime):
    runtime._ui_mode = "field"
    _key(runtime, pygame.K_i)
    assert runtime._ui_mode == "status"
    menu = runtime.status_menu
    seen = {}
    for _ in range(4):
        seen[menu.tab] = menu.rows()
        _key(runtime, pygame.K_TAB)
    assert set(seen) == {"status", "items", "equipment", "skills"}
    assert any(r[0] == "resource" and r[1] == "vitality" for r in seen["status"])
    assert any(r[0] == "item" for r in seen["items"]) and any(r[0] == "slot" for r in seen["equipment"])
    assert any(r[0] == "ability" for r in seen["skills"])
    first = menu.actor_id
    _key(runtime, pygame.K_e)
    assert menu.actor_id != first  # next party member
    _key(runtime, pygame.K_ESCAPE)
    assert runtime._ui_mode == "field"


def test_using_a_consumable_changes_the_party_member_and_the_bag(runtime):
    from asteria.gameplay.effects import Effect, EffectOperation, EffectOperationKind
    from asteria.rpg.items import ItemDefinition

    game = runtime.game
    potion = ItemDefinition(
        "test_potion",
        "Test Potion",
        use_effects=[Effect("potion.heal", [EffectOperation(EffectOperationKind.RESOURCE_DELTA, "vitality", 30)])],
    )
    game.project.rpg_database.add_item(potion)
    actor = game.save.rpg_state.party_active_actor_ids[0]
    snapshot = game.save.rpg_state.actor_snapshots[actor]
    values = snapshot.resources["values"]["vitality"]
    values["current"] = values["maximum"] - 50  # hurt
    game.save.rpg_state.inventory.add("test_potion", 2)
    runtime.open_status_menu()
    menu = runtime.status_menu
    menu.tab = "items"
    menu.row = next(i for i, r in enumerate(menu.rows()) if r[1] == "test_potion")
    assert "(use)" in menu.rows()[menu.row][3]
    result = menu.activate()
    assert result.used and menu.message == "Used Test Potion"
    healed = game.save.rpg_state.actor_snapshots[actor].resources["values"]["vitality"]["current"]
    assert healed == values["maximum"] - 20 and game.save.rpg_state.inventory.count("test_potion") == 1


def test_equipment_tab_unequips_to_the_bag_and_equips_back(runtime):
    game = runtime.game
    runtime.open_status_menu()
    menu = runtime.status_menu
    menu.tab = "equipment"
    actor = menu.actor_id
    loadout = game.save.rpg_state.loadouts[actor]
    weapon = loadout.equipped("weapon")[0].equipment.equipment_id
    menu.row = next(i for i, r in enumerate(menu.rows()) if r == ("slot", "weapon", r[2], r[3]))
    assert menu.activate() == weapon
    assert not loadout.equipped("weapon") and game.save.rpg_state.inventory.count(weapon) >= 1
    candidates = [i for i, r in enumerate(menu.rows()) if r[0] == "candidate" and r[1] == weapon]
    assert candidates  # the bag item is offered back through the equipment screen view
    menu.row = candidates[0]
    menu.activate()
    assert loadout.equipped("weapon")[0].equipment.equipment_id == weapon


def test_status_menu_draws_in_a_window(runtime):
    runtime.open_status_menu()
    for _ in range(4):
        runtime._frame([], 0.016)
        _key(runtime, pygame.K_TAB)
    assert runtime.screen.get_at((40, 40))[:3] != (0, 0, 0)
