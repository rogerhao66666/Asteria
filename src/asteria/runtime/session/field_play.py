"""The field: the player's movement, field systems, tiles and paths, prefabs, move routes,
balloons, map rules and the field update."""

from __future__ import annotations

import random
from dataclasses import replace

from asteria.core import Transform
from asteria.core.prefab import instantiate
from asteria.gameplay import ResourcePool
from asteria.rpg import (
    RpgActorSnapshot,
)
from asteria.rpg.world.map_rules import MapRulesRuntime
from asteria.runtime.field.character_control import CharacterController2DComponent
from asteria.runtime.field.collision import CombinedQuery
from asteria.runtime.input_map import InputSnapshot
from asteria.runtime.session.field_entities import FieldEntitiesMixin
from asteria.runtime.session.field_sight import FieldSightMixin
from asteria.runtime.session.support import (
    GameSessionError,
)


class FieldPlayMixin(FieldEntitiesMixin, FieldSightMixin):
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
        from asteria.runtime.field.character_control import FACINGS, CharacterController2DComponent

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
        if source is not None and self._out_of_reach(source):
            return None  # on the bridge, or under it: out of reach of each other
        if source is not None:  # talked to while hidden: it shows itself
            from asteria.runtime.field.grid_actors import SightTrigger2DComponent

            sight = source.try_get(SightTrigger2DComponent)
            if sight is not None and sight.reveal_variable:
                self.save.event_context.set_variable(sight.reveal_variable, 2)
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
            from asteria.runtime.field.ai import FieldAISystem, SpawnSystem
            from asteria.runtime.field.collision import CollisionWorld
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
                return query if tiles is None else CombinedQuery(query, tiles)

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
            from asteria.runtime.action.combat import CombatSystem
            from asteria.runtime.field.behavior_tree import BehaviorTreeSystem
            from asteria.runtime.field.character_control import (
                CharacterControllerSystem,
                HitboxSystem,
                PlayerInputSystem,
            )
            from asteria.runtime.field.entity_actions import EntityActionSystem

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
            from asteria.runtime.action.projectiles import ProjectileSystem

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
            from asteria.runtime.action.abilities import ActionCombatSystem

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
            from asteria.runtime.action.ground_loot import LootSystem

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
        from asteria.runtime.field.collision import CollisionWorld
        from asteria.runtime.field.navigation import NavGrid

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
        from asteria.runtime.field.navigation import PathFollower

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

    ENTITY_ICON_PREFIX = "icon."

    # -- scripted routes, switch visibility, variable looks, kept positions -------------------
    POSITION_PREFIX = "pos."
    FACING_VARIABLE = "player.facing"  # "up" / "down" / ...: the facing as the event began
    RESPAWN_VARIABLE = "respawn.point"  # "scene id|x|y|facing" (SET_RESPAWN)

    def _story_frame(self, dt):
        """Every field frame, events running or not: routes walk, entities follow their
        visibility switch and their look variable, kept positions hold."""
        self._light_frame(dt)  # SET_LIGHT growing or shrinking
        from asteria.runtime.field.grid_actors import (
            GridMover2DComponent,
            LookByVariable2DComponent,
            SwitchVisibility2DComponent,
            look_key,
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
                def facing(entity_id):
                    if entity_id == session.player.id:
                        return session.facing
                    entity = session.scene.get_entity(entity_id)
                    mover = entity.try_get(GridMover2DComponent) if entity is not None else None
                    if mover is not None:
                        return mover.facing
                    return session.entity_facing.get(entity_id, "down")

                @staticmethod
                def set_facing(entity_id, facing):
                    session.route_home_facing.setdefault(entity_id, Host.facing(entity_id))
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
                def face_original(entity_id):
                    home = session.route_home_facing.pop(entity_id, None)
                    if home is not None:
                        Host.set_facing(entity_id, home)
                        session.route_home_facing.pop(entity_id, None)

                @staticmethod
                def has_tag(x, y, tag):
                    keys_at = session.tile_keys_at
                    return keys_at is not None and f"tag:{tag}" in keys_at(x, y)

                @staticmethod
                def play_clip(entity_id, name):
                    if name:
                        session.route_clips[entity_id] = name
                    else:
                        session.route_clips.pop(entity_id, None)

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
            look = looks_of(spec.looks).get(look_key(spec.variable, get))
            if look is None:
                continue
            from asteria.runtime.scene.components import Animator2DComponent, SpriteRenderer2D

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

    def grid_heights(self):
        """The current map's ``GridHeights`` (None while no tile map is bound)."""
        from asteria.runtime.field.grid_heights import GridHeights

        keys_at = getattr(self, "tile_keys_at", None)
        if keys_at is None:
            return None
        known = getattr(self, "_grid_heights", None)
        if known is None or known.keys_at is not keys_at:
            known = self._grid_heights = GridHeights(keys_at, over=self.height_over)
        return known

    def sprites_over_above(self):
        """Ids of the entities drawn over the map's layers above people."""
        system = self._grid_movers.get(self.scene.id)
        over = set(system.over) if system is not None else set()
        if self.player_drawn_height in self.height_over:
            over.add(self.player.id)
        return over

    def grid_movers(self):
        """The current scene's ``GridMoverSystem`` (created on first use)."""
        system = self._grid_movers.get(self.scene.id)
        if system is None:
            from asteria.runtime.field.grid_actors import GridMoverSystem

            system = self._grid_movers[self.scene.id] = GridMoverSystem(
                random.Random(f"{self.scene.id}:grid")
            )
        return system

    def _update_grid_movers(self, dt):
        """Walk the scene's grid characters (GridMover2D) a cell at a time."""
        from asteria.runtime.field.grid_actors import GridMover2DComponent

        movers = [e.id for e, _ in self.scene.query(GridMover2DComponent)]
        if not movers:
            return
        system = self.grid_movers()
        solid = self.frame_collision_world().blocking_query(exclude={self.player.id, *movers})
        tiles = self._tile_blocking.get(self.scene.id)
        walls = solid if tiles is None else CombinedQuery(solid, tiles)
        t = self.player.get(Transform)
        size = 16.0
        for _, spec in self.scene.query(GridMover2DComponent):
            size = spec.grid_size
            break
        reserved = {(int(t.x // size), int(t.y // size)), *self.grid_reserved}
        system.heights = self.grid_heights()
        system.update(self.scene, dt, walls.collides_world_point, reserved)

    def bind_map_rules(self, keys_at):
        """Apply the project's map rule set (floor damage, regions...) to the field's tiles.

        ``keys_at(x, y)`` gives the area keys at a point (see ``runtime.map_rules_field``).
        Returns the ``FieldMapRules`` (``None`` when the project defines no rule set).
        """
        self.tile_keys_at = keys_at
        from asteria.runtime.field.map_rules import FieldMapRules

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

        transform = self.player.get(Transform)
        return self.map_rules.runtime.battle_background(transform.x, transform.y)

    def damage_party(self, resource_id, amount, *, can_kill=False):
        """Floor-style damage to every active hero's saved resource; without ``can_kill`` a
        hero is left on the last point."""

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
        from asteria.runtime.field.collision import CollisionWorld

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
        from asteria.runtime.field.ai import VisibleEncounterComponent

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
