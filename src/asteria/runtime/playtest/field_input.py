"""The player's input on the field: walking, riding, pushing, tile actions, clicking to move or
talk, grid steps and ledges."""

from __future__ import annotations

from asteria.core import Transform, world_position
from asteria.presentation.screens.creature import creature_settings
from asteria.runtime.action.abilities import ActionCombatComponent
from asteria.runtime.field.character_control import CharacterController2DComponent
from asteria.runtime.field.collision import CombinedQuery, box_blocked, feet_box
from asteria.runtime.field.grid_walk import FACING_STEP, GridWalker
from asteria.runtime.scene.components import Interaction2DComponent


class FieldInputMixin:
    """The player's input on the field: walking, riding, pushing, clicking, grid steps."""

    def _field_input(self, events, dt):
        for event in events:  # clicking a picture that has an event
            if event.type == self.pg.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                if self._click_picture(*event.pos) is not None:
                    return False
                if self.game.click_entity(*self._field_world_xy(*event.pos)) is not None:
                    return False
                self._click_move_to(*event.pos)
        if self.game.cutscene_active:
            if self.game.cutscene_skippable and self.input.just_pressed("cancel"):
                self.game.skip_cutscene()
                return False
            self._dialogue_input(events)
            return False
        if self._equip_offer_input(events):
            return False
        if self._dialogue_input(events) or (
            getattr(self, "_network_event_busy", False)
            if self._multiplayer_connected()
            else self.game.event_busy
        ):
            if self._multiplayer_connected():
                self._send_multiplayer_input(0, 0, {})
            else:
                self.game.set_field_input(None)
            return False
        if (
            self.multiplayer_bridge is not None
            and not self.multiplayer_bridge.connected
            and any(
                event.type == self.pg.KEYDOWN and event.key == self.pg.K_F3 for event in events
            )
        ):
            if self.multiplayer_bridge.connect():
                self._network_predictor = None
                self._network_input_prediction_sequences.clear()
                self._network_prediction_reconciled_revision = -1
                self.multiplayer_bridge.send_input(
                    {"move_x": 0.0, "move_y": 0.0, "attack": False}, force=True
                )
                self._multiplayer_error = ""
                self._network_revision = -1
            else:
                self._multiplayer_error = self.multiplayer_bridge.error
        if self.game.action_scene:
            return self._action_input(events, dt)
        # Project input map: keyboard and gamepad (stick / d-pad) both drive movement.
        dx, dy = self._click_move_vector(*self.input.current.movement_vector(), dt)
        moving = bool(dx or dy)
        connected = self._multiplayer_connected()
        if connected:
            self._predict_multiplayer_player(dx, dy, dt)
            self._send_multiplayer_input(dx, dy, dict(self.input.current.actions))
            self._sync_multiplayer_player()
        elif self.manifest.get("field", {}).get("movement") == "grid":
            moving = self._grid_field_step(dx, dy, dt)
        elif moving:
            mag = max(1.0, (dx * dx + dy * dy) ** 0.5)
            speed = float(self.manifest.get("field", {}).get("walk_speed", 0) or 36.0)
            pt = self.game.player.get(Transform)
            blocked = self.game.frame_collision_world().blocking_query(
                exclude={self.game.player.id}
            )
            x_range, y_range = (-120.0, 120.0), (-52.0, 52.0)
            if self.tile_view is not None:
                # a tile map: its walls block and its edge bounds the walk, the pace is a walk
                # across a screen in a few seconds

                walls = self.game._tile_blocking.get(self.game.scene.id)
                blocked = CombinedQuery(blocked, walls)
                x0, y0, x1, y1 = self.tile_view.bounds
                x_range, y_range = (x0 + 6, x1 - 6), (y0 + 6, y1 - 2)
                speed = float(self.manifest.get("field", {}).get("walk_speed", 0) or 64.0)
            feet = feet_box(self.game.player)
            nx = max(x_range[0], min(x_range[1], pt.x + dx / mag * speed * dt))
            if not box_blocked(blocked, nx, pt.y, feet):
                pt.x = nx
            ny = max(y_range[0], min(y_range[1], pt.y + dy / mag * speed * dt))
            if not box_blocked(blocked, pt.x, ny, feet):
                pt.y = ny
            self.game.save.player_position = (pt.x, pt.y)
            if abs(dx) > abs(dy):
                self.game.set_player_facing("right" if dx > 0 else "left")
            else:
                self.game.set_player_facing("down" if dy > 0 else "up")
            self._field_step += 1
        if not connected:  # a player with ActionCombat bindings strikes and shoots here too
            self.game.set_field_input(
                dict(self.input.current.actions) if self._field_abilities() else None
            )

        if self.input.just_pressed("menu") and self.settings.developer_menu:
            self._ui_mode = "build"
        if self.input.just_pressed("cancel"):
            if creature_settings(self, "field.creature_menu"):  # the game's own menu
                from asteria.runtime.creature.menu import CreatureMenuScreen

                self._creature_menu = CreatureMenuScreen(self)
                self._ui_mode = "creature_menu"
                return moving
            self._pause_menu.index = 0
            self._ui_mode = "pause"
            return moving
        if any(e.type == self.pg.KEYDOWN and e.key == self.pg.K_i for e in events):
            self.open_status_menu(back="field")
            return moving
        if any(e.type == self.pg.KEYDOWN and e.key == self.pg.K_q for e in events):
            self._quest_return = "field"
            self._ui_mode = "quests"
            return moving
        if moving and not connected and self.game.mode == "field":
            self.game.field_step({})  # doors and other triggers walked into
        # GameSessionRuntime interaction is edge-triggered. Emit release after press.
        if self.input.just_pressed("interact") and not connected:
            self.game.field_step({"interact": 1.0})
            if self.game.mode == "field":
                self.game.field_step({"interact": 0.0})
                self._tile_action()
        return moving

    def _tile_keys(self):
        """``keys_at(x, y)`` of the field's tile map (its tags and regions), or None."""
        view = self.tile_view
        if view is None:
            return None
        cache = getattr(self, "_ledge_keys", None)
        if cache is None or cache[0] is not view.tilemap:
            from asteria.runtime.field.map_rules import tile_area_keys

            cache = self._ledge_keys = (view.tilemap, tile_area_keys(view.tilemap, view.tileset))
        return cache[1]

    def _field_ride(self):
        """``field.rides``: what the player rides now, or None. Each is ``variable`` and
        ``value`` (its variable has that value while riding), and may have ``tag`` (it moves on
        tiles with that tag, walls or not, and only there), ``leave_program`` (runs when the
        player heads for free ground from such tiles), ``speed`` (world units a second) and
        ``music`` (plays instead of the area's)."""
        rides = self.manifest.get("field", {}).get("rides")
        if not rides:
            return None
        context = self.game.save.event_context
        for ride in rides:
            if context.get_variable(str(ride.get("variable", "")), 0) == ride.get("value"):
                scenes = ride.get("scenes")  # ``scenes``: it ends anywhere else (no bikes indoors)
                if scenes and self.game.scene.name not in scenes:
                    context.set_variable(str(ride["variable"]), 0)
                    return None
                return ride
        return None

    def _field_push(self, dx, dy, size, stopped):
        """``field.push``: once switch ``switch`` is on, walking into a character whose name is
        in ``names`` moves it a cell on (``sound`` plays) if the cell behind it is free."""
        rule = self.manifest.get("field", {}).get("push")
        game = self.game
        if not rule or game.event_busy or not (dx or dy) or (dx and dy):
            return False
        if not game.save.event_context.get_switch(str(rule.get("switch", ""))):
            return False
        movers = game._grid_movers.get(game.scene.id)
        if movers is None:
            return False
        names = set(rule.get("names") or ())
        transform = game.player.get(Transform)
        cell = (int(transform.x // size) + (dx > 0) - (dx < 0),
                int(transform.y // size) + (dy > 0) - (dy < 0))  # fmt: skip
        for entity_id, mover in movers.state.items():
            if mover.cell != cell or mover.target is not None:
                continue
            entity = game.scene.get_entity(entity_id)
            if entity is None or entity.name not in names:
                return False
            ahead = (cell[0] + (dx > 0) - (dx < 0), cell[1] + (dy > 0) - (dy < 0))
            if stopped((ahead[0] + 0.5) * size, (ahead[1] + 0.5) * size):
                return False
            way = "right" if dx > 0 else "left" if dx < 0 else "down" if dy > 0 else "up"
            from asteria.events import WorldCommand

            game.world_commands.dispatch(
                WorldCommand("GRID_ROUTE", {"entity": entity.name, "steps": [f"walk_{way}"]})
            )
            self._sound(rule.get("sound"))
            return True
        return False

    def _tile_action(self):
        """``field.tile_actions``: the action key on a tile with ``tag`` starts ``program``
        (when nobody there took the key), unless variable ``unless`` is ``unless_value``."""
        actions = self.manifest.get("field", {}).get("tile_actions")
        keys_at = self._tile_keys() if actions else None
        game = self.game
        if keys_at is None or game.event_busy or game.mode != "field":
            return

        size = float(self.manifest.get("field", {}).get("grid_size", 16.0))
        transform = game.player.get(Transform)
        ox, oy = FACING_STEP.get(game.facing, (0, 0))
        keys = keys_at(transform.x + ox * size, transform.y + oy * size)
        get = game.save.event_context.get_variable
        for action in actions:
            if f"tag:{action.get('tag')}" not in keys:
                continue
            if "unless" in action and get(action["unless"], 0) == action.get("unless_value"):
                continue
            game.events.start(str(action["program"]))
            game.update_events(0.0)
            return

    def _click_move_to(self, screen_x, screen_y):
        """Click to move (``InputActionMap.click_move``, D85): a left click on the map that hit
        no picture, click-event figure or menu sends the player walking there around what
        blocks it; a click on a figure the player talks to walks up to it and talks."""
        self._click_path = None
        game = self.game
        if not (self.input.input_map.mouse and self.input.input_map.click_move):
            return
        if game.mode != "field" or not self._click_move_scene():
            return
        player = game.player.get(Transform)
        goal = self._field_world_xy(screen_x, screen_y)
        target = self._click_talk_target(*goal)
        if target is not None:
            goal = (target.get(Transform).x, target.get(Transform).y)
        field = self.manifest.get("field", {})
        cell = float(field.get("grid_size", 16.0)) if field.get("movement") == "grid" else 16.0
        walker = target.id if target is not None else None  # its own collider is the goal
        path = game.find_path((player.x, player.y), goal, cell_size=cell, walker=walker)
        if path or target is not None:  # a figure already in reach is talked to at once
            points = list(path or ())[1:] or [goal]
            self._click_path = [game.scene.id, points, 0.0, None, walker]

    def _click_move_scene(self):
        """Whether a click can walk here: the field, a network game's field, and an action
        scene seen from above (a side-view platformer's player jumps instead)."""
        if not self.game.action_scene:
            return True

        controller = self.game.player.try_get(CharacterController2DComponent)
        return controller is None or controller.mode != "platformer"

    def _click_talk_target(self, world_x, world_y):
        """The figure under a click that the player talks to (an ``action`` interaction with
        an event), or None."""

        best = None
        for entity in self.game.scene.entities():
            interaction = entity.try_get(Interaction2DComponent)
            if entity is self.game.player or not entity.enabled or interaction is None:
                continue
            if not interaction.enabled or not interaction.event_program_id:
                continue
            if getattr(interaction, "trigger", "action") != "action":
                continue
            ex, ey = world_position(entity)
            distance = abs(ex - world_x) + abs(ey - world_y)
            if distance <= 16.0 and (best is None or distance < best[0]):
                best = (distance, entity)
        return best[1] if best is not None else None

    def _click_move_vector(self, dx, dy, dt):
        """The movement of this frame: the keys' (they cancel a walk), else a step along the
        clicked path toward its next waypoint; a walk that stops getting closer ends. A walk
        to a figure ends in its talking range, facing it, with the interact press."""
        walk = getattr(self, "_click_path", None)
        if dx or dy or walk is None:
            self._click_path = None
            return dx, dy
        scene, points, stuck, last, target_id = walk
        game = self.game
        player = game.player.get(Transform)
        if scene != game.scene.id or game.event_busy or game.mode != "field":
            self._click_path = None
            return 0.0, 0.0
        target = game.scene.get_entity(target_id) if target_id else None
        if target_id and self._click_talk(target, player):
            self._click_path = None
            return 0.0, 0.0
        near = max(2.0, 72.0 * dt)  # within a frame's step of a waypoint: the next one
        while points and abs(points[0][0] - player.x) + abs(points[0][1] - player.y) <= near:
            points.pop(0)
        if not points:
            self._click_path = None
            return 0.0, 0.0
        here = (round(player.x, 1), round(player.y, 1))
        walk[2] = stuck + dt if here == last else 0.0
        walk[3] = here
        if walk[2] > 0.4:  # walked into something the path did not know: stop
            self._click_path = None
            return 0.0, 0.0
        tx, ty = points[0][0] - player.x, points[0][1] - player.y
        length = max(1e-6, (tx * tx + ty * ty) ** 0.5)
        return tx / length, ty / length

    def _click_talk(self, target, player):
        """At the clicked figure (within its range, less a little): face it and press interact,
        as the key would. True when the walk is over (talked, or the figure is gone)."""

        interaction = target.try_get(Interaction2DComponent) if target is not None else None
        if interaction is None or not target.enabled:
            return True
        ex, ey = world_position(target)
        tx, ty = ex - player.x, ey - player.y
        if (tx * tx + ty * ty) ** 0.5 > max(4.0, interaction.range - 2.0):
            return False
        if abs(tx) > abs(ty):
            self.game.set_player_facing("right" if tx > 0 else "left")
        else:
            self.game.set_player_facing("down" if ty > 0 else "up")
        if self._multiplayer_connected():
            self._send_multiplayer_input(0, 0, {"interact": 1.0})
            return True
        self.game.field_step({"interact": 1.0})
        if self.game.mode == "field":
            self.game.field_step({"interact": 0.0})
        return True

    def _grid_field_step(self, dx, dy, dt):
        """``field.movement: "grid"``: a whole cell a step (runtime/field/grid_walk.py)."""

        walker = getattr(self, "_grid_walker", None)
        moves = getattr(self.game, "player_story_moves", 0)  # an event moved / turned the player
        if (
            walker is None
            or getattr(self, "_grid_walker_scene", None) != self.game.scene.id
            or getattr(self, "_grid_walker_moves", moves) != moves
        ):
            walker = self._grid_walker = GridWalker(self.manifest.get("field", {}))
            self._grid_walker_scene = self.game.scene.id
            transform = self.game.player.get(Transform)  # on a whole cell again
            size = walker.size
            transform.x = (transform.x // size) * size + size / 2
            transform.y = (transform.y // size) * size + size / 2
        self._grid_walker_moves = moves
        game = self.game
        blocked = game.frame_collision_world().blocking_query(exclude={game.player.id})
        walls = game._tile_blocking.get(game.scene.id)
        if walls is not None:
            blocked = CombinedQuery(blocked, walls)
        running = self.input.held(walker.run_action) if walker.run_action else False
        needs = self.manifest.get("field", {}).get("run_switch")  # running only once allowed
        if running and needs and not game.save.event_context.get_switch(needs):
            running = False
        transform = game.player.get(Transform)
        movers = game._grid_movers.get(game.scene.id)
        held = movers.held_cells() if movers is not None else set()
        size = walker.size

        before = walker.target

        ride = self._field_ride()
        ride_tag = f"tag:{ride['tag']}" if ride and ride.get("tag") else None
        keys_at = self._tile_keys() if ride_tag else None
        solid = game.frame_collision_world().blocking_query(exclude={game.player.id})
        leaving = []
        heights = game.grid_heights()
        if heights is not None:
            self._read_player_height(heights, transform)

        def stopped(x, y):  # a wall, or a cell a grid character stands on or walks into
            cell = (int(x // size), int(y // size))
            if movers is not None and heights is not None:
                if movers.holds_at(cell, game.player_height):
                    return True
            elif cell in held:
                return True
            if heights is not None and not ride_tag:
                here = heights.cell_of(transform.x, transform.y)
                if heights.stopped(here, cell, game.player_height):
                    return True
            if keys_at is None:
                return blocked.collides_world_point(x, y)
            if solid.collides_world_point(x, y):
                return True
            if ride_tag in keys_at(x, y):
                return False
            if not blocked.collides_world_point(x, y):
                leaving.append(cell)  # free ground ahead: the ride ends
            return True

        if walker.target is None and self._field_push(dx, dy, size, stopped):
            return
        if ride is not None and ride.get("speed"):
            running, walker.run_speed = True, float(ride["speed"])
        elif ride is None:
            walker.run_speed = float(self.manifest.get("field", {}).get("run_speed", 120.0))
        facing, moving = walker.step(
            transform,
            game.facing,
            dx,
            dy,
            dt,
            stopped,
            running=running,
            ledge=None if ride_tag else self._grid_ledge(),
        )
        if leaving and ride.get("leave_program") and not game.event_busy:
            game.events.start(str(ride["leave_program"]))
            game.update_events(0.0)
        game.player_lift = walker.lift  # the view draws a hopping player raised
        if before is not None and walker.target != before and game.mode == "field":
            # a step ended on a cell: the area there may start a random encounter
            if game.step_arrived():
                transform.x, transform.y = before  # the battle starts on that cell
                walker.target, walker.jump, walker.lift = None, None, 0.0
                game.player_lift = 0.0
        target = walker.target
        game.grid_reserved = (
            ((int(target[0] // size), int(target[1] // size)),) if target is not None else ()
        )
        if facing != game.facing:
            game.set_player_facing(facing)
        game.save.player_position = (transform.x, transform.y)
        if moving:
            self._field_step += 1
        return moving

    def _read_player_height(self, heights, transform):
        """Keep the player's height current: a step changes it by the cell's rules; anything
        further (a door, an event) puts the player on the cell's own height."""
        game = self.game
        cell = heights.cell_of(transform.x, transform.y)
        last = getattr(self, "_height_cell", None)
        if last == (game.scene.id, cell):
            return
        self._height_cell = (game.scene.id, cell)
        near = last is not None and last[0] == game.scene.id
        if near and abs(last[1][0] - cell[0]) + abs(last[1][1] - cell[1]) <= 2:
            game.player_height, game.player_drawn_height = heights.stepped(
                last[1], cell, game.player_height, game.player_drawn_height
            )
        else:
            game.player_height, game.player_drawn_height = heights.placed(cell)

    def _grid_ledge(self):
        """``ledge(x, y, facing)`` for the grid walk: the tiles there carry the tag
        ``<field.ledge_tag><facing>`` (default ``ledge_down`` ...); ``None`` without a tile map."""
        view = self.tile_view
        if view is None:
            return None
        cache = getattr(self, "_ledge_keys", None)
        if cache is None or cache[0] is not view.tilemap:
            from asteria.runtime.field.map_rules import tile_area_keys

            cache = self._ledge_keys = (view.tilemap, tile_area_keys(view.tilemap, view.tileset))
        keys_at = cache[1]
        prefix = str(self.manifest.get("field", {}).get("ledge_tag", "ledge_"))
        return lambda x, y, facing: f"tag:{prefix}{facing}" in keys_at(x, y)

    def _field_abilities(self):
        """The player carries ActionCombat bindings (a field attack in a turn-based game)."""

        combat = self.game.player.try_get(ActionCombatComponent)
        return combat is not None and combat.enabled and bool(combat.bindings.strip())
