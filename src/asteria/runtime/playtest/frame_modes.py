"""One frame of the screen the player is on.

``PlayableTestRuntime._frame`` handles what every frame does (time played, the debugger, the
network game); then the open menu screen, named by ``_ui_mode``, gets the frame from
``SCREEN_FRAMES``. With no menu open the frame goes to the creature battle screen, the battle
or the field. The field frame also opens the screens a story event asked for (a shop, a name
entry, crafting...), and starts the battle an encounter began.
"""

from __future__ import annotations

from asteria.core import Transform
from asteria.runtime.menus.game_menus import ShopScreen

# _ui_mode -> the method that runs that screen's frame, as (events, dt)
SCREEN_FRAMES = {
    "title": "_title_frame",
    "build": "_build_frame",
    "equipment": "_gear_frame",
    "enhance": "_gear_frame",
    "pause": "_pause_frame",
    "slots": "_slots_frame",
    "controls": "_controls_frame",
    "status": "_status_frame",
    "quests": "_quests_frame",
    "shop": "_shop_frame",
    "crafting": "_crafting_frame",
    "service": "_service_frame",  # a quest board, recruiting office or gacha (U5)
    "achievements": "_list_screen_frame",
    "bestiary": "_list_screen_frame",
    "settings": "_settings_frame",
    "bag": "_bag_frame",
    "extra": "_extra_frame",
    "creature_menu": "_creature_menu_frame",  # the start menu in the game's own art
    "name_input": "_name_input_frame",  # NAME_INPUT: entering a name
    "picture_choice": "_picture_choice_frame",  # PICTURE_CHOICE: pictured options
    "creature_shop": "_creature_shop_frame",  # a shop in the game's own art
    "pets": "_pets_frame",
    "learn": "_learn_frame",  # a creature learned a move past its limit
    "skills": "_skills_frame",
    "game_over": "_game_over_frame",
}


class FrameModesMixin:
    """The frame of each screen: menus, the creature battle, the battle and the field."""

    # defaults until something sets them (code may read them first)
    _bgm_override = None
    _creature_menu_back = "field"
    _last_player_xy = None
    _network_event_busy = False

    def _screen_frame(self, events, dt):
        """Run the frame of the screen the player is on."""
        method = SCREEN_FRAMES.get(self._ui_mode)
        if method is not None:
            getattr(self, method)(events, dt)
        elif self._creature_battle is not None:  # the creature battle screen (one on one)
            self._creature_battle_frame(events, dt)
        elif self.game.mode == "battle" and self._creature_style() and not self._victory:
            self._open_creature_battle()  # started outside the field (an event, a test)
        elif self.game.mode == "battle" or self._victory:
            self._battle_frame(events, dt)
        elif self.game.mode == "field":
            self._field_frame(events, dt)

    # -- menu screens --------------------------------------------------------------------

    def _menu_screen_frame(self, screen, events, dt, *, back):
        """A menu screen object: handled, then drawn, or closed back to ``back``."""
        screen.handle(dt, events)
        if screen.closed:
            self._ui_mode = back
            return True
        with self.menu_fit():
            screen.draw()
        return False

    def _title_frame(self, events, dt):
        program = self._title_program()
        if program:
            self._title_program_frame(events, dt, program)
            return
        for event in events:
            if event.type == self.pg.KEYDOWN and event.key == self.pg.K_n:
                self._ui_mode = "field"
            elif event.type == self.pg.KEYDOWN and event.key == self.pg.K_l:
                self.open_slots("load", back="title")
        self._draw_title()

    def _build_frame(self, events, dt):
        self._build_menu_input(events)
        self._draw_build_menu()

    def _gear_frame(self, events, dt):
        screen = self._gear_screen
        self._menu_screen_frame(screen, events, dt, back=screen.back)

    def _pause_frame(self, events, dt):
        self._pause_input()
        self._draw_overlay_menu(self.game.tr("pause.heading", "Paused"), self._pause_menu)

    def _slots_frame(self, events, dt):
        self._slots_input(events)
        self._draw_slots()

    def _controls_frame(self, events, dt):
        self._controls_input(events)
        self._draw_controls()

    def _status_frame(self, events, dt):
        self._status_input(events)
        with self.menu_fit():
            self._draw_status_menu()

    def _quests_frame(self, events, dt):
        self._quests_input()
        with self.menu_fit():
            self._draw_quests()

    def _shop_frame(self, events, dt):
        self._shop_input()
        with self.menu_fit():
            self._draw_shop()

    def _crafting_frame(self, events, dt):
        self._crafting_input(events)
        with self.menu_fit():
            self._draw_crafting()

    def _service_frame(self, events, dt):
        screen = self._service_screen
        if self._menu_screen_frame(screen, events, dt, back=screen.back):
            self._service_screen = None

    def _list_screen_frame(self, events, dt):
        self._list_screen_input()
        with self.menu_fit():
            self._draw_list_screen(self._ui_mode)

    def _settings_frame(self, events, dt):
        self._settings_input()
        self._draw_settings()

    def _bag_frame(self, events, dt):
        self._bag_screen.handle(dt)
        if self._bag_screen.closed:
            self._ui_mode = "field"
        else:
            with self.menu_fit():
                self._bag_screen.draw()

    def _extra_frame(self, events, dt):
        self._menu_screen_frame(self._extra_screen, events, dt, back="pause")

    def _creature_menu_frame(self, events, dt):
        menu = self._creature_menu
        menu.update(dt, events)
        if menu.done:
            self._creature_menu = None
            self._ui_mode = self._creature_menu_back
            self._creature_menu_back = "field"
            if self._ui_mode == "field":
                self._draw_field(False)
            return
        from asteria.runtime.creature.menu_style import OVERLAY_PHASES

        if menu.phase in OVERLAY_PHASES:
            self._draw_field(False)
        menu.draw()

    def _name_input_frame(self, events, dt):
        self._name_input.update(dt, events)
        if self._name_input.done:
            self._name_input = None
            self._ui_mode = "field"
            self._draw_field(False)
        else:
            self._name_input.draw()

    def _picture_choice_frame(self, events, dt):
        self._picture_choice.update(dt, events)
        if self._picture_choice.done:
            self._picture_choice = None
            self._ui_mode = "field"
            self._draw_field(False)
        else:
            self._picture_choice.draw()

    def _pets_frame(self, events, dt):
        screen = self._pets_screen
        self._menu_screen_frame(screen, events, dt, back=getattr(screen, "back", "pause"))

    def _learn_frame(self, events, dt):
        self._learn_input(events)
        self._draw_field(False)
        self._draw_learn_prompt()

    def _skills_frame(self, events, dt):
        tree = self._skill_tree
        tree.handle(dt, events)
        if tree.closed:
            self._ui_mode = getattr(tree, "back", "field")
        else:
            tree.draw()

    def _game_over_frame(self, events, dt):
        self._game_over_input()
        title = self.game.tr("game_over.heading", "Game Over")
        self._draw_overlay_menu(title, self._game_over_menu, base="battle", screen_id="game_over")

    def _show_game_over(self, *, stop_music=True):
        self._game_over_menu.index = 0
        self._ui_mode = "game_over"
        if stop_music:
            self.audio.stop_music(fade_out=0.5)

    # -- battles -------------------------------------------------------------------------

    def _open_creature_battle(self):
        """The creature battle screen (one on one) for the battle that just began."""
        from asteria.runtime.creature.battle import CreatureBattleScreen

        self._creature_battle = CreatureBattleScreen(self)
        self._end_temporary_music()
        self._music(
            self._creature_battle.music("start") or self.manifest.get("battle", {}).get("bgm")
        )
        self._creature_battle.draw()

    def _creature_battle_frame(self, events, dt):
        screen = self._creature_battle
        if not self._dialogue_input(events):
            screen.update(dt, events)
        screen.draw()
        self._draw_dialogue()
        if not screen.done:
            return
        self._creature_battle = None
        if screen.weather_rules:
            self.game.set_battle_weather("none")
        if screen.defeated and "defeat_continues" in screen.tags:
            self.game.mode = "field"  # a battle the story goes on after, lost or won
            self.game.battle = None
        elif screen.defeated and self.game.rules.defeat == "respawn":
            self.game.respawn_after_defeat()  # healed at the last respawn point
        elif screen.defeated:
            self.game.mode = "field"
            self.game.battle = None
            self._show_game_over()
        else:
            self.game.mode = "field"

    def _battle_frame(self, events, dt):
        if self.game.mode == "battle":
            with self.profiler.section("events"):
                self.game.update_events(dt)  # battle events (EVT-03)
        if not (
            self._dialogue_input(events) or (self.game.mode == "battle" and self.game.event_busy)
        ):
            self._battle_input(events)
        self._present_battle(dt)
        self._draw_dialogue()
        if self._defeat:
            self._show_game_over()

    def _start_battle(self, dt):
        """An encounter began on the field: open its battle screen."""
        if self._creature_style():
            self._open_creature_battle()
            return
        self._turn_actor = None
        self._battle_presentation.begin()
        self._music(self.manifest.get("battle", {}).get("bgm"))
        self._advance_to_hero_turn()
        self._present_battle(dt)

    # -- the field -----------------------------------------------------------------------

    def _events_busy(self):
        """A story event still runs (in a network game, the host's)."""
        if self._multiplayer_connected():
            return self._network_event_busy
        return self.game.event_busy

    def _open_requested_screens(self):
        """Open the screens story events asked for, each once the dialogue has closed."""
        game = self.game
        talking = game.pending_dialogue is not None
        if self._ui_mode == "field" and game.name_input_request and not talking:
            from asteria.runtime.menus.name_input import NameInputScreen

            self._name_input = NameInputScreen(self, game.name_input_request)
            self._ui_mode = "name_input"  # NAME_INPUT: the event waits for the name
        if self._ui_mode == "field" and game.picture_choice_request and not talking:
            from asteria.runtime.menus.picture_choice import PictureChoiceScreen

            self._picture_choice = PictureChoiceScreen(self, game.picture_choice_request)
            self._ui_mode = "picture_choice"  # PICTURE_CHOICE: the event waits for the choice
        from asteria.presentation.screens.creature import creature_settings

        if (  # a shop in the game's own art opens at once: the event waits for it
            self._ui_mode == "field"
            and game.open_shop_id
            and creature_settings(self, "field.creature_shop")
            and game.pending_dialogue is None
        ):
            from asteria.runtime.creature.shop import CreatureShopScreen

            self._creature_shop = CreatureShopScreen(self)
            self._ui_mode = "creature_shop"
        busy = self._events_busy()
        if self._ui_mode == "field" and game.open_shop_id and not busy:
            self._shop_screen = ShopScreen(game)
            self._ui_mode = "shop"
        if self._ui_mode == "field" and game.pet_storage_requested and not busy:
            from asteria.runtime.menus.pets import PetsScreen

            game.pet_storage_requested = False
            self._pets_screen = PetsScreen(self, back="field", storage=True)
            self._ui_mode = "pets"
        if self._ui_mode == "field" and game.pending_pet_moves() and not busy:
            self._ui_mode = "learn"
        if self._ui_mode == "field" and game.open_crafting_station is not None and not busy:
            self._open_crafting(game.open_crafting_station, back="field")
        service = getattr(game, "open_service", None)
        if self._ui_mode == "field" and service and not busy:
            from asteria.runtime.menus.services import open_service

            game.open_service = None
            open_service(self, *service, back="field")

    def _update_field_world(self, dt):
        """The field's own frame: the world, the network player, the action HUD."""
        if not self._multiplayer_connected():
            with self.profiler.section("update"):
                self.game.field_update(dt)
        self._sync_multiplayer_player()
        if not self.game.action_scene:
            return
        self.action_hud.observe(self.game, dt)
        if self._multiplayer_connected():
            self.game.combat.events = ()
        if getattr(self.game, "player_defeated", False):
            self.game.player_defeated = False
            self._show_game_over(stop_music=False)

    def _update_field_view(self, dt):
        """The camera following the player, animated tiles, effects and skeletons."""
        pt = self.game.player.get(Transform)
        last = self._last_player_xy
        velocity = (
            ((pt.x - last[0]) / dt, (pt.y - last[1]) / dt) if last is not None and dt > 0 else None
        )
        self._last_player_xy = (pt.x, pt.y)
        self.field_camera.update(dt, (pt.x, pt.y), velocity)
        if self.tile_view is not None:
            self.tile_view.update(dt)
        self.field_effects.sync_emitters(self.game.scene, self.game.project.assets)  # VFX-01
        self.field_effects.update(dt)
        self._skeleton_scene_runtime.update(self.game.scene, dt)

    def _field_music(self):
        """A story event's track, else the map area's own music, else the field's."""
        track = self._bgm_override
        if track is None:
            ride = self._field_ride()
            track = (ride or {}).get("music") or self.game.area_music
            track = track or self.manifest["field"].get("bgm")
        return track

    def _field_frame(self, events, dt):
        moving = self._field_input(events, dt)
        if not self._multiplayer_connected():
            with self.profiler.section("events"):
                self.game.update_events(dt)
        self._open_requested_screens()
        if self.game.mode == "field" and self._ui_mode == "field":
            self._update_field_world(dt)
        self._update_field_view(dt)
        if self.game.mode == "battle":
            self._start_battle(dt)
            return
        self._music(self._field_music())
        self._preload_battle_images()
        self._draw_field(moving)
