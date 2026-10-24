"""Every menu screen of the Full Verification demo, opened the way the game opens it (U1).

``prepare(game)`` fills a fresh save so no screen is empty (gold, items, every recipe, the
quests that can start, a pet of each species, two backlog lines). ``screens(runtime)`` gives
``(name, setup)`` pairs; ``visit(runtime, setup)`` runs one and ``reset(runtime)`` puts the game
back on the field. ``scripts/ui_tour_live_check.py`` pictures them in a real window and
``tests/test_full_verification_ui_words.py`` reads every word they draw in Chinese.
"""

from __future__ import annotations

ITEMS = (
    "potion",
    "hi_potion",
    "antidote",
    "thunder_bomb",
    "fire_orb_item",
    "card_sage_item",
    "wolf_fur",
    "iron_ore",
    "silver_ore",
    "blessed_scroll",
    "mithril_ingot",
    "ice_orb_item",
    "card_knight_item",
)


BAG = ("a_mithril_mail", "w_saint_staff", "hd_plate_helmet", "lg_wizard_leggings")
# Roger wears these (U3): the doll's head, legs, feet and second weapon places fill
WORN = ("hd_chain_helmet", "lg_chain_leggings", "ft_explorer_boots", "w_demon_ring")


def prepare(game):
    state = game.save.rpg_state
    state.currencies["gold"] = 50000.0
    for item_id in ITEMS:
        state.inventory.add(item_id, 3)
    db = game.project.rpg_database
    for recipe_id in db.composition_recipes:  # every recipe known: the crafting list fills
        game.learn_recipe(recipe_id)
    for quest_id in db.quests:  # those that can start now (others wait on earlier quests)
        try:
            game.start_quest(quest_id)
        except Exception:  # noqa: BLE001 - a prerequisite not met yet
            pass
    for species_id in db.pet_species:
        game.add_pet(species_id, level=5)
    for equipment_id in BAG:  # the bag's grid and its compare tooltip have something to show
        game.gain_equipment(equipment_id)
    for equipment_id in WORN:
        (piece,) = game.gain_equipment(equipment_id)
        game.wear_from_bag("hero_01", piece.instance_id, piece.equipment.slot)
    (scepter,) = game.gain_equipment("w_bone_scepter")  # a piece that grows: the growth page
    game.wear_from_bag("hero_01", scepter.instance_id, "weapon", 0)
    game.equip_offers.clear()
    game.backlog.add("Warden Thessaly", "The road north is yours to clear.")
    game.backlog.add("Roger", "Then I'll clear it.")


def reset(runtime):
    game = runtime.game
    runtime._ui_mode = "field"
    game.close_shop()
    runtime._shop_screen = None
    game.open_crafting_station = None
    game.battle = None
    game.mode = "field"


def _gear(runtime, kind, **state):
    """Open the equipment (``kind`` "equipment") or enhance screen and set its state: the
    enhance screen's page, the chosen rows, the focus."""

    def setup():
        if kind == "equipment":
            runtime.open_equipment_screen(back="field")
        else:
            runtime.open_enhance_screen(back="field")
        screen = runtime._gear_screen
        for name, value in state.items():
            if name == "rows":  # a row may be worked out when the screen opens
                screen.rows.update({k: v() if callable(v) else v for k, v in value.items()})
            else:
                setattr(screen, name, value)

    return setup


def _row(runtime, equipment_id):
    """The enhance screen's gear row of a piece Roger wears."""
    loadout = runtime.game.save.rpg_state.loadouts["hero_01"]
    pieces = [p for s in loadout.slot_ids() for p in loadout.equipped(s)]
    return next(i for i, p in enumerate(pieces) if p.equipment.equipment_id == equipment_id)


def screens(runtime):
    """``[(name, setup)]`` for every screen (``setup()`` opens it)."""
    from asteria.events.world_commands import WorldCommand
    from asteria.runtime import extras_screens
    from asteria.runtime.bag_screen import BagScreen
    from asteria.runtime.game_menus import ShopScreen
    from asteria.runtime.pets_screen import PetsScreen
    from asteria.runtime.skill_tree_screen import SkillTreeScreen

    game = runtime.game
    project = runtime.project

    def mode(value, **attrs):
        def setup():
            for k, v in attrs.items():
                setattr(runtime, k, v() if callable(v) else v)
            runtime._ui_mode = value

        return setup

    def controls():
        from asteria.runtime.input_rebinding import ControlsMenu

        return ControlsMenu(project.input_map, runtime.settings.input_overrides, tr=game.tr)

    def status(tab):
        def setup():
            runtime.open_status_menu()
            runtime.status_menu.tab = tab

        return setup

    def shop(tab):
        def setup():
            game.open_shop("remedy_shop")
            runtime._shop_screen = ShopScreen(game)
            runtime._shop_screen.tab = tab
            runtime._ui_mode = "shop"

        return setup

    def offer():  # the Demon Ring fits the free hand: "wear it now?"
        game.world_commands.dispatch(
            WorldCommand("GIVE_EQUIPMENT", {"equipment_id": "w_demon_ring"})
        )

    def extra(kind):
        return mode("extra", _extra_screen=lambda: kind(runtime))

    return [
        ("title", mode("title")),
        ("field", mode("field")),
        ("pause", mode("pause")),
        ("settings", mode("settings")),
        ("controls", mode("controls", controls_menu=controls)),
        ("save_slots", lambda: runtime.open_slots("save", back="pause")),
        ("status", status("status")),
        ("status_items", status("items")),
        ("status_equipment", status("equipment")),
        ("status_skills", status("skills")),
        ("bag", mode("bag", _bag_screen=lambda: BagScreen(runtime))),
        ("skill_tree", mode("skills", _skill_tree=lambda: SkillTreeScreen(runtime))),
        ("build", mode("build")),
        ("equipment", _gear(runtime, "equipment")),
        ("equipment_list", _gear(runtime, "equipment", place=7, focus="list")),
        ("enhance_refine", _gear(runtime, "enhance", tab=0)),
        (
            "enhance_sockets",
            _gear(
                runtime,
                "enhance",
                tab=1,
                focus="choices",
                rows={"gear": lambda: _row(runtime, "w_demon_ring")},
            ),
        ),
        (
            "enhance_cards",
            _gear(
                runtime,
                "enhance",
                tab=2,
                focus="sockets",
                rows={"gear": lambda: _row(runtime, "w_demon_ring"), "sockets": 1},
            ),
        ),
        ("enhance_growth", _gear(runtime, "enhance", tab=3)),
        ("crafting", lambda: runtime._open_crafting("", back="field")),
        ("shop_buy", shop("buy")),
        ("shop_sell", shop("sell")),
        ("quests", mode("quests", _quest_return="field")),
        ("pets", mode("pets", _pets_screen=lambda: PetsScreen(runtime))),
        ("achievements", mode("achievements", _list_scroll=0)),
        ("bestiary", mode("bestiary", _list_scroll=0)),
        ("backlog", extra(extras_screens.BacklogScreen)),
        ("music", extra(extras_screens.MusicRoomScreen)),
        ("credits", extra(extras_screens.CreditsScreen)),
        ("ability_slots", extra(extras_screens.AbilitySlotsScreen)),
        ("equip_offer", offer),
    ]
