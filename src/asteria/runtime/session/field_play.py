"""The field: the player's movement, field systems, tiles and paths, prefabs, move routes,
balloons, map rules and the field update."""

from __future__ import annotations

import random
from dataclasses import replace

from asteria.core import Transform
from asteria.events.world_commands import WorldCommand
from asteria.rpg import (
    RpgActorSnapshot,
)
from asteria.runtime.character_control import CharacterController2DComponent
from asteria.runtime.collision import CombinedQuery
from asteria.runtime.input import InputSnapshot

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class FieldPlayMixin:
    def set_player_position(self, x, y):
        t = self.player.get(Transform)
        t.x = float(x)
        t.y = float(y)
        self.save.player_position = (t.x, t.y)
        return self.save.player_position

    def set_player_facing(self, facing):
        self.facing = str(facing)
        self.save.player_facing = self.facing
        self._turn_player_controller()
        return self.facing

    def _turn_player_controller(self):
        """A real-time scene's player controller keeps its own facing: turn it with the session's
        (a door's ``facing``, a loaded save) so the two do not disagree."""
        from asteria.runtime.character_control import FACINGS, CharacterController2DComponent

        controller = self.player.try_get(CharacterController2DComponent)
        if controller is not None and self.facing in FACINGS and controller.facing != self.facing:
            controller.facing = self.facing

    def field_step(self, actions=None):
        """Feed field input; an interaction starts its event program in the foreground runner."""
        if self.mode != "field":
            raise GameSessionError("field input unavailable outside field mode")
        if self.event_busy:
            self.interaction.observe(InputSnapshot(dict(actions or {})))
            return None
        trigger = self.interaction.step(
            InputSnapshot(dict(actions or {})), self.scene, self.player, self.facing
        )
        if trigger is None:
            trigger = self.touch.step(self.scene, self.player)  # doors / transfers walked into
        if trigger is None:
            return None
        source = self.scene.get_entity(trigger.source_entity_id)
        if source is not None and self._grid_movers.get(self.scene.id) is not None:
            t = self.player.get(Transform)
            self._grid_movers[self.scene.id].face_toward(source, t.x, t.y)
        self.events.start_trigger(trigger, replace=True)
        self.update_events(0.0)
        return trigger

    def _field_systems(self):
        """Field AI and spawn systems for the current scene (created on first use)."""
        systems = self._field_simulation.get(self.scene.id)
        if systems is None:
            from asteria.runtime.collision import CollisionWorld
            from asteria.runtime.field_ai import FieldAISystem, SpawnSystem
            from asteria.runtime.preview import build_preview_registry

            scene = self.scene

            def blocking(entity):
                # Enemies are blocked by solid colliders, not by the player they chase.
                # The world is built once per field update (start-of-frame positions).
                world = self._frame_collision_world
                if world is None:
                    with self.profiler.section("collision"):
                        world = self._frame_collision_world = CollisionWorld.from_scene(scene)
                query = world.blocking_query(exclude={entity.id, self.player.id})
                tiles = self._tile_blocking.get(scene.id)
                return query if tiles is None else _EitherBlocks(query, tiles)

            systems = (
                SpawnSystem(
                    self.project.prefabs,
                    build_preview_registry(),
                    switches=self.save.event_context.get_switch,
                    rng=random.Random(f"{scene.id}:spawn"),
                ),
                FieldAISystem(
                    blocking, rng=random.Random(f"{scene.id}:ai"), default_target_id=self.player.id
                ),
            )
            from asteria.runtime.behavior_tree import BehaviorTreeSystem
            from asteria.runtime.character_control import (
                CharacterControllerSystem,
                HitboxSystem,
                PlayerInputSystem,
            )
            from asteria.runtime.combat import CombatSystem
            from asteria.runtime.entity_actions import EntityActionSystem

            hits = HitboxSystem()
            library = self.project.gameplay_library
            # ASTERIA_SPEC §20: landed hits -> damage, poise, super armor, knockdown, knockback,
            # hitstop, death, drops
            combat = CombatSystem(
                library.attacks,
                hits=hits,
                formulas=library.formulas,
                drop_tables=self.project.rpg_database.drop_tables,
                rng=random.Random(f"{scene.id}:combat"),
                counters=self.world.counters,  # drop table pity is saved with the world state
                switches=self.save.event_context.get_switch,
                states=library.states,  # poison, burn, buffs tick in real time
                # an ActorLink entity fights with its RPG actor's build
                stats_provider=self._actor_combat_state,
            )
            combat.listeners.append(self._remember_defeat)
            combat.listeners.append(self._award_experience)
            combat.listeners.append(self._player_fell)
            combat.protected.add(
                self.player.id
            )  # the player falls and respawns; death never removes it
            from asteria.runtime.projectiles import ProjectileSystem

            def frame_world():
                world = self._frame_collision_world
                if world is None or world.stale:
                    with self.profiler.section("collision"):
                        world = self._frame_collision_world = CollisionWorld.from_scene(scene)
                return world

            projectiles = ProjectileSystem(
                library.projectiles,
                hits=hits,
                combat=combat,
                world=frame_world,
                paused=combat.paused,
            )
            actions = EntityActionSystem(
                hitboxes=hits, paused=combat.paused, armor=combat, projectiles=projectiles
            )
            combat.actions = actions
            from asteria.core.prefab import instantiate
            from asteria.runtime.action_combat import ActionCombatSystem

            def summon(prefab_id, x, y):
                entity = instantiate(self.project.prefabs, prefab_id, build_preview_registry())
                if not entity.has(Transform):
                    entity.add_component(Transform())
                entity.get(Transform).x, entity.get(Transform).y = x, y
                return scene.add_entity(entity)

            # ASTERIA_SPEC §20: abilities used in real time (input bindings, combos, cancels,
            # cooldowns, lock-on)
            action_combat = ActionCombatSystem(
                library.abilities,
                library.timelines,
                actions=actions,
                combat=combat,
                formulas=library.formulas,
                snapshot_provider=lambda: self.field_input,
                known_abilities=self._known_abilities,
                equipped_abilities=self._equipped_abilities,
                # the party's bag pays "item:<id>" costs of party members (potions, arrows)
                inventory=lambda e: self.save.rpg_state.inventory if self._actor_of(e) else None,
            )
            behavior = BehaviorTreeSystem(
                self.project.rpg_database.behavior_trees,  # RPG-09
                target_id=self.player.id,
                switches=self.save.event_context.get_switch,
                set_switch=self.save.event_context.set_switch,
                start_encounter=lambda encounter_id: setattr(
                    self, "_pending_tree_encounter", encounter_id
                ),
                rng=random.Random(f"{scene.id}:bt"),
                # use abilities, read hp for boss phases, probe ledges, summon (ASTERIA_SPEC §20)
                action_combat=action_combat,
                combat=combat,
                world=frame_world,
                spawn=summon,
                sight_scale=lambda: self.sight_scale,  # map areas (shadows) shorten it
            )
            from asteria.runtime.loot import LootSystem

            # ASTERIA_SPEC §35: drops become loot on the ground; picking it up puts it in the save
            loot = LootSystem(
                self.project.rpg_database,
                rng=random.Random(f"{scene.id}:loot"),
                collect=self._collect_loot,
            )
            loot.name_of = self.name_of

            def drop_loot(event):
                if event.kind == "drop":
                    data = event.data
                    loot.drop(
                        scene,
                        event.x,
                        event.y,
                        items=data.get("items"),
                        currencies=data.get("currencies"),
                        level=data.get("level", 1),
                        luck=data.get("luck", 0.0),
                    )

            combat.listeners.append(drop_loot)
            # ENG-02 / ENG-17 / ANI-05 / RPG-09: behavior trees, entity action timelines,
            # controllers, hits
            spawn, ai = systems
            systems = {
                "spawn": spawn,
                "ai": ai,
                "behavior": behavior,
                "player_input": PlayerInputSystem(
                    lambda: self.field_input
                ),  # PlayerInput2D -> controller
                "action_combat": action_combat,
                "actions": actions,
                # controllers build the frame's world after AI, keep it current as they move,
                # projectiles reuse it
                "controllers": CharacterControllerSystem(paused=combat.paused, world=frame_world),
                "hits": hits,
                "projectiles": projectiles,
                "combat": combat,
                "loot": loot,
            }
            self._field_simulation[scene.id] = systems
            self._apply_tile_blocking(scene.id)
            self._remove_defeated(scene)
        return systems

    def set_tile_blocking(self, query, scene_id=None):
        """Walls of a tile map for a scene (the current one by default): any
        ``collides_world_point`` query. Controllers, field AI and projectiles respect it."""
        scene_id = self.scene.id if scene_id is None else str(scene_id)
        if query is None:
            self._tile_blocking.pop(scene_id, None)
        else:
            self._tile_blocking[scene_id] = query
        self._apply_tile_blocking(scene_id)

    def _apply_tile_blocking(self, scene_id):
        systems = self._field_simulation.get(scene_id)
        if systems is None:
            return
        tiles = self._tile_blocking.get(scene_id)
        systems["controllers"].extra_blocking = tiles
        systems["projectiles"].tiles = tiles

    def navigation_grid(self, *, cell_size=16.0, margin=0.0, walker=None):
        """A ``NavGrid`` over the field: tiles, solid colliders and restricted areas block it.

        ``walker`` (an entity id) is left out of the colliders so it does not block itself."""
        from asteria.runtime.collision import CollisionWorld
        from asteria.runtime.navigation import NavGrid

        exclude = {self.player.id} | ({str(walker)} if walker else set())
        solids = CollisionWorld.from_scene(self.scene).blocking_query(exclude=exclude)
        parts = [self.field_tiles, solids]
        if self.map_rules is not None:
            parts.append(self.map_rules.block_query("npc"))
        bounds = self.field_bounds
        if bounds is None:
            points = [
                (e.get(Transform).x, e.get(Transform).y)
                for e in self.scene.entities()
                if e.has(Transform)
            ]
            xs, ys = [p[0] for p in points] or [0.0], [p[1] for p in points] or [0.0]
            bounds = (min(xs) - 256, min(ys) - 256, max(xs) + 256, max(ys) + 256)
        return NavGrid(
            bounds, cell_size, CombinedQuery(*parts).collides_world_point, margin=margin
        )

    def find_path(self, start, goal, *, walker=None, cell_size=16.0, margin=0.0):
        """Waypoints from ``start`` to ``goal`` around everything that blocks, or ``None``."""
        grid = self.navigation_grid(cell_size=cell_size, margin=margin, walker=walker)
        return grid.find_path(start, goal)

    def walk_to(self, entity_key, x, y, *, speed=60.0):
        """Send an entity walking to ``(x, y)`` around obstacles (cutscenes, NPCs). Returns the
        waypoints, or ``None`` when there is no way (the entity stays). While it walks the switch
        ``walk.<entity id>.done`` is off; it turns on on arrival."""
        from asteria.runtime.navigation import PathFollower

        entity = self._sequence_entity(entity_key)
        transform = entity.get(Transform)
        path = self.find_path((transform.x, transform.y), (float(x), float(y)), walker=entity.id)
        done = f"walk.{entity.id}.done"
        if path is None:
            self.walkers.pop(entity.id, None)
            self.save.event_context.set_switch(done, True)
            return None
        self.save.event_context.set_switch(done, False)
        self.walkers[entity.id] = PathFollower(path, float(speed))
        return path

    ACTOR_VARIABLE_PREFIX = "actor."

    def actor_variable(self, actor_id, name, default=0):
        """A per-actor variable (saved with the event variables as ``actor.<id>.<name>``)."""
        key = f"{self.ACTOR_VARIABLE_PREFIX}{actor_id}.{name}"
        return self.save.event_context.get_variable(key, default)

    def set_actor_variable(self, actor_id, name, value):
        if str(actor_id) not in self.project.rpg_database.actors:
            raise GameSessionError(f"unknown actor: {actor_id}")
        key = f"{self.ACTOR_VARIABLE_PREFIX}{actor_id}.{name}"
        self.save.event_context.set_variable(key, value)
        return value

    def spawn_prefab(self, prefab_id, x, y, *, name=None):
        """Create an entity from a project prefab at ``(x, y)`` in the present scene (an event
        spawner); returns the new entity's id."""
        from asteria.core.prefab import instantiate
        from asteria.runtime.preview import build_preview_registry

        if str(prefab_id) not in self.project.prefabs.ids():
            raise GameSessionError(f"unknown prefab: {prefab_id}")
        entity = instantiate(
            self.project.prefabs, str(prefab_id), build_preview_registry(), name=name
        )
        if not entity.has(Transform):
            entity.add_component(Transform())
        transform = entity.get(Transform)
        transform.x, transform.y = float(x), float(y)
        self.scene.add_entity(entity)
        return entity.id

    def copy_entity(self, entity_key, x, y, *, name=None):
        """A copy of a scene entity (every serialisable component) placed at ``(x, y)``."""
        from asteria.core import Entity
        from asteria.core.serialization import deserialize_component, serialize_component
        from asteria.runtime.preview import build_preview_registry

        source = self._sequence_entity(entity_key)
        registry = build_preview_registry()
        entity = Entity(name or source.name)
        for component in source.components():
            entity.add_component(deserialize_component(serialize_component(component), registry))
        transform = entity.get(Transform)
        transform.x, transform.y = float(x), float(y)
        self.scene.add_entity(entity)
        return entity.id

    def morph_entity(self, entity_key, prefab_id):
        """Replace an entity by a prefab instance standing where it stood (an event morph);
        returns the new entity's id."""
        source = self._sequence_entity(entity_key)
        if source is self.player:
            raise GameSessionError("the player entity cannot be morphed")
        transform = source.get(Transform)
        new_id = self.spawn_prefab(prefab_id, transform.x, transform.y, name=source.name)
        self.scene.remove_entity(source)
        return new_id

    def click_entity(self, world_x, world_y):
        """A mouse click in the field: the nearest entity whose interaction is ``click``-triggered
        and whose ``range`` reaches the point starts its event program. Returns the trigger or
        ``None``."""
        from math import hypot

        from asteria.core import world_position
        from asteria.runtime.components2d import Interaction2DComponent
        from asteria.runtime.interaction import InteractionTrigger

        if self.mode != "field" or self.event_busy:
            return None
        best = None
        for entity in self.scene.entities():
            if entity is self.player or not entity.enabled:
                continue
            interaction = entity.try_get(Interaction2DComponent)
            if (
                interaction is None
                or not interaction.enabled
                or not interaction.event_program_id
                or interaction.trigger != "click"
                or not entity.has(Transform)
            ):
                continue
            ex, ey = world_position(entity)
            distance = hypot(ex - float(world_x), ey - float(world_y))
            if distance <= interaction.range and (best is None or distance < best[0]):
                best = (distance, entity, interaction)
        if best is None:
            return None
        _distance, entity, interaction = best
        trigger = InteractionTrigger(
            entity.id, interaction.event_program_id, interaction.local_scope_id or entity.id
        )
        self.events.start_trigger(trigger, replace=True)
        self.update_events(0.0)
        return trigger

    ROUTE_DIRECTIONS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}
    BALLOONS = {
        "exclamation": "!",
        "question": "?",
        "heart": "<3",
        "music": "~",
        "anger": "#",
        "silence": "...",
        "idea": "*",
        "sweat": ";",
    }

    def move_route(self, entity_key, route, *, step=32.0, speed=60.0):
        """Walk an entity along a relative route such as ``"up 3, left 2"`` (steps of ``step``
        pixels, in a straight line - no pathfinding). Arrival turns on the switch
        ``walk.<entity id>.done`` like ``walk_to``. Returns the waypoints."""
        from asteria.runtime.navigation import PathFollower

        entity = self._sequence_entity(entity_key)
        transform = entity.get(Transform)
        x, y, waypoints = transform.x, transform.y, []
        for part in str(route).replace(";", ",").split(","):
            words = part.split()
            if not words:
                continue
            direction = self.ROUTE_DIRECTIONS.get(words[0].lower())
            if direction is None:
                raise GameSessionError(f"unknown route direction: {words[0]}")
            try:
                count = float(words[1]) if len(words) > 1 else 1.0
            except ValueError as exc:
                raise GameSessionError(f"bad route step count: {words[1]}") from exc
            x += direction[0] * count * float(step)
            y += direction[1] * count * float(step)
            waypoints.append((x, y))
        done = f"walk.{entity.id}.done"
        if not waypoints:
            self.save.event_context.set_switch(done, True)
            return []
        self.save.event_context.set_switch(done, False)
        self.walkers[entity.id] = PathFollower(waypoints, float(speed))
        return waypoints

    ENTITY_ICON_PREFIX = "icon."

    def set_entity_icon(self, entity_key, icon_id=""):
        """Keep an icon over an entity (a quest marker, a status of an NPC) until it is cleared
        with an empty ``icon_id``; saved with the event variables as ``icon.<entity id>``."""
        entity = self._sequence_entity(entity_key)
        key = f"{self.ENTITY_ICON_PREFIX}{entity.id}"
        self.save.event_context.set_variable(key, str(icon_id or ""))
        return entity.id

    def entity_icons(self):
        """``{entity id: icon id}`` of the icons now shown in the present scene."""
        prefix = self.ENTITY_ICON_PREFIX
        icons = {}
        for key, value in self.save.event_context.variables.items():
            if key.startswith(prefix) and value:
                entity = self.scene.get_entity(key[len(prefix) :])
                if entity is not None:
                    icons[entity.id] = str(value)
        return icons

    def show_balloon(self, entity_key, balloon="exclamation", *, duration_ms=1000.0):
        """A balloon over an entity (a short popup with the balloon's glyph)."""
        glyph = self.BALLOONS.get(str(balloon).lower(), str(balloon))
        self.notify(glyph, entity=entity_key, duration_ms=float(duration_ms), kind="balloon")

    def _advance_walkers(self, dt):
        for entity_id in tuple(self.walkers):
            entity = self.scene.get_entity(entity_id)
            follower = self.walkers[entity_id]
            if entity is None or not entity.has(Transform):
                del self.walkers[entity_id]
                continue
            transform = entity.get(Transform)
            transform.x, transform.y = follower.step(transform.x, transform.y, dt)
            if follower.done:
                del self.walkers[entity_id]
                self.save.event_context.set_switch(f"walk.{entity_id}.done", True)

    def _map_rules_ready(self):
        """Map rules bound to the scene the player is in (just after a transfer the new
        scene's tiles are not bound yet: the old rules must not read the new position)."""
        return (
            self.map_rules is not None
            and getattr(self, "_map_rules_scene", self.scene.id) == self.scene.id
        )

    def can_meet_wild(self):
        """Random encounters need someone to fight them: when creatures decide a battle, a
        standing creature in the party."""
        rules = self.pet_rules
        if rules is None or not rules.pets_decide_outcome:
            return True
        return any(self.pet_standing(pet) for pet in self.battle_pets())

    def step_arrived(self):
        """The player finished a step (a grid cell): roll the area's random encounter.
        Returns the encounter id started, or None."""
        if self.mode != "field" or self.event_busy or not self._map_rules_ready():
            return None
        self.map_rules.update(0.0)  # the areas of the cell just reached
        if not self.can_meet_wild():
            return None
        encounter_id = self.map_rules.roll_encounter(self._step_rng)
        if not encounter_id:
            return None
        self.start_encounter(encounter_id)
        return encounter_id

    # -- scripted routes, switch visibility, variable looks, kept positions -------------------
    POSITION_PREFIX = "pos."
    FACING_VARIABLE = "player.facing"  # "up" / "down" / ...: the facing as the event began
    RESPAWN_VARIABLE = "respawn.point"  # "scene id|x|y|facing" (SET_RESPAWN)

    def respawn_after_defeat(self):
        """The battle rules' ``defeat: respawn``: the party is healed, a share of the money is
        lost, the player goes back to the last respawn point (``SET_RESPAWN``, else where the
        game started) and the rules' ``defeat_event`` runs. Returns the money lost."""
        rules = self.rules
        self.battle = None
        self.mode = "field"
        self.events.stop()  # the event that led to the battle ends with it
        self.heal_pets()
        lost = 0.0
        currencies = self.save.rpg_state.currencies
        currency = rules.defeat_currency
        if currency and rules.defeat_currency_loss:
            have = currencies.get(currency, 0.0)
            lost = float(int(have * rules.defeat_currency_loss))
            currencies[currency] = have - lost
        point = self.save.event_context.get_variable(self.RESPAWN_VARIABLE)
        if point:
            scene_id, x, y, facing = str(point).split("|")
            x, y = float(x), float(y)
        else:
            start = self.project.game_start
            x, y = start.player_position or (None, None)
            scene_id, facing = start.scene_id or self.project.startup_scene_id, start.player_facing
        self.transfer_player(scene_id, x, y, facing=facing)
        if rules.defeat_event:
            self.events.start(rules.defeat_event)
            self.update_events(0.0)
        return lost

    def grid_route(self, entity_key, steps):
        """Walk ``entity_key`` (``"player"`` or an entity) along ``steps`` (see
        ``grid_actors.parse_step``); the switch ``route.<entity id>.done`` turns on when it is
        over, and ``route.all.done`` while no route runs. Returns the entity id."""
        entity = self._sequence_entity(entity_key)
        self.routes.start(entity.id, list(steps))
        if entity is self.player:
            self.player_story_moves += 1  # a step the player had begun is dropped
        switches = self.save.event_context
        names = {entity.id, entity.name} | ({"player"} if entity is self.player else set())
        self._route_names[entity.id] = names  # route.<id>, route.<name> and route.player
        for name in names:
            switches.set_switch(f"route.{name}.done", False)
        switches.set_switch("route.all.done", False)
        return entity.id

    def set_entity_movement(self, entity_key, behaviour="", facing=""):
        """Change how a grid character moves (``GRID_BEHAVIOURS``) and / or the way it faces;
        it starts again from where it stands."""
        from asteria.runtime.grid_actors import FACINGS, GRID_BEHAVIOURS, GridMover2DComponent

        entity = self._sequence_entity(entity_key)
        mover = entity.try_get(GridMover2DComponent)
        if mover is None:
            raise GameSessionError(f"SET_MOVEMENT: {entity.name} is not a grid character")
        if behaviour:
            if behaviour not in GRID_BEHAVIOURS:
                raise GameSessionError(f"SET_MOVEMENT: unknown behaviour {behaviour}")
            mover.behaviour = behaviour
        if facing:
            if facing not in FACINGS:
                raise GameSessionError(f"SET_MOVEMENT: unknown facing {facing}")
            mover.facing = facing
        system = self._grid_movers.get(self.scene.id)
        if system is not None:
            system.state.pop(entity.id, None)
        return entity.id

    def show_entity(self, entity_key, shown=True):
        """Show or hide an entity: one with ``SwitchVisibility2D`` turns its switch (so it stays
        so), any other is hidden until shown or the scene changes."""
        from asteria.runtime.grid_actors import SwitchVisibility2DComponent

        entity = self._sequence_entity(entity_key)
        spec = entity.try_get(SwitchVisibility2DComponent)
        if spec is not None and spec.hidden_switch:
            self.save.event_context.set_switch(spec.hidden_switch, not shown)
        else:
            (self.route_hidden.discard if shown else self.route_hidden.add)(entity.id)
        return entity.id

    def set_entity_position(self, entity_key, x, y, *, facing=None, permanent=False):
        """Put an entity on ``(x, y)`` (``None``: where it is on that axis); ``permanent``
        keeps it there whenever its scene loads (saved as ``pos.<entity id>``)."""
        entity = self._sequence_entity(entity_key)
        transform = entity.get(Transform)
        x = transform.x if x is None else float(x)
        y = transform.y if y is None else float(y)
        transform.x, transform.y = x, y
        if entity is self.player:
            self.save.player_position = (transform.x, transform.y)
            self.player_story_moves += 1
            if facing:
                self.set_player_facing(facing)
        else:
            from asteria.runtime.grid_actors import GridMover2DComponent

            mover = entity.try_get(GridMover2DComponent)
            if mover is not None and facing:
                mover.facing = str(facing)
            system = self._grid_movers.get(self.scene.id)
            if system is not None:
                system.state.pop(entity.id, None)  # it starts again from its new cell
        if permanent:
            self.save.event_context.set_variable(
                f"{self.POSITION_PREFIX}{entity.id}", f"{float(x)}|{float(y)}|{facing or ''}"
            )
        return entity.id

    def _story_frame(self, dt):
        """Every field frame, events running or not: routes walk, entities follow their
        visibility switch and their look variable, kept positions hold."""
        self._light_frame(dt)  # SET_LIGHT growing or shrinking
        from asteria.runtime.grid_actors import (
            GridMover2DComponent,
            LookByVariable2DComponent,
            SwitchVisibility2DComponent,
            looks_of,
        )

        context = self.save.event_context
        if not self.event_busy and context.get_variable(self.FACING_VARIABLE) != self.facing:
            # the facing an event starts with (it keeps it while turning the player)
            context.set_variable(self.FACING_VARIABLE, self.facing)
        if self.mode == "field" and context.get_switch(self.BATTLE_RUNNING_SWITCH):
            context.set_switch(self.BATTLE_RUNNING_SWITCH, False)  # back from a battle
        if getattr(self, "_story_scene", None) != self.scene.id:  # a scene just loaded
            self._story_scene = self.scene.id
            self.route_hidden.clear()  # hidden by a route or SHOW_ENTITY: until the scene changes
            self._forget_tile_changes()  # SET_TILE without permanent: until the scene changes
            context = self.save.event_context
            for entity in self.scene.entities():
                kept = context.get_variable(f"{self.POSITION_PREFIX}{entity.id}")
                if kept and entity.has(Transform) and entity is not self.player:
                    kept = str(kept).split("|")  # "x|y|facing"
                    t = entity.get(Transform)
                    t.x, t.y = float(kept[0]), float(kept[1])
                    mover = entity.try_get(GridMover2DComponent)
                    if mover is not None and len(kept) > 2 and kept[2]:
                        mover.facing = kept[2]
        if not self.routes.done():
            session = self

            class Host:
                @staticmethod
                def transform(entity_id):
                    entity = session.scene.get_entity(entity_id)
                    if entity is None and entity_id == session.player.id:
                        entity = session.player
                    return entity.get(Transform) if entity is not None else None

                @staticmethod
                def set_facing(entity_id, facing):
                    if entity_id == session.player.id:
                        session.set_player_facing(facing)
                        return
                    entity = session.scene.get_entity(entity_id)
                    mover = entity.try_get(GridMover2DComponent) if entity else None
                    if mover is not None:
                        mover.facing = facing

                @staticmethod
                def set_lift(entity_id, height):
                    if entity_id == session.player.id:
                        session.player_lift = height

                @staticmethod
                def set_hidden(entity_id, hidden):
                    (session.route_hidden.add if hidden else session.route_hidden.discard)(
                        entity_id
                    )

                @staticmethod
                def emote(entity_id, key):
                    session.emotes[entity_id] = (key, 1.0)

                @staticmethod
                def face_player(entity_id):
                    entity = session.scene.get_entity(entity_id)
                    if entity is None or entity is session.player:
                        return
                    there = entity.get(Transform)
                    here = session.player.get(Transform)
                    dx, dy = here.x - there.x, here.y - there.y
                    if abs(dx) >= abs(dy):
                        Host.set_facing(entity_id, "right" if dx > 0 else "left")
                    else:
                        Host.set_facing(entity_id, "down" if dy > 0 else "up")

            running = set(self.routes.routes)
            self.routes.update(dt, Host)
            for entity_id in running - set(self.routes.routes):
                for name in self._route_names.pop(entity_id, {entity_id}):
                    self.save.event_context.set_switch(f"route.{name}.done", True)
                if entity_id == self.player.id:
                    t = self.player.get(Transform)
                    self.save.player_position = (t.x, t.y)
            if self.routes.done():
                self.save.event_context.set_switch("route.all.done", True)
                system = self._grid_movers.get(self.scene.id)
                if system is not None:  # walked people start again from where they stand
                    for entity_id in running:
                        system.state.pop(entity_id, None)
        switches = self.save.event_context.get_switch
        scene = self.scene
        # hidden ones too: a switch may show them again (each entity is settled on its own, so
        # the switch-shown ones come from the component index and the rest only by the ids a
        # route or SHOW_ENTITY hid - not from a scan of the whole scene every frame)
        for entity in scene._members(SwitchVisibility2DComponent):
            if entity.destroy_requested:
                continue
            spec = entity.get(SwitchVisibility2DComponent)
            shown = not (spec.hidden_switch and switches(spec.hidden_switch))
            entity.enabled = shown and entity.id not in self.route_hidden
        for entity_id in tuple(self.route_hidden | self._story_hidden):
            entity = scene.get_entity(entity_id)
            if (
                entity is None
                or entity.destroy_requested
                or entity.has(SwitchVisibility2DComponent)
            ):
                continue
            # hidden by a route / SHOW_ENTITY only
            if entity.id in self.route_hidden and entity is not self.player:
                entity.enabled = False
                self._story_hidden.add(entity.id)
            elif entity.id in self._story_hidden:
                entity.enabled = True
                self._story_hidden.discard(entity.id)
        self.player.enabled = self.player.id not in self.route_hidden
        get = self.save.event_context.get_variable
        for entity, spec in self.scene.query(LookByVariable2DComponent):
            look = looks_of(spec.looks).get(str(get(spec.variable, "")))
            if look is None:
                continue
            from asteria.runtime.components2d import Animator2DComponent, SpriteRenderer2D

            sprite = entity.try_get(SpriteRenderer2D)
            animator = entity.try_get(Animator2DComponent)
            if sprite is not None and sprite.sprite_sheet_asset_id != look[0]:
                sprite.sprite_sheet_asset_id = look[0]
            if animator is not None and look[1] and animator.clip_set_id != look[1]:
                animator.clip_set_id = look[1]

    # -- characters that notice the player (SightTrigger2D) -----------------------------------
    SIGHT_EMOTE_SECONDS = 1.0

    def _tick_emotes(self, dt):
        for entity_id, (emote, left) in list(self.emotes.items()):
            if left - dt <= 0:
                del self.emotes[entity_id]
            else:
                self.emotes[entity_id] = (emote, left - dt)

    def check_sight(self):
        """A character with ``SightTrigger2D`` that sees the player standing in a clear line
        ahead of it notices them: its mark shows, its music plays, it walks up and then its
        interaction event starts. Returns the entity id, or None."""
        from asteria.runtime.grid_actors import (
            GridMover2DComponent,
            SightTrigger2DComponent,
            line_of_sight,
        )

        if self.mode != "field" or self.event_busy or not self.can_meet_wild():
            return None
        found = list(self.scene.query(SightTrigger2DComponent, Transform))
        if not found:
            return None
        switches = self.save.event_context.get_switch
        player = self.player.get(Transform)
        size = 16.0
        movers = self._grid_movers.get(self.scene.id)
        held = movers.held_cells() if movers is not None else set()
        tiles = self._tile_blocking.get(self.scene.id)
        for entity, sight, transform in found:
            if not entity.enabled or sight.range <= 0:
                continue
            if sight.done_switch and switches(sight.done_switch):
                continue
            mover = entity.try_get(GridMover2DComponent)
            if mover is not None:
                size = mover.grid_size
            own = (int(transform.x // size), int(transform.y // size))
            target = (int(player.x // size), int(player.y // size))
            facing = mover.facing if mover is not None else "down"

            def blocked(cell, own=own, size=size):
                if cell in held and cell != own:
                    return True
                centre = (cell[0] * size + size / 2, cell[1] * size + size / 2)
                return tiles is not None and tiles.collides_world_point(*centre)

            if line_of_sight(sight.range, facing, own, target, blocked) is None:
                continue
            self.sighting = {"entity": entity.id, "phase": "emote", "time": 0.0}
            self.emotes[entity.id] = (sight.emote or "exclamation", self.SIGHT_EMOTE_SECONDS)
            if sight.music:
                self.presentation_requests.append(
                    WorldCommand("PLAY_BGM", {"asset_id": sight.music, "temporary": True})
                )
            return entity.id
        return None

    def _advance_sighting(self, dt):
        """The noticing character's mark, its walk up to the player, then its event."""
        from asteria.runtime.grid_actors import (
            STEP,
            GridMover2DComponent,
            SightTrigger2DComponent,
        )

        state = self.sighting
        entity = self.scene.get_entity(state["entity"])
        if entity is None:
            self.sighting = None
            return
        state["time"] += dt
        if state["phase"] == "emote":
            if state["time"] < self.SIGHT_EMOTE_SECONDS:
                return
            state["phase"] = "approach"
        sight = entity.get(SightTrigger2DComponent)
        mover_spec = entity.try_get(GridMover2DComponent)
        transform = entity.get(Transform)
        player = self.player.get(Transform)
        if state["phase"] == "approach" and sight.approach and mover_spec is not None:
            system = self.grid_movers()
            system.update(self.scene, 0.0, None, ())  # make sure it is known to the system
            mover = system.state[entity.id]
            if mover.target is not None:
                system._walk(mover_spec, mover, transform, dt)
                return
            size = mover_spec.grid_size
            own = (int(transform.x // size), int(transform.y // size))
            target = (int(player.x // size), int(player.y // size))
            ox, oy = STEP.get(mover_spec.facing, (0, 1))
            distance = (target[0] - own[0]) * ox + (target[1] - own[1]) * oy
            if distance > 1:
                mover.target = (own[0] + ox, own[1] + oy)
                return
        self.sighting = None
        if mover_spec is not None:  # the two face each other
            opposite = {"up": "down", "down": "up", "left": "right", "right": "left"}
            self.set_player_facing(opposite.get(mover_spec.facing, self.facing))
        from asteria.runtime.components2d import Interaction2DComponent
        from asteria.runtime.interaction import InteractionTrigger

        interaction = entity.try_get(Interaction2DComponent)
        if interaction is not None and interaction.event_program_id:
            self.events.start_trigger(
                InteractionTrigger(
                    entity.id,
                    interaction.event_program_id,
                    interaction.local_scope_id or entity.id,
                ),
                replace=True,
            )
            self.update_events(0.0)

    def grid_movers(self):
        """The current scene's ``GridMoverSystem`` (created on first use)."""
        system = self._grid_movers.get(self.scene.id)
        if system is None:
            from asteria.runtime.grid_actors import GridMoverSystem

            system = self._grid_movers[self.scene.id] = GridMoverSystem(
                random.Random(f"{self.scene.id}:grid")
            )
        return system

    def _update_grid_movers(self, dt):
        """Walk the scene's grid characters (GridMover2D) a cell at a time."""
        from asteria.runtime.grid_actors import GridMover2DComponent

        movers = [e.id for e, _ in self.scene.query(GridMover2DComponent)]
        if not movers:
            return
        system = self.grid_movers()
        solid = self.frame_collision_world().blocking_query(exclude={self.player.id, *movers})
        tiles = self._tile_blocking.get(self.scene.id)
        walls = solid if tiles is None else _EitherBlocks(solid, tiles)
        t = self.player.get(Transform)
        size = 16.0
        for _, spec in self.scene.query(GridMover2DComponent):
            size = spec.grid_size
            break
        reserved = {(int(t.x // size), int(t.y // size)), *self.grid_reserved}
        system.update(self.scene, dt, walls.collides_world_point, reserved)

    def bind_map_rules(self, keys_at):
        """Apply the project's map rule set (floor damage, regions...) to the field's tiles.

        ``keys_at(x, y)`` gives the area keys at a point (see ``runtime.map_rules_field``).
        Returns the ``FieldMapRules`` (``None`` when the project defines no rule set).
        """
        from asteria.rpg.map_rules import MapRulesRuntime
        from asteria.runtime.map_rules_field import FieldMapRules

        sets = self.project.rpg_database.map_rule_sets
        self.area_title_shown = ""  # a new map: its area name shows again
        self._map_rules_scene = self.scene.id  # the rules read this scene's tiles only
        if not sets:
            self.map_rules = None
            return None
        ruleset = sets[sorted(sets)[0]]
        runtime = MapRulesRuntime(ruleset, keys_at, self.save.event_context.get_switch)
        self.map_rules = FieldMapRules(self, runtime)
        self._field_simulation.clear()  # enemy systems rebuild with the new restrictions
        return self.map_rules

    def _area_battle_background(self):
        """Battle background of the area under the player ("" when none names one)."""
        if self.map_rules is None:
            return ""
        from asteria.core import Transform

        transform = self.player.get(Transform)
        return self.map_rules.runtime.battle_background(transform.x, transform.y)

    def damage_party(self, resource_id, amount, *, can_kill=False):
        """Floor-style damage to every active hero's saved resource; without ``can_kill`` a
        hero is left on the last point."""

        from asteria.gameplay import ResourcePool

        state = self.save.rpg_state
        for actor_id in state.party_active_actor_ids:
            snapshot = state.actor_snapshots.get(actor_id)
            if snapshot is None:  # not fought yet: start from the actor's base
                if actor_id not in self.project.rpg_database.actors:
                    continue
                base = self._actor_runtime(actor_id)
                snapshot = RpgActorSnapshot(
                    actor_id,
                    base.stats.to_data(),
                    base.resources.to_data(),
                    base.tags.to_data(),
                    None,
                )
            resources = ResourcePool.from_data(snapshot.resources)
            if not resources.contains(resource_id):
                continue
            value = resources.get(resource_id)
            floor = value.minimum if can_kill else value.minimum + 1.0
            hurt = min(float(amount), max(0.0, value.current - floor))
            if hurt <= 0:
                continue
            resources.change(resource_id, -hurt)
            state.actor_snapshots[actor_id] = replace(snapshot, resources=resources.to_data())

    def frame_collision_world(self):
        """The frame's collision world brought up to date with the scene now (followed in
        place, or rebuilt when it cannot be): the same shapes ``CollisionWorld.from_scene``
        would read, without rebuilding the whole world every time a step asks."""
        from asteria.runtime.collision import CollisionWorld

        world = self._frame_collision_world
        with self.profiler.section("collision"):
            if world is None or not world.follow(self.scene):
                world = self._frame_collision_world = CollisionWorld.from_scene(self.scene)
        return world

    def _follow_collision_world(self):
        """Keep the frame's collision world current: updated in place when only positions or
        sizes changed (the common case), dropped - rebuilt when next asked for - otherwise."""
        world = self._frame_collision_world
        if world is not None:
            with self.profiler.section("collision"):
                if not world.follow(self.scene):
                    self._frame_collision_world = None

    def field_update(self, dt):
        """Advance field enemies and spawn zones, then start any touched visible encounter."""
        self._tick_emotes(float(dt))
        if self.mode == "field":
            self._story_frame(float(dt))
        if self.mode == "field" and self.sighting is not None:
            self._advance_sighting(float(dt))
            return None
        if self.mode != "field" or self.event_busy:
            return None
        if not self.grid_reserved and self.check_sight():
            return None
        if self._map_rules_ready():
            self.map_rules.update(float(dt))
        if self.walkers:
            self._advance_walkers(float(dt))
        self._update_grid_movers(float(dt))
        systems = self._field_systems()
        self.progression_events = []
        action = self.action_scene
        if action:
            start = self.player.get(Transform)
            self._action_spawn.setdefault(
                self.scene.id, (start.x, start.y)
            )  # where the player respawns
            if self.player_down > 0:
                self.player_down = max(0.0, self.player_down - float(dt))
                if self.player_down == 0.0:
                    self._respawn_player()
        systems["player_input"].update(self.scene, float(dt))
        with self.profiler.section("spawn"):
            systems["spawn"].update(self.scene, float(dt))
        self._follow_collision_world()
        with self.profiler.section("ai"):
            systems["ai"].update(self.scene, float(dt))
            systems["behavior"].update(self.scene, float(dt))
        self._follow_collision_world()  # the foes moved
        systems["action_combat"].update(self.scene, float(dt))
        systems["actions"].update(self.scene, float(dt))
        rules = self.map_rules
        controller = self.player.try_get(CharacterController2DComponent)
        if rules is not None and controller is not None:
            rules.shape_player_intent(controller)  # a slippery floor carries the player on
        with self.profiler.section("collision"):
            systems["controllers"].update(self.scene, float(dt))
            systems["hits"].update(self.scene, float(dt))
        if rules is not None and controller is not None:
            rules.settled(float(dt), blocked=controller.hit_wall)
        with self.profiler.section("projectiles"):
            systems["projectiles"].update(self.scene, float(dt))
        with self.profiler.section("combat"):
            systems["combat"].update(self.scene, float(dt))
        systems["loot"].update(self.scene, float(dt))
        pending = getattr(self, "_pending_tree_encounter", None)
        if pending:
            self._pending_tree_encounter = None
            self.start_encounter(pending)
            return pending
        if action:
            # action scenes fight in real time: touching an enemy is not a turn-based encounter
            return None
        struck = self._struck_encounter(systems)
        if struck:
            return struck
        return self.check_visible_encounter()

    def _struck_encounter(self, systems):
        """A field foe (VisibleEncounterComponent) hit first by the player's attack or shot
        starts its fight with the component's ``struck_opening``."""
        from asteria.runtime.field_ai import VisibleEncounterComponent

        if self.mode != "field" or self.event_busy:
            return None
        attacks = self.project.gameplay_library.attacks
        hits = (*systems["hits"].events, *systems["projectiles"].hit_events)
        for hit in hits:
            if hit.attacker_id != self.player.id or attacks.get(hit.hit_tag) is None:
                continue
            entity = self.scene.get_entity(hit.target_id)
            spec = None if entity is None else entity.try_get(VisibleEncounterComponent)
            if spec is None or not spec.encounter_id or not spec.struck_opening:
                continue
            if spec.remove_on_start:
                self.scene.remove_entity(entity)
            self.start_encounter(spec.encounter_id, opening=spec.struck_opening)
            self.struck_encounters += 1
            return spec.encounter_id
        return None

    @property
    def behavior_trees(self):
        """Behavior tree runtime (RPG-09) for the current scene; ``status`` per entity."""
        return self._field_systems()["behavior"]

    @property
    def entity_actions(self):
        """Action timelines on field entities (ANI-05) for the current scene."""
        return self._field_systems()["actions"]

    def play_action(self, entity_key, timeline_id):
        """Start a project action timeline (gameplay library) on a field entity — scripts and
        PLAY_ACTION."""
        timeline = self.project.gameplay_library.timelines.get(str(timeline_id))
        if timeline is None:
            raise GameSessionError(f"unknown action timeline {timeline_id}")
        entity = self._sequence_entity(entity_key)
        self.entity_actions.play(entity.id, timeline)
        return entity.id
