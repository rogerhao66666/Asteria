"""A menu screen drawn off screen with sample data, for the editor's layout canvas (U2b).

``MenuPreview(project, root)`` starts the game's own drawing code once without a window (SDL's
dummy video driver; the editor plays the game in a separate process, so this does not clash)
and fills a copy of the starting save so no screen is empty: money, a few of each kind of item,
some equipment in the bag, every recipe known, the quests that can start, a pet of each
species, two message-log lines. ``render(screen_id, locale)`` opens that screen the way the game
opens it, draws one frame and returns ``(surface, boxes)``: ``boxes`` maps each element the
screen drew to its rectangle on the picture, so the editor can outline and drag it.

Nothing here is saved: the preview plays on its own copy of the save.
"""

from __future__ import annotations

import os


class MenuPreview:
    def __init__(self, project, root, size=(1280, 720)):
        os.environ.setdefault("ASTERIA_MUTE", "1")
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        from asteria.runtime.playable_test_runtime import PlayableTestRuntime

        self.project = project
        save = project.game_start.instantiate(project) if project.game_start else None
        if save is None:
            raise ValueError("the project needs a game start to preview its menus")
        self.runtime = PlayableTestRuntime(project, save, root, width=size[0], height=size[1])
        self.runtime.open()
        self.runtime._menu_boxes = {}
        self._fill(self.runtime.game)

    def close(self):
        self.runtime.close()

    # --- sample data --------------------------------------------------------------------
    @staticmethod
    def _fill(game):
        db = game.project.rpg_database
        state = game.save.rpg_state
        for currency in {"gold", *state.currencies}:
            state.currencies[currency] = max(state.currencies.get(currency, 0), 5000.0)
        for item_id in list(db.items)[:16]:
            try:
                state.inventory.add(item_id, 3)
            except Exception:  # noqa: BLE001 - a key item or a full bag: the preview goes on
                pass
        worn = {g.equipment.equipment_id for lo in state.loadouts.values() for g in lo.equipped()}
        for equipment_id in [e for e in db.equipment if e not in worn][:4]:
            try:
                game.gain_equipment(equipment_id)
            except Exception:  # noqa: BLE001
                pass
        game.equip_offers.clear()
        for recipe_id in db.composition_recipes:
            try:
                game.learn_recipe(recipe_id)
            except Exception:  # noqa: BLE001
                pass
        for quest_id in list(db.quests)[:6]:
            try:
                game.start_quest(quest_id)
            except Exception:  # noqa: BLE001 - waits on another quest
                pass
        for species_id in list(db.pet_species)[:3]:
            try:
                game.add_pet(species_id, level=5)
            except Exception:  # noqa: BLE001
                pass
        game.backlog.add("", game.tr("backlog.title", "Message Log"))
        game.backlog.add("", game.tr("status.empty", "Nothing here yet."))

    # --- drawing ------------------------------------------------------------------------
    def render(self, screen_id, locale=None):
        """``(surface, boxes)`` of ``screen_id`` drawn once (in ``locale`` when given)."""
        rt = self.runtime
        game = rt.game
        if locale and locale in game.localizer.locales():
            game.set_locale(locale)
        self._reset()
        rt._menu_boxes.clear()
        rt._menu_style_cache = None
        rt._menu_preview = True  # the battle screen says where its groups are (no layout too)
        open_menu_screen(rt, screen_id)
        for _ in range(2):
            rt._frame([], 0.0)
        request = rt.__dict__.pop("_preview_request", None)
        if request is not None:  # a message window: drawn over the field with a sample
            from asteria.runtime.dialogue_screen import draw_message_window

            draw_message_window(rt, request, getattr(request, "line", None))
        from asteria.presentation.menu_layout import base_screen

        # a station without its own layout yet draws through the shared one
        found = rt._menu_boxes.get(screen_id) or rt._menu_boxes.get(base_screen(screen_id), {})
        boxes = dict(found)
        # screen pixels a layout unit takes (the battle's own coordinates are smaller)
        self.unit = float(rt.__dict__.get("_menu_units", {}).get(base_screen(screen_id), 1.0))
        surface = rt.capture()
        self._reset()
        return surface, boxes

    def _reset(self):
        rt = self.runtime
        game = rt.game
        if game.mode == "battle":  # the battle preview's fight: left without its outcome
            game.battle = None
            game.mode = "field"
            game.encounter_id = None
            game._enemy_ids = ()
            game.interaction.reset()
        rt._ui_mode = "field"
        game.close_shop()
        rt._shop_screen = None
        game.open_crafting_station = None
        game.open_service = None
        rt._service_screen = None
        game.equip_offers.clear()


def open_menu_screen(rt, screen_id):
    """Open ``screen_id`` the way the game opens it (the preview, and the editor's "Open in
    game", which starts the play-test on that screen)."""
    game = rt.game
    project = game.project
    db = project.rpg_database
    if screen_id in ("title", "pause", "settings", "game_over", "field_hint"):
        rt._ui_mode = "field" if screen_id == "field_hint" else screen_id
    elif screen_id == "controls":
        from asteria.runtime.input_rebinding import ControlsMenu

        rt.controls_menu = ControlsMenu(project.input_map, rt.settings.input_overrides, tr=game.tr)
        rt._ui_mode = "controls"
    elif screen_id == "save_slots":
        rt.open_slots("save", back="pause")
    elif screen_id == "status":
        rt.open_status_menu()
    elif screen_id == "bag":
        from asteria.runtime.bag_screen import BagScreen

        rt._bag_screen, rt._ui_mode = BagScreen(rt), "bag"
    elif screen_id == "equipment":
        rt.open_equipment_screen()
    elif screen_id == "enhance":
        rt.open_enhance_screen()
    elif screen_id == "skill_tree":
        from asteria.runtime.skill_tree_screen import SkillTreeScreen

        rt._skill_tree, rt._ui_mode = SkillTreeScreen(rt), "skills"
    elif screen_id == "shop":
        from asteria.runtime.game_menus import ShopScreen

        if db.shops:
            game.open_shop(sorted(db.shops)[0])
            rt._shop_screen, rt._ui_mode = ShopScreen(game), "shop"
    elif screen_id == "crafting" or screen_id.startswith("crafting."):
        station = screen_id.partition(".")[2]  # crafting.forge: that workstation's screen
        if not station:  # the shared layout: a station that draws through it
            used = {r.station for r in db.composition_recipes.values() if r.station}
            stations = sorted(db.workstations) or sorted(used)
            shared = [
                k
                for k in stations
                if rt.menu_layout(f"crafting.{k}") is None
                and not getattr(db.workstations.get(k), "layout", "")
            ]
            station = (shared or [""])[0]
        rt._open_crafting(station, back="field")
    elif screen_id.partition(".")[0] in ("quest_board", "recruit", "gacha"):
        from asteria.runtime.service_screens import open_service

        kind, _, record_id = screen_id.partition(".")  # gacha.star: that banner's own
        store = {"quest_board": db.quest_boards, "recruit": db.recruit_offices}.get(
            kind, db.gacha_banners
        )
        if not record_id:  # the shared layout: a record that draws through it
            shared = [
                k
                for k, v in sorted(store.items())
                if rt.menu_layout(f"{kind}.{k}") is None and not v.layout
            ]
            record_id = (shared or sorted(store) or [""])[0]
        if record_id in store:
            open_service(rt, kind, record_id)
    elif screen_id == "quests":
        rt._quest_return, rt._ui_mode = "field", "quests"
    elif screen_id == "pets":
        from asteria.runtime.pets_screen import PetsScreen

        rt._pets_screen, rt._ui_mode = PetsScreen(rt), "pets"
    elif screen_id in ("achievements", "bestiary"):
        rt._list_scroll, rt._ui_mode = 0, screen_id
    elif screen_id in ("backlog", "music", "credits", "ability_slots"):
        from asteria.runtime import extras_screens

        kind = {
            "backlog": extras_screens.BacklogScreen,
            "music": extras_screens.MusicRoomScreen,
            "credits": extras_screens.CreditsScreen,
            "ability_slots": extras_screens.AbilitySlotsScreen,
        }[screen_id]
        rt._extra_screen, rt._ui_mode = kind(rt), "extra"
    elif screen_id == "hud_action":
        rt._ui_mode = "field"
        if not game.action_scene:
            raise KeyError("the game starts on a map without action play: no action RPG HUD")
        hud = rt.action_hud.bottom
        hud.hint_left = hud.HINT_SECONDS  # the controls line shows
    elif screen_id == "battle":
        encounters = tuple(game.project.rpg_database.encounters)
        if not encounters:
            raise KeyError("the project has no encounter to show the battle screen with")
        rt._ui_mode = "field"
        game.start_encounter(encounters[0])
        rt._battle_presentation.begin()
        rt._advance_to_hero_turn()
        for _ in range(240):  # the camera and the figures settle, the menu opens
            rt._frame([], 1 / 60)
    elif screen_id in ("dialogue", "dialogue_choice"):
        rt._ui_mode = "field"
        rt._preview_request = sample_dialogue(game, screen_id, rt.resource_root)
    elif screen_id == "equip_offer":
        from asteria.runtime.session.support import EquipOffer

        state = game.save.rpg_state
        party = state.party_active_actor_ids
        if party and state.equipment_bag:
            item = state.equipment_bag[0]
            offer = EquipOffer(item.instance_id, party[0], item.equipment.slot)
            game.equip_offers.append(offer)
    else:
        raise KeyError(f"unknown menu screen: {screen_id}")


def sample_dialogue(game, screen_id, root=None):
    """A line (with the first picture of the game's ``portraits`` folder as its face) or a
    choice to show a message window with."""
    from asteria.events.dialogue import (
        ChoiceRequest,
        DialogueChoice,
        DialogueLine,
        DialogueRequest,
    )

    tr = game.tr
    if screen_id == "dialogue_choice":
        words = [
            tr("dialogue.sample_yes", "Yes, gladly"),
            tr("dialogue.sample_no", "Not now"),
            tr("dialogue.sample_ask", "Tell me more"),
        ]
        choices = tuple(DialogueChoice(w, n) for n, w in enumerate(words))
        return ChoiceRequest(tr("dialogue.choose", "Choose"), choices)
    from pathlib import Path

    portrait = ""
    for folder in ("portraits", "playable_assets/portraits"):
        found = sorted(Path(root or ".").joinpath(folder).glob("*.png"))
        if found:
            portrait = f"{folder}/{found[0].name}"
            break
    speaker = game.name_of(next(iter(game.project.rpg_database.actors.values()), None), "Roger")
    text = tr("status.empty", "Nothing here yet.") + "\n" + tr("backlog.title", "Message Log")
    return DialogueRequest(DialogueLine(text, speaker, portrait or ""))
