"""Action scenes (ASTERIA_SPEC section 20; D22 A8)."""

from __future__ import annotations

from .support import (  # noqa: F401 - the names the moved methods use
    BESTIARY_TAG_KINDS,
    FIELD_BODY_HEIGHT,
    WALK_PATTERN_SEQUENCE,
    WALK_ROW_BY_FACING,
    _load_manifest,
    field_player_render_size,
    walking_pattern_index,
    walking_row_index,
)


class ActionSceneMixin:
    # -- action scenes (ASTERIA_SPEC §20; D22 A8) -------------------------------------------------
    @property
    def action_hud(self):
        hud = getattr(self, "_action_hud", None)
        if hud is None:
            from asteria.runtime.action_play import ActionHud

            hud = self._action_hud = ActionHud()
        return hud

    def _action_input(self, events, dt=0.0):
        """Real-time control: the input actions drive the player's controller and abilities through
        the session."""
        if not self._multiplayer_connected():
            self.game.prepare_action_player()
        actions = dict(self.input.current.actions)
        dx, dy = self._click_move_vector(*self.input.current.movement_vector(), dt)
        if getattr(self, "_click_path", None) is not None:  # walking to a click (D85)
            for name, value in (
                ("move_left", -dx),
                ("move_right", dx),
                ("move_up", -dy),
                ("move_down", dy),
            ):
                actions[name] = max(0.0, value)
        if self._multiplayer_connected():
            self._predict_multiplayer_player(dx, dy, dt)
            self._send_multiplayer_input(dx, dy, actions)
            self._sync_multiplayer_player()
        else:
            self.game.set_field_input(actions)
        if self._multiplayer_connected() and (
            self.input.just_pressed("pickup")
            or any(event.type == self.pg.KEYDOWN and event.key == self.pg.K_g for event in events)
        ):
            import uuid

            self.multiplayer_bridge.send_command("pickup", {"operation_id": uuid.uuid4().hex})
        if self.input.just_pressed("pickup") and not self._multiplayer_connected():
            self.game.loot.pick_up_nearest(self.game.scene, self.game.player)
        if self.input.just_pressed("bag"):
            from asteria.runtime.bag_screen import BagScreen

            if (
                self._multiplayer_connected()
                and self.multiplayer_bridge.state.get("schema")
                != "asteria.multiplayer.project_state"
            ):
                from asteria.runtime.network_bag_screen import NetworkBagScreen

                self._bag_screen = NetworkBagScreen(self)
            else:
                self._bag_screen = BagScreen(self)
            self._ui_mode = "bag"
        if self.input.just_pressed("menu"):  # the skill tree (D22 A10)
            from asteria.runtime.skill_tree_screen import SkillTreeScreen

            if self._multiplayer_connected():
                from asteria.runtime.network_bag_screen import NetworkSkillTreeScreen

                self._skill_tree = NetworkSkillTreeScreen(self)
            else:
                self._skill_tree = SkillTreeScreen(self)
            self._ui_mode = "skills"
        if self.input.just_pressed("cancel"):
            self._pause_menu.index = 0
            self._ui_mode = "pause"
        if (
            not self._multiplayer_connected()
            and self.input.just_pressed("interact")
            and not self.input.just_pressed("jump")
        ):
            self.game.field_step({"interact": 1.0})
            if self.game.mode == "field":
                self.game.field_step({"interact": 0.0})
        from asteria.runtime.character_control import CharacterController2DComponent

        controller = self.game.player.try_get(CharacterController2DComponent)
        moving = controller is not None and bool(controller.intent_x or controller.intent_y)
        if controller is not None:
            self.game.set_player_facing(controller.facing)
        if moving:
            self._field_step += 1
        return moving
