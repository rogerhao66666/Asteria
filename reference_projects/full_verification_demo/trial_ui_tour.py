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
    "healing_herb",
    "bat_wing",
    "scorpion_claw",
    "coal",
    "ruby_item",
)
# left undiscovered: the crafting screens show a ??? row (U4)
HIDDEN_RECIPES = ("brew_elixir", "forge_ice_orb")


BAG = ("a_mithril_mail", "w_saint_staff", "hd_plate_helmet", "lg_wizard_leggings")
# Roger wears these (U3): the doll's head, legs, feet and second weapon places fill
WORN = ("hd_chain_helmet", "lg_chain_leggings", "ft_explorer_boots", "w_demon_ring")


def prepare(game):
    state = game.save.rpg_state
    state.currencies["gold"] = 50000.0
    for item_id in ITEMS:
        state.inventory.add(item_id, 3)
    db = game.project.rpg_database
    for recipe_id in db.composition_recipes:  # the recipes known: the crafting lists fill
        if recipe_id not in HIDDEN_RECIPES:
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
    allocation = state.progression_allocations.get("hero_01")
    if allocation is not None:  # the Status page's + have points to spend (D87)
        allocation.grant("stat_points", 5)
    game.backlog.add("Warden Thessaly", "The road north is yours to clear.")
    game.backlog.add("Roger", "Then I'll clear it.")


def reset(runtime):
    game = runtime.game
    runtime._ui_mode = "field"
    game.close_shop()
    runtime._shop_screen = None
    game.open_crafting_station = None
    runtime._service_screen = None
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

    def page(name, category=0, item_filter=-1):  # a pause entry's page of its own (D87)
        def setup():
            runtime._open_pause_page(name)
            runtime.status_menu.category = category
            runtime.status_menu.filter = item_filter

        return setup

    def gear_page():
        def setup():
            if not game.save.rpg_state.equipment_bag:
                game.gain_equipment("w_sunbrand")
            page("items", 4)()  # Weapons

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

    def craft(station, tab, recipe_id="", quantity=1):
        def setup():
            runtime._open_crafting(station, back="field")
            screen = runtime._crafting_screen
            screen.tab = tab
            ids = [r.recipe_id for r in screen.rows()]
            screen.index = ids.index(recipe_id) if recipe_id in ids else 0
            screen.quantity = quantity

        return setup

    def extra(kind):
        return mode("extra", _extra_screen=lambda: kind(runtime))

    def service(kind, record_id, **state):  # the board, the guild office, the chest (U5)
        def setup():
            from asteria.runtime.service_screens import open_service

            screen = open_service(runtime, kind, record_id)
            for name, value in state.items():
                setattr(screen, name, value)

        return setup

    def pulled():  # ten pulls with a fixed seed, the prizes shown
        import random

        from asteria.runtime.service_screens import open_service

        game.save.rpg_state.currencies["star_stones"] = 300.0
        screen = open_service(runtime, "gacha", "starfall")
        screen.action = 1
        screen.confirm(random.Random(5))
        screen.page = "results"

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
        ("page_status", page("status")),
        ("page_items", page("items")),
        ("page_items_potions", page("items", 1, 1)),
        ("page_items_gear", gear_page()),  # a bag piece's details beside the list (D88)
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
        ("crafting", craft("alchemy", 0, "brew_hi_potion")),
        ("crafting_gems", craft("alchemy", 1)),
        ("crafting_disassemble", craft("alchemy", 4)),
        ("crafting_forge", craft("forge", 1, "forge_iron_ball", quantity=3)),
        ("crafting_hidden", craft("forge", 2, "forge_ice_orb")),
        ("board", service("quest_board", "hearthfold_board")),
        ("board_flipped", service("quest_board", "hearthfold_board", flipped=True)),
        ("recruit", service("recruit", "hearthfold_guild")),
        ("recruit_ask", service("recruit", "hearthfold_guild", asking=True)),
        ("gacha", service("gacha", "starfall")),
        ("gacha_results", pulled),
        ("gacha_rates", service("gacha", "starfall", page="rates")),
        ("gacha_history", service("gacha", "starfall", page="history")),
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
