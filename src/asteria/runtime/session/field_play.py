"""The field: the player's movement, field systems, tiles and paths, prefabs, move routes,
balloons, map rules and the field update."""

from __future__ import annotations

import random
from dataclasses import replace

from asteria.core import Transform
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
            return None
        trigger = self.interaction.step(
            InputSnapshot(dict(actions or {})), self.scene, self.player, self.facing
        )
        if trigger is None:
            trigger = self.touch.step(self.scene, self.player)  # doors / transfers walked into
        if trigger is None:
            return None
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

    def bind_map_rules(self, keys_at):
        """Apply the project's map rule set (floor damage, regions...) to the field's tiles.

        ``keys_at(x, y)`` gives the area keys at a point (see ``runtime.map_rules_field``).
        Returns the ``FieldMapRules`` (``None`` when the project defines no rule set).
        """
        from asteria.rpg.map_rules import MapRulesRuntime
        from asteria.runtime.map_rules_field import FieldMapRules

        sets = self.project.rpg_database.map_rule_sets
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
        if self.mode != "field" or self.event_busy:
            return None
        if self.map_rules is not None:
            self.map_rules.update(float(dt))
        if self.walkers:
            self._advance_walkers(float(dt))
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
