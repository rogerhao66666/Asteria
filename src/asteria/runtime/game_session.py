from __future__ import annotations

import random
from dataclasses import dataclass, replace

from asteria.core import Transform
from asteria.core.lifecycle import LifecycleHookBus
from asteria.core.scene_transition import carry_persistent_entities
from asteria.events import EventRunner, EventScheduler, SceneEventRuntime, WorldCommandRouter
from asteria.events.timers import EventTimers
from asteria.gameplay import AbilityRegistry, AbilityRuntime, GameplaySubject
from asteria.presentation.message_codes import MessageContext, expand_message, plain_message
from asteria.rpg import (
    ActorAbilityState,
    ActorProgressionState,
    BattleAction,
    BattleRuntime,
    BattleSessionRules,
    ClassAssignment,
    EquipmentGrowthRuntime,
    EquippedItem,
    Party,
    PartyMember,
    RewardRuntime,
    RpgActorRuntime,
    RpgActorSnapshot,
    resolve_actor_build,
    roll_reward,
)
from asteria.rpg.economy import ShopRuntime
from asteria.rpg.enemies import RewardDefinition
from asteria.rpg.quests import QuestLog
from asteria.rpg.targeting import TargetRelation
from asteria.runtime.backlog import MessageBacklog
from asteria.runtime.character_control import CharacterController2DComponent
from asteria.runtime.input import InputSnapshot
from asteria.runtime.interaction import InteractionController
from asteria.runtime.world_command_handlers import (
    move_entity_to_scene,
    register_standard_world_commands,
)


class _EitherBlocks:
    """Two ``collides_world_point`` queries: a point is blocked when either blocks it."""

    def __init__(self, first, second):
        self.first, self.second = first, second

    def collides_world_point(self, x, y):
        return self.first.collides_world_point(x, y) or self.second.collides_world_point(x, y)


class GameSessionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BattleLogEntry:
    """One canonical battle fact, in order, for presentation adapters to consume.

    kinds: ``battle_started``, ``turn``, ``action``, ``gauge``, ``capture``, ``summoned``,
    ``battle_finished``.
    ``outcomes`` pairs each target with its non-mutating interaction outcome.
    """

    sequence: int
    kind: str
    member_id: str = ""
    ability_id: str = ""
    target_ids: tuple[str, ...] = ()
    outcomes: tuple = ()
    data: object = None


class GameSessionRuntime:
    """Generic Project + GameRuntimeSave integration runtime.

    This is the engine-level seam used by reference/full-play validation. It does
    not know project-specific actor, boss, job, resource, weakness or party-size
    names. Project definitions provide those rules; GameRuntimeSave provides the
    mutable player state.
    """

    def __init__(self, project, runtime_save):
        runtime_save.validate(project)
        runtime_save.rpg_state.bind_database(project.rpg_database)
        self.project = project
        self.save = runtime_save
        self._configure_inventory()
        # short messages for the field (CMP-03 popups): {"text", "entity", "duration_ms"}
        self.notices = []
        self.scene = project.scene(runtime_save.scene_id)
        self.player = self.scene.get_entity(runtime_save.player_entity_id)
        if self.player is None and runtime_save.player_entity_id:
            # saved after a transfer: bring the player from the scene the project file puts it in
            for other in project.scenes():
                entity = other.get_entity(runtime_save.player_entity_id)
                if entity is not None:
                    move_entity_to_scene(entity, other, self.scene)
                    self.player = entity
                    break
        if self.player is None:
            raise GameSessionError("saved player entity does not exist")
        self.facing = runtime_save.player_facing
        self._turn_player_controller()  # a loaded save faces the way it was saved
        if runtime_save.player_position is not None:
            transform = self.player.get(Transform)
            transform.x, transform.y = runtime_save.player_position
        self.interaction = InteractionController(action="interact")
        from .interaction import TouchTriggerController

        self.touch = TouchTriggerController()
        self.touch.arm(self.scene, self.player)
        self.mode = "field"
        self.battle = None
        self.encounter_id = None
        self._enemy_ids = ()
        self._captured = set()
        self._pets_sent = set()
        self.enemy_levels = {}  # enemy member id -> level, when the project has level rules
        self._last_defeated = ()
        self.map_rules = None  # FieldMapRules, set when a tile field binds area rules
        self.field_tiles = None  # the tile field's blocking query, for pathfinding
        self.field_bounds = None  # (x0, y0, x1, y1) of the field map
        self.walkers = {}  # entity id -> PathFollower (WALK_TO)
        self.timers = EventTimers(runtime_save.event_context)
        self._localizer = None
        self._last_logged_line = None
        self.backlog = MessageBacklog(self._backlog_limit())
        self.battle_log = []
        self._log_sequence = 0
        self._logged_turn = None
        # Event programs run here: one foreground runner for interactions plus
        # the current scene's autorun/parallel scheduler.
        self.presentation_requests = []
        self.event_errors = []
        self.world_commands = register_standard_world_commands(WorldCommandRouter(), self)
        self.events = EventRunner(
            project.event_programs,
            context=runtime_save.event_context,
            world_commands=self.world_commands,
        )
        self.events.sequence_host = self
        if runtime_save.active_event is not None:
            self.events.restore(runtime_save.active_event)
        # Project-wide common events (EVT-03): autorun / parallel ones run while their switch is
        # on.
        self.common_events = EventScheduler(
            project.event_programs,
            context=runtime_save.event_context,
            world_commands=self.world_commands,
            sequence_host=self,
        )
        self.battle_events = None
        self.pending_followups = []  # event programs queued by world interactions (RPG-07)
        self.entity_facing = {}
        self.entity_animation = {}
        self.scene_events = None
        self.open_shop_id = None
        self.open_crafting_station = None
        self._field_simulation = {}
        self._tile_blocking = {}  # scene id -> tile map walls (set_tile_blocking)
        self._frame_collision_world = None
        from asteria.runtime.profiler import NullProfiler

        self.profiler = NullProfiler()
        self.field_input = None  # InputSnapshot for real-time control this frame (set_field_input)
        # real-time play with RPG actors (D22 A7): experience from defeated foes, level-ups this
        # field update
        self.action_progression = {
            "level_threshold": 1000.0,
            "ap_per_level": 2.0,
            "ability_points_per_level": 1.0,
        }
        self.progression_events = []
        self.player_down = 0.0  # seconds until the fallen player respawns (action scenes)
        self._action_spawn = {}  # scene id -> where the player respawns
        self._build_scene_events()
        # WLD-02: saved NPC state (visibility, position, flags...) and the "npc" condition source
        runtime_save.event_context.providers["npc"] = self._npc_value
        from asteria.runtime.npc_state import apply_npc_states

        apply_npc_states(self.scene, self.world, self.entity_facing)

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
            )
            from asteria.runtime.loot import LootSystem

            # ASTERIA_SPEC §35: drops become loot on the ground; picking it up puts it in the save
            loot = LootSystem(
                self.project.rpg_database,
                rng=random.Random(f"{scene.id}:loot"),
                collect=self._collect_loot,
            )

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
        from .collision import CollisionWorld, CombinedQuery
        from .navigation import NavGrid

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
        from .navigation import PathFollower

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

        from .map_rules_field import FieldMapRules

        sets = self.project.rpg_database.map_rule_sets
        if not sets:
            self.map_rules = None
            return None
        ruleset = sets[sorted(sets)[0]]
        runtime = MapRulesRuntime(ruleset, keys_at, self.save.event_context.get_switch)
        self.map_rules = FieldMapRules(self, runtime)
        self._field_simulation.clear()  # enemy systems rebuild with the new restrictions
        return self.map_rules

    def damage_party(self, resource_id, amount, *, can_kill=False):
        """Floor-style damage to every active hero's saved resource; without ``can_kill`` a
        hero is left on the last point."""
        from dataclasses import replace

        from asteria.gameplay import ResourcePool

        state = self.save.rpg_state
        for actor_id in state.party_active_actor_ids:
            snapshot = state.actor_snapshots.get(actor_id)
            if snapshot is None:  # not fought yet: start from the actor's present build
                if actor_id not in self.project.rpg_database.actors:
                    continue
                build = self.resolve_actor_build(actor_id)
                snapshot = RpgActorSnapshot(
                    actor_id,
                    build.stats.to_data(),
                    build.resources.to_data(),
                    build.tags.to_data(),
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
        self._frame_collision_world = None
        with self.profiler.section("ai"):
            systems["ai"].update(self.scene, float(dt))
            systems["behavior"].update(self.scene, float(dt))
        self._frame_collision_world = None
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
        return self.check_visible_encounter()

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

    # -- real-time play with RPG actors (ASTERIA_SPEC §20, §21; D22 A7) ---------------------------
    def _actor_of(self, entity):
        from asteria.runtime.actor_link import ActorLinkComponent

        link = entity.try_get(ActorLinkComponent)
        if link is None or link.actor_id not in self.project.rpg_database.actors:
            return None
        return link.actor_id

    def _actor_combat_state(self, entity, combatant):
        """Combat stats, resources and tags of an ActorLink entity: its actor's resolved build
        (classes, level,
        skill tree, equipment and rolled affixes)."""
        from asteria.gameplay import ResourcePool, StatBlock, TagSet
        from asteria.runtime.combat import CombatantState

        actor_id = self._actor_of(entity)
        if actor_id is None:
            return None
        build = self.resolve_actor_build(actor_id)
        return CombatantState(
            StatBlock.from_data(build.stats.to_data()),
            ResourcePool.from_data(build.resources.to_data()),
            TagSet(build.tags.values()),
        )

    def _known_abilities(self, entity):
        actor_id = self._actor_of(entity)
        return None if actor_id is None else set(self.resolve_actor_build(actor_id).abilities)

    def refresh_combatant(self, entity):
        """Rebuild an entity's combat stats (after a level-up, a new class, a skill point, an
        equipment change);
        current resource values (hp...) and running states are kept."""
        from asteria.runtime.combat import CombatantComponent

        combatant = entity.try_get(CombatantComponent)
        if combatant is None or combatant.state is None:
            return None
        old = combatant.state
        combatant.reset_state()
        new = self.combat.state(entity)
        for name in old.resources.names():
            if new.resources.contains(name):
                new.resources.set_current(
                    name, min(old.resources.current(name), new.resources.maximum(name))
                )
        new.poise, new.dead = old.poise, old.dead
        if old.states is not None:
            old.states.stats, old.states.resources, old.states.tags = (
                new.stats,
                new.resources,
                new.tags,
            )
            new.states = old.states
        return new

    def refresh_actor_combatants(self, actor_id):
        from asteria.runtime.actor_link import ActorLinkComponent

        for entity, link in self.scene.query(ActorLinkComponent):
            if link.actor_id == str(actor_id):
                self.refresh_combatant(entity)

    @property
    def combat_scene(self):
        """The current scene's ``CombatScene`` settings (``None``: a classic encounter scene)."""
        from asteria.runtime.action_play import combat_scene

        return combat_scene(self.scene)

    @property
    def action_scene(self):
        settings = self.combat_scene
        return settings is not None and settings.combat_mode == "action"

    def prepare_action_player(self):
        """In an action scene, give the player what real-time play needs and does not have yet: a
        controller (in
        the scene's view), player input, hit / hurt boxes, a combatant, ability use, a looter and
        a link to the first
        party actor (so it fights with that actor's build). Authored components are left as they
        are."""
        settings = self.combat_scene
        if settings is None or settings.combat_mode != "action":
            return
        from asteria.runtime.action_combat import ActionCombatComponent
        from asteria.runtime.actor_link import ActorLinkComponent
        from asteria.runtime.character_control import (
            CharacterController2DComponent,
            Hitbox2DComponent,
            Hurtbox2DComponent,
            PlayerInput2DComponent,
        )
        from asteria.runtime.combat import CombatantComponent
        from asteria.runtime.loot import LooterComponent

        player = self.player
        controller = player.try_get(CharacterController2DComponent)
        if controller is None:
            controller = player.add_component(CharacterController2DComponent())
            controller.speed, controller.half_width, controller.half_height = 70.0, 6.0, 8.0
            controller.coyote_time, controller.jump_buffer, controller.jump_cut = 0.1, 0.12, 0.45
        controller.mode = settings.view
        if not player.has(PlayerInput2DComponent):
            player.add_component(PlayerInput2DComponent())
        if not player.has(ActorLinkComponent) and self.save.rpg_state.party_actor_ids:
            player.add_component(
                ActorLinkComponent()
            ).actor_id = self.save.rpg_state.party_actor_ids[0]
        if not player.has(CombatantComponent):
            player.add_component(CombatantComponent()).team = "hero"
        if settings.player_life_resource:
            player.get(CombatantComponent).life_resource = settings.player_life_resource
        team = player.get(CombatantComponent).team or "hero"
        if not player.has(Hurtbox2DComponent):
            hurt = player.add_component(Hurtbox2DComponent())
            hurt.team, hurt.width, hurt.height = team, 12.0, 16.0
        if not player.has(Hitbox2DComponent):
            hit = player.add_component(Hitbox2DComponent())
            hit.team, hit.width, hit.height, hit.offset_x, hit.follow_facing = (
                team,
                24.0,
                16.0,
                14.0,
                True,
            )
        if not player.has(ActionCombatComponent):
            player.add_component(ActionCombatComponent())
        if not player.has(LooterComponent):
            player.add_component(LooterComponent())

    def _player_fell(self, event):
        if event.kind != "death" or event.target_id != self.player.id or not self.action_scene:
            return
        settings = self.combat_scene
        if settings.on_player_death == "game_over":
            self.player_defeated = True
            return
        self.player_down = max(settings.respawn_delay, 1e-6)
        from asteria.runtime.character_control import CharacterController2DComponent

        controller = self.player.try_get(CharacterController2DComponent)
        if controller is not None:
            controller.lock_control(self.player_down)

    def _respawn_player(self):
        from asteria.runtime.combat import CombatantComponent

        x, y = self._action_spawn.get(
            self.scene.id, (self.player.get(Transform).x, self.player.get(Transform).y)
        )
        self.set_player_position(x, y)
        combatant = self.player.try_get(CombatantComponent)
        if combatant is not None and combatant.state is not None:
            state = combatant.state
            state.dead = False
            state.down_phase, state.down_left = "", 0.0
            if self.combat_scene.respawn_heal:
                for name in state.resources.names():
                    state.resources.set_current(name, state.resources.maximum(name))
            self.hits.grant_invincibility(self.player.id, 1.5)

    def _remember_defeat(self, event):
        """A defeated combatant with a ``defeat_switch`` is remembered in the save."""
        name = event.data.get("defeat_switch") if event.kind == "death" else ""
        if name:
            self.save.event_context.set_switch(str(name), True)

    def _remove_defeated(self, scene):
        """Entities whose ``defeat_switch`` is on stay gone (they were beaten in an earlier
        visit or session)."""
        from asteria.runtime.combat import CombatantComponent

        for entity, combatant in list(scene.query(CombatantComponent)):
            name = combatant.defeat_switch
            if name and self.save.event_context.get_switch(str(name)):
                scene.remove_entity(entity)

    def _award_experience(self, event):
        if event.kind != "death" or not event.data.get("experience") or not event.attacker_id:
            return
        attacker = self.scene.get_entity(event.attacker_id)
        actor_id = None if attacker is None else self._actor_of(attacker)
        if actor_id is None:
            return
        result = self.grant_actor_experience(
            actor_id, event.data["experience"], **self.action_progression
        )
        self.progression_events.append({"actor_id": actor_id, **result})
        if result["levels_gained"]:
            self.refresh_actor_combatants(actor_id)

    def equip_from_bag(self, actor_id, index, slot_id=None):
        """Equip a rolled item from the equipment bag (its requirements checked against the actor's
        capabilities); whatever was in the slot goes back to the bag."""
        actor_id = str(actor_id)
        bag = self.save.rpg_state.equipment_bag
        item = bag[int(index)]
        slot_id = str(slot_id or item.equipment.slot)
        loadout = self.save.rpg_state.loadouts[actor_id]
        capabilities = self.resolve_actor_build(actor_id).capabilities
        displaced = list(loadout.equipped(slot_id))
        for _ in displaced:
            loadout.unequip(slot_id, 0)
        try:
            loadout.equip(slot_id, item, capabilities=capabilities)
        except Exception:
            for previous in displaced:
                loadout.equip(slot_id, previous, validate_requirements=False)
            raise
        bag.pop(int(index))
        bag.extend(displaced)
        self.refresh_actor_combatants(actor_id)
        return item

    def unequip_to_bag(self, actor_id, slot_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        items = list(loadout.equipped(str(slot_id)))
        if not items:
            return None
        loadout.unequip(str(slot_id), 0)
        self.save.rpg_state.equipment_bag.append(items[0])
        self.refresh_actor_combatants(actor_id)
        return items[0]

    def reset_progression(self, actor_id, graph_id=None, *, cost=None):
        """Refund every allocated skill-tree point of ``actor_id`` (one graph or all) for ``cost``
        currencies."""
        actor_id = str(actor_id)
        allocation = self.save.rpg_state.progression_allocations.get(actor_id)
        if allocation is None:
            raise GameSessionError(f"{actor_id} has no skill tree")
        currencies = self.save.rpg_state.currencies
        for currency, amount in dict(cost or {}).items():
            if currencies.get(currency, 0) < amount:
                raise GameSessionError(f"not enough {currency}")
        graphs = [str(graph_id)] if graph_id is not None else list(allocation.allocations)
        refunded = {}
        changed = True
        while changed:  # refund leaves first: a node whose dependants are gone can go next
            changed = False
            for gid in graphs:
                for node_id, rank in list(allocation.allocations[gid].items()):
                    try:
                        refund = allocation.refund(gid, node_id, rank)
                    except ValueError:
                        continue
                    for currency, amount in refund.items():
                        refunded[currency] = refunded.get(currency, 0.0) + amount
                    changed = True
        for currency, amount in dict(cost or {}).items():
            currencies[currency] = currencies.get(currency, 0) - amount
        self.refresh_actor_combatants(actor_id)
        return refunded

    @property
    def loot(self):
        """Loot on the ground (ASTERIA_SPEC §35): ``drop``, ``pick_up_nearest``, ``labels``."""
        return self._field_systems()["loot"]

    def _collect_loot(self, looter, loot, equipment):
        """A picked-up stack goes into the save: currencies, the inventory, or the equipment
        bag."""
        state = self.save.rpg_state
        if loot.kind == "currency":
            state.currencies[loot.item_id] = state.currencies.get(loot.item_id, 0) + loot.amount
            return True
        if loot.kind == "equipment":
            if equipment is None:
                return False
            state.equipment_bag.append(equipment)
            return True
        room = state.inventory.room_for(loot.item_id)
        if room is not None and room < loot.amount:
            return False  # the bag is full: it stays on the ground
        state.inventory.add(loot.item_id, loot.amount)
        return True

    def set_field_input(self, actions=None):
        """This frame's input actions for real-time control (``ActionCombat`` bindings, lock-on);
        ``None`` = none."""
        from asteria.runtime.input import InputSnapshot

        self.field_input = None if actions is None else InputSnapshot(dict(actions))

    @property
    def action_combat(self):
        """Real-time ability use (ASTERIA_SPEC §20) for the current scene: ``use``, cooldowns,
        lock-on."""
        return self._field_systems()["action_combat"]

    @property
    def combat(self):
        """Real-time combat resolution (ASTERIA_SPEC §20) for the current scene; ``combat.events``
        per update."""
        return self._field_systems()["combat"]

    @property
    def projectiles(self):
        """Projectiles in flight (ASTERIA_SPEC §20) for the current scene; ``fire`` / ``views()`` /
        ``events``."""
        return self._field_systems()["projectiles"]

    @property
    def hits(self):
        """Hitbox / hurtbox detection (ENG-17) for the current scene; ``hits.events`` per
        update."""
        return self._field_systems()["hits"]

    def check_visible_encounter(self):
        """Start the encounter of a field enemy (VisibleEncounterComponent) the player touches."""
        from asteria.runtime.field_ai import VisibleEncounterComponent, touched_encounter

        if self.mode != "field" or self.event_busy:
            return None
        entity = touched_encounter(self.scene, self.player)
        if entity is None:
            return None
        spec = entity.get(VisibleEncounterComponent)
        encounter_id = spec.encounter_id
        if spec.remove_on_start:
            self.scene.remove_entity(entity)
        self.start_encounter(encounter_id)
        return encounter_id

    def _build_scene_events(self):
        bindings = self.project.scene_event_bindings.get(self.scene.id)
        self.scene_events = (
            None
            if bindings is None
            else SceneEventRuntime.build(
                bindings,
                self.project.event_programs,
                context=self.save.event_context,
                world_commands=self.world_commands,
                sequence_host=self,
            )
        )

    @property
    def event_busy(self):
        """True while a foreground or autorun event blocks player control."""
        return (
            self.events.busy
            or (self.scene_events is not None and self.scene_events.scheduler.autorun_busy)
            or self.common_events.autorun_busy
        )

    def _all_runners(self):
        yield self.events
        if self.scene_events is not None:
            yield from self.scene_events.scheduler.runners()
        yield from self.common_events.runners()

    def _dialogue_runner(self):
        return next((r for r in self._all_runners() if r.dialogue.blocked), None)

    # -- cutscenes and the sequence host (EVT-03 / EVT-04) ------------------------------------
    @property
    def cutscene_active(self):
        """A cutscene sequence is running: hosts lock player control (and may letterbox)."""
        return any(r.cutscene for r in self._all_runners())

    @property
    def cutscene_skippable(self):
        return any(r.can_skip for r in self._all_runners())

    def skip_cutscene(self):
        """Fast-forward skippable cutscenes to their end state (moves land, world commands still
        run)."""
        skipped = sum(r.skip_sequences() for r in self._all_runners())
        self.update_events(0.0)
        return skipped

    def _sequence_entity(self, key):
        key = str(key)
        if key in ("player", "@player", self.player.id):
            return self.player
        entity = self.scene.get_entity(key) or next(
            (e for e in self.scene.entities() if e.name == key), None
        )
        if entity is None or not entity.has(Transform):
            raise GameSessionError(
                f"sequence: no entity {key} with a position in {self.scene.name}"
            )
        return entity

    def position(self, key):
        t = self._sequence_entity(key).get(Transform)
        return (t.x, t.y)

    def set_position(self, key, x, y):
        entity = self._sequence_entity(key)
        if entity is self.player:
            return self.set_player_position(x, y)
        t = entity.get(Transform)
        t.x, t.y = float(x), float(y)
        self._record_npc(entity)
        return (t.x, t.y)

    # -- NPC state (WLD-02) -----------------------------------------------------------------------
    def _record_npc(self, entity):
        from asteria.runtime.npc_state import NpcIdentity2DComponent

        identity = entity.try_get(NpcIdentity2DComponent)
        if identity is None or not identity.npc_id:
            return None
        state = self.world.npc(identity.npc_id)
        t = entity.get(Transform)
        state["scene_id"], state["position"] = self.scene.id, [t.x, t.y]
        if entity.id in self.entity_facing:
            state["facing"] = self.entity_facing[entity.id]
        return state

    def _npc_value(self, name):
        npc_id, _, key = str(name).partition(".")
        return self.world.npc_value(npc_id, key)

    def set_npc(self, npc_id, key, value):
        """Change an NPC's saved state: visible, alive, mood, stage or flag.<name>; applied to the
        scene now."""
        from asteria.runtime.npc_state import NPC_KEYS, apply_npc_states, coerce_npc_value

        key = str(key)
        state = self.world.npc(npc_id)
        if key.startswith("flag."):
            state["flags"][key[5:]] = value
        elif key in NPC_KEYS:
            state[key] = coerce_npc_value(key, value)
        else:
            raise GameSessionError(f"unknown NPC field {key}")
        apply_npc_states(self.scene, self.world, self.entity_facing)
        self.refresh_quests()
        return state

    def move_npc(self, npc_id, scene_id, x, y):
        """Relocate an NPC (possibly to another scene); it appears there when that scene is
        entered."""
        from asteria.runtime.npc_state import apply_npc_states

        if self.project.scene(str(scene_id)) is None:
            raise GameSessionError(f"unknown scene: {scene_id}")
        state = self.world.npc(npc_id)
        state["scene_id"], state["position"] = str(scene_id), [float(x), float(y)]
        apply_npc_states(self.scene, self.world, self.entity_facing)
        return state

    def set_facing(self, key, facing):
        entity = self._sequence_entity(key)
        if entity is self.player:
            return self.set_player_facing(facing)
        self.entity_facing[entity.id] = str(facing)
        self._record_npc(entity)
        return self.entity_facing[entity.id]

    def play_animation(self, key, clip):
        from asteria.runtime.components2d import Animator2DComponent

        entity = self._sequence_entity(key)
        animator = entity.try_get(Animator2DComponent)
        if animator is not None:
            animator.default_clip = str(clip)
        self.entity_animation[entity.id] = str(clip)
        return str(clip)

    # -- battle events (EVT-03) -------------------------------------------------------------------
    def _battle_hook_bus(self):
        """A fresh hook bus per battle; project lifecycle bindings on ``rpg.battle.*`` hooks run as
        battle events."""
        from asteria.events import LifecycleEventBridge

        bus = LifecycleHookBus()
        bus.subscribe(
            "rpg.battle.turn_skipped", self._turn_skipped
        )  # asleep, stunned, broken...: shown in battle
        bus.subscribe("rpg.battle.after_action", self._wear_equipment)  # durability
        bindings = [
            b
            for b in self.project.lifecycle_event_bindings
            if b.hook_name.startswith("rpg.battle.")
        ]
        self.battle_events = LifecycleEventBridge(bus, self.events, bindings) if bindings else None
        self.save.event_context.providers["battle"] = self._battle_value
        return bus

    @property
    def durability_rules(self):
        """Project equipment durability rules: the first by id, or ``None``."""
        values = self.project.rpg_database.durability_rules
        return values[sorted(values)[0]] if values else None

    def wear_equipment(self, actor_id, event):
        """Wear ``actor_id``'s gear for ``event`` (``attack``, ``hit`` ...); returns what broke."""
        rules = self.durability_rules
        loadout = self.save.rpg_state.loadouts.get(str(actor_id))
        if rules is None or loadout is None:
            return ()
        in_battle = self.mode == "battle" and str(actor_id) in self.battle.members
        before = self.resolve_actor_build(actor_id) if in_battle else None
        broke = rules.apply_wear(loadout, str(event))
        for item in broke:
            name = item.nickname or item.equipment.display_name
            self.notify(f"{name} broke!", kind="warning")
        if broke and in_battle:
            self._apply_break_to_battle(str(actor_id), before)
        return broke

    def _apply_break_to_battle(self, actor_id, before):
        """A weapon that breaks mid-battle stops helping at once: the stats and resource
        maxima it gave are taken off the fighter and the abilities it granted are blocked."""
        after = self.resolve_actor_build(actor_id)
        member = self.battle.member(actor_id)
        stats, resources = member.subject.stats, member.subject.resources
        for name in before.stats.names():
            delta = after.stats.get(name) - before.stats.get(name)
            if delta and stats.contains(name):
                stats.add(name, delta)
        for name in before.resources.names():
            if resources.contains(name) and after.resources.contains(name):
                top = resources.maximum(name) + (
                    after.resources.maximum(name) - before.resources.maximum(name)
                )
                resources.get(name).set_maximum(max(top, resources.get(name).minimum))
        lost = set(before.abilities) - set(after.abilities)
        if lost:
            self.battle.blocked_abilities.setdefault(actor_id, set()).update(lost)

    def _wear_equipment(self, event):
        if self.durability_rules is None:
            return
        data = event.data
        if not data["result"].execution_result.executed:
            return
        actor = data["actor"]
        if actor.side == "heroes":
            self.wear_equipment(actor.member_id, "attack")
        for target in data["targets"]:
            if target.side == "heroes" and target.side != actor.side:
                self.wear_equipment(target.member_id, "hit")

    def _equipped(self, actor_id, instance_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        item = next((x for x in loadout.equipped() if x.instance_id == str(instance_id)), None)
        if item is None:
            raise GameSessionError(f"{instance_id} is not equipped by {actor_id}")
        return item

    def repair_equipment(self, actor_id, instance_id, amount=None):
        """Repair an equipped item, paying the rules' price in currency; returns points fixed."""
        rules = self.durability_rules
        if rules is None:
            raise GameSessionError("the project defines no durability rules")
        item = self._equipped(actor_id, instance_id)
        currency, cost = rules.repair_cost(item, amount)
        funds = self.save.rpg_state.currencies
        if cost and funds.get(currency, 0.0) < cost:
            raise GameSessionError(f"a repair costs {cost:g} {currency}")
        points = rules.repair(item, amount)
        if cost and points:
            funds[currency] = funds.get(currency, 0.0) - cost
        return points

    def rename_equipment(self, actor_id, instance_id, name):
        """Give an equipped item a nickname of the player's choice."""
        return self._equipped(actor_id, instance_id).rename(name)

    def disassemble(self, item_id):
        """Break one ``item_id`` down by the project's disassembly recipe."""
        from asteria.rpg.disassembly import disassemble

        recipe = self.project.rpg_database.disassembly_recipes.get(str(item_id))
        if recipe is None:
            raise GameSessionError(f"{item_id} cannot be disassembled")
        state = self.save.rpg_state
        counter = self.world.add_counter("disassembly.count", 1)
        result = disassemble(
            recipe,
            state.inventory,
            state.currencies,
            random.Random(f"{item_id}:{int(counter)}:disassemble"),
        )
        if not result.done:
            raise GameSessionError(f"cannot disassemble {item_id}: {result.reason}")
        return result

    @property
    def job_point_rules(self):
        values = self.project.rpg_database.job_point_rules
        return values[sorted(values)[0]] if values else None

    def _award_job_points(self, defeated_count):
        rules = self.job_point_rules
        if rules is None:
            return {}
        state = self.save.rpg_state
        given = {}
        for actor_id in state.party_active_actor_ids:
            progress = state.actor_progression.get(actor_id)
            allocation = state.progression_allocations.get(actor_id)
            if progress is None or allocation is None:
                continue
            for balance, points in rules.award(progress.active_class_ids, defeated_count).items():
                allocation.grant(balance, points)
                given.setdefault(actor_id, {})[balance] = points
        return given

    def new_game_plus(self, rules_id=None):
        """A fresh save from the project's game start that keeps what the New Game Plus rules
        carry over from this game (the running game is left as it is)."""
        from asteria.rpg.new_game_plus import carry_over

        rules = self.project.rpg_database.new_game_plus_rules
        if not rules:
            raise GameSessionError("the project defines no New Game Plus rules")
        chosen = rules[str(rules_id) if rules_id else sorted(rules)[0]]
        self.sync_world_state()
        fresh = self.project.game_start.instantiate(self.project)
        return carry_over(chosen, self.save, fresh)

    @property
    def revealed_weaknesses(self):
        """``{(enemy kind, interaction rule id)}`` found by hitting a weakness (kept for the whole
        session)."""
        values = getattr(self, "_revealed_weaknesses", None)
        if values is None:
            values = self._revealed_weaknesses = set()
        return values

    def shield_resource(self):
        """The battle resource shown as shields: the rules' ``shield_resource_id``, else the first
        break gauge's."""
        if self.rules.shield_resource_id:
            return self.rules.shield_resource_id
        for composition_id in sorted(self.battle.gauge_compositions.definitions):
            for impact in self.battle.gauge_compositions.definitions[composition_id].impacts:
                return impact.resource_id
        return ""

    def weaknesses(self, member_id):
        """The member's weaknesses for the battle screen: ``[(label, revealed)]`` from the
        interaction rules whose
        outcome is the weakness tag and whose target tags the member carries (labels from their
        source tags)."""
        weak = self.rules.weakness_outcome_tag
        tags = self.battle.member(member_id).subject.tags
        kind = str(member_id).split(":", 1)[0]
        found = []
        for rule in self.battle.interactions.rules.values():
            if weak not in rule.outcome_tags:
                continue
            if rule.target_tags_all and not all(tags.contains(t) for t in rule.target_tags_all):
                continue
            if rule.target_tags_any and not any(tags.contains(t) for t in rule.target_tags_any):
                continue
            names = rule.source_tags_all or rule.source_tags_any or (rule.rule_id,)
            label = "/".join(n.split(".")[-1] for n in names)
            found.append((label, (kind, rule.rule_id) in self.revealed_weaknesses))
        return found

    def _turn_skipped(self, event):
        data = event.data or {}
        self._log(
            "turn_skipped",
            member_id=str(event.source),
            data={"states": tuple(data.get("blocking_states", ()))},
        )

    def _battle_value(self, name):
        """Values battle-event conditions can read: ``round``, ``hp_ratio:<member or enemy id>``,
        ``alive:<id>``."""
        battle = self.battle
        if battle is None:
            return None
        if name == "round":
            return battle.turn_queue.round_index
        kind, _, key = str(name).partition(":")
        members = [
            m
            for m in battle.members.values()
            if m.member_id == key or m.member_id.split(":", 1)[0] == key
        ]
        if kind == "alive":
            return any(battle.is_active(m) for m in members)
        if kind == "hp_ratio":
            resource = self.rules.knockout_resource_id
            for member in members:
                value = member.subject.resources.get(resource)
                return 0.0 if value.maximum == 0 else value.current / value.maximum
            return None
        raise KeyError(f"unknown battle value {name}")

    def _refresh_common_events(self):
        from asteria.events.scheduler import EventScheduleMode, ScheduledEventSpec

        desired = {}
        for common in self.project.common_events:
            if common.active(self.save.event_context):
                mode = (
                    EventScheduleMode.AUTORUN
                    if common.trigger == "autorun"
                    else EventScheduleMode.PARALLEL
                )
                spec = ScheduledEventSpec(f"common:{common.program_id}", common.program_id, mode)
                desired[spec.event_id] = spec
        for spec in self.common_events.specs():
            if spec.event_id not in desired:
                self.common_events.remove(spec.event_id)
        existing = {s.event_id for s in self.common_events.specs()}
        for event_id, spec in desired.items():
            if event_id not in existing:
                self.common_events.add(spec)

    @property
    def pending_dialogue(self):
        """The DialogueRequest or ChoiceRequest waiting for the player, if any."""
        runner = self._dialogue_runner()
        if runner is None:
            return None
        request = runner.dialogue.dialogue or runner.dialogue.choice
        line = getattr(request, "line", None)
        if line is not None and line is not self._last_logged_line:
            self._last_logged_line = line  # each line is logged once, when it first shows
            self.backlog.add(
                self.expand_message(line.speaker, plain=True),
                self.expand_message(line.text, plain=True),
            )
        return request

    # --- messages, translation and the message log ------------------------------------------
    @property
    def message_settings(self):
        values = self.project.rpg_database.message_settings
        return values[sorted(values)[0]] if values else None

    def _backlog_limit(self):
        settings = self.message_settings
        return settings.backlog_limit if settings is not None else 0

    LOCALE_VARIABLE = "locale.current"

    @property
    def localizer(self):
        """The project's translations (``rpg.localization``) at the player's chosen locale."""
        from asteria.rpg.localization import Localizer

        db = self.project.rpg_database
        settings = self.message_settings
        chosen = self.save.event_context.get_variable(self.LOCALE_VARIABLE, "")
        if self._localizer is None:
            self._localizer = Localizer(
                db.locale_tables.values(),
                default_locale=settings.default_locale if settings else "",
            )
        self._localizer.locale = str(chosen or self._localizer.default_locale)
        return self._localizer

    def set_locale(self, locale):
        if str(locale) not in self.localizer.locales():
            raise GameSessionError(f"unknown locale: {locale}")
        self.save.event_context.set_variable(self.LOCALE_VARIABLE, str(locale))
        return str(locale)

    def tr(self, key, default=None, **params):
        return self.localizer.tr(key, default, **params)

    def message_context(self):
        """What ``\\V[..]``, ``\\N[..]``, ``\\G``, ``\\M[..]`` and ``\\T[..]`` read."""
        db = self.project.rpg_database
        state = self.save.rpg_state
        settings = self.message_settings
        context = self.save.event_context
        currency = settings.currency_id if settings else "gold"

        def variable(name):
            value = context.get_variable(name)
            return None if value is None else value

        def party(index):
            ids = state.party_active_actor_ids
            actor = db.actors.get(ids[index - 1]) if 0 < index <= len(ids) else None
            return None if actor is None else actor.display_name

        def actor_name(actor_id):
            actor = db.actors.get(actor_id)
            return None if actor is None else actor.display_name

        return MessageContext(
            variable=variable,
            switch=context.get_switch,
            actor_name=actor_name,
            party_name=party,
            currency_label=(settings.currency_label if settings else "") or currency,
            currency_amount=lambda: state.currencies.get(currency, 0.0),
            macros=dict(settings.macros) if settings else None,
            translate=self.localizer.lookup,
        )

    def expand_message(self, text, *, plain=False):
        """A message with its data codes replaced; ``plain`` also drops the formatting codes."""
        if plain:
            return plain_message(text, self.message_context())
        return expand_message(text, self.message_context())

    def message_icon(self, number):
        """The icon asset for ``\\I[number]``: the project's message settings map numbers to icon
        ids; with no mapping the number is itself tried as an icon id."""
        settings = self.message_settings
        mapped = dict(settings.icons) if settings is not None else {}
        return mapped.get(str(number), "")

    def note_music_heard(self, asset_id):
        """Playing a track opens it in the music room (``music.heard.<track id>``)."""
        for track in self.project.rpg_database.music_tracks.values():
            if track.asset_id == str(asset_id):
                self.save.event_context.set_switch(f"music.heard.{track.track_id}", True)

    def acknowledge_dialogue(self):
        runner = self._dialogue_runner()
        if runner is None:
            raise GameSessionError("no dialogue is waiting")
        runner.acknowledge_dialogue()
        return self.update_events(0.0)

    def choose(self, index):
        runner = self._dialogue_runner()
        if runner is None:
            raise GameSessionError("no choice is waiting")
        selected = runner.choose(index)
        self.update_events(0.0)
        return selected

    def update_events(self, dt=0.0):
        """Advance running event programs. Failures stop that event and are kept in
        event_errors."""
        output = ()
        try:
            output = self.events.update(dt)
        except Exception as exc:
            self.event_errors.append(exc)
            self.events.stop()
        if not self.events.busy:
            self.events.clear_completed()
        if self.scene_events is not None and self.mode == "field" and not self.events.busy:
            try:
                self.scene_events.update(dt)
            except Exception as exc:
                self.event_errors.append(exc)
                self.scene_events.scheduler.stop_all()
        if self.mode == "field" and not self.events.busy:
            try:
                self._refresh_common_events()
                self.common_events.update(dt)
            except Exception as exc:
                self.event_errors.append(exc)
                self.common_events.stop_all()
        if self.mode == "field":
            for finished in self.timers.update(dt):  # event timers (TIMER_START ...)
                if finished.on_expire:
                    self.pending_followups.append(finished.on_expire)
        if self.pending_followups and not self.events.busy:
            self.events.clear_completed()
            self.events.start(self.pending_followups.pop(0))  # an interaction's follow-up event
        if self.mode == "battle" and self.battle_events is not None and not self.events.busy:
            self.battle_events.pump()  # queued battle events start once the previous one finished
        return output

    def transfer_player(self, scene_id, x=None, y=None, *, facing=None):
        """Move the player entity to another scene (or position) and switch event bindings."""
        destination = self.project.scene(str(scene_id))
        if destination is None:
            raise GameSessionError(f"unknown scene: {scene_id}")
        changed = destination is not self.scene
        previous = self.scene
        transform = move_entity_to_scene(self.player, self.scene, destination, x, y)
        if changed:
            carry_persistent_entities(previous, destination)
        self.scene = destination
        self.save.scene_id = destination.id
        self.save.player_position = (transform.x, transform.y)
        if facing:
            self.set_player_facing(facing)
        self.touch.arm(
            destination, self.player
        )  # arriving on a door must not send the player back
        if changed:
            self.interaction.reset()
            self._build_scene_events()
            from asteria.runtime.npc_state import apply_npc_states

            apply_npc_states(destination, self.world, self.entity_facing)
        return destination

    def set_active_classes(self, actor_id, class_ids):
        actor_id = str(actor_id)
        state = self.save.rpg_state.actor_progression[actor_id]
        values = tuple(dict.fromkeys(str(x) for x in class_ids))
        missing = set(values) - set(state.unlocked_class_ids)
        if missing:
            raise GameSessionError("cannot activate locked classes: " + ", ".join(sorted(missing)))
        self.save.rpg_state.actor_progression[actor_id] = ActorProgressionState(
            state.level,
            state.experience,
            points=state.points,
            unlocked_class_ids=state.unlocked_class_ids,
            active_class_ids=values,
        )
        self.refresh_actor_combatants(
            actor_id
        )  # a field combatant linked to the actor changes class now
        return values

    def set_classes(self, actor_id, class_ids, *, unlock=True):
        """Make ``class_ids`` the actor's active classes (a class shrine, a job board, a story
        event); with ``unlock`` they are unlocked first. ``actor_id`` "" = the player's actor."""
        actor_id = str(actor_id or "") or self._actor_of(self.player) or ""
        if not actor_id:
            actor_id = (self.save.rpg_state.party_actor_ids or ("",))[0]
        values = tuple(dict.fromkeys(str(x).strip() for x in class_ids if str(x).strip()))
        unknown = [x for x in values if x not in self.project.rpg_database.classes]
        if unknown:
            raise GameSessionError("unknown classes: " + ", ".join(unknown))
        state = self.ensure_actor_progression(actor_id)
        if unlock:
            unlocked = tuple(dict.fromkeys(state.unlocked_class_ids + values))
            self.save.rpg_state.actor_progression[actor_id] = ActorProgressionState(
                state.level,
                state.experience,
                points=state.points,
                unlocked_class_ids=unlocked,
                active_class_ids=state.active_class_ids,
            )
        return self.set_active_classes(actor_id, values)

    def set_active_party(self, actor_ids, placements=None):
        actor_ids = tuple(dict.fromkeys(str(x) for x in actor_ids))
        roster = set(self.save.rpg_state.party_actor_ids)
        if not set(actor_ids).issubset(roster):
            raise GameSessionError("active party must be selected from roster")
        self.save.rpg_state.party_active_actor_ids = actor_ids
        if placements is not None:
            values = {str(k): str(v) for k, v in dict(placements).items()}
            if not set(values).issubset(set(actor_ids)):
                raise GameSessionError("placements must reference active party actors")
            self.save.rpg_state.party_placements = values
        return actor_ids

    def _ability_state(self, actor_id):
        snapshot = self.save.rpg_state.actor_snapshots[str(actor_id)]
        return (
            ActorAbilityState()
            if snapshot.ability_state is None
            else ActorAbilityState.from_data(snapshot.ability_state)
        )

    def _store_ability_state(self, actor_id, state):
        actor_id = str(actor_id)
        old = self.save.rpg_state.actor_snapshots[actor_id]
        self.save.rpg_state.actor_snapshots[actor_id] = RpgActorSnapshot(
            old.actor_id, old.stats, old.resources, old.tags, state.to_data()
        )
        return state

    def learn_ability(self, actor_id, ability_id):
        ability_id = str(ability_id)
        if self.project.gameplay_library.abilities.get(ability_id) is None:
            raise KeyError(ability_id)
        state = self._ability_state(actor_id)
        state.learn(ability_id)
        self._store_ability_state(actor_id, state)
        return ability_id

    def equip_passive(self, actor_id, passive_id, *, capacity=None):
        passive_id = str(passive_id)
        if passive_id not in self.project.rpg_database.passives:
            raise KeyError(passive_id)
        state = self._ability_state(actor_id)
        if passive_id not in state.active_passives:
            cap = max(len(state.active_passives) + 1, 1) if capacity is None else int(capacity)
            state.equip_passive(passive_id, capacity=cap)
        self._store_ability_state(actor_id, state)
        return passive_id

    def allocate_progression(self, actor_id, graph_id, node_id, count=1):
        allocation = self.save.rpg_state.progression_allocations[str(actor_id)]
        result = allocation.allocate(str(graph_id), str(node_id), int(count))
        self.refresh_actor_combatants(
            actor_id
        )  # a field combatant linked to the actor fights with the new ranks
        return result

    def grant_actor_points(self, actor_id, **point_amounts):
        actor_id = str(actor_id)
        state = self.save.rpg_state.actor_progression[actor_id]
        points = dict(state.points)
        for key, amount in point_amounts.items():
            key = str(key).strip()
            amount = float(amount)
            if not key or amount < 0:
                raise ValueError("actor point grants require non-negative named amounts")
            points[key] = points.get(key, 0.0) + amount
        self.save.rpg_state.actor_progression[actor_id] = ActorProgressionState(
            state.level,
            state.experience,
            points=points,
            unlocked_class_ids=state.unlocked_class_ids,
            active_class_ids=state.active_class_ids,
        )
        allocation = self.save.rpg_state.progression_allocations.get(actor_id)
        if allocation is not None and "ap" in point_amounts:
            allocation.grant("ap", point_amounts["ap"])
        return dict(points)

    def ensure_actor_progression(self, actor_id):
        """The actor's progression record, created at level 1 with its authored classes when it
        joins later
        (a captured companion, a guest) - so every party member can level up."""
        actor_id = str(actor_id)
        records = self.save.rpg_state.actor_progression
        if actor_id not in records:
            actor = self.project.rpg_database.actors[actor_id]
            classes = tuple(a.class_id for a in actor.class_assignments)
            primary = (
                tuple(a.class_id for a in actor.class_assignments if a.role == "primary")
                or classes[:1]
            )
            records[actor_id] = ActorProgressionState(
                unlocked_class_ids=classes, active_class_ids=primary
            )
        return records[actor_id]

    def grant_actor_experience(
        self,
        actor_id,
        amount,
        *,
        level_threshold=1000.0,
        ap_per_level=2.0,
        ability_points_per_level=1.0,
    ):
        """Generic acceptance/runtime helper for actor-level progression.

        Projects choose the threshold and point vocabulary; the engine does not
        attach semantics to AP/ability_points beyond persisting named balances.
        """
        actor_id = str(actor_id)
        amount = float(amount)
        threshold = float(level_threshold)
        if amount < 0 or threshold <= 0:
            raise ValueError("experience amount must be >= 0 and threshold > 0")
        state = self.ensure_actor_progression(actor_id)
        total = state.experience + amount
        old_level = state.level
        new_level = max(old_level, int(total // threshold) + 1)
        gained = max(0, new_level - old_level)
        points = dict(state.points)
        if gained:
            points["ap"] = points.get("ap", 0.0) + gained * float(ap_per_level)
            points["ability_points"] = points.get("ability_points", 0.0) + gained * float(
                ability_points_per_level
            )
            allocation = self.save.rpg_state.progression_allocations.get(actor_id)
            if allocation is not None and ap_per_level:
                allocation.grant("ap", gained * float(ap_per_level))
        self.save.rpg_state.actor_progression[actor_id] = ActorProgressionState(
            new_level,
            total,
            points=points,
            unlocked_class_ids=state.unlocked_class_ids,
            active_class_ids=state.active_class_ids,
        )
        return {
            "old_level": old_level,
            "new_level": new_level,
            "levels_gained": gained,
            "experience": total,
            "points": dict(points),
        }

    def set_secondary_class(self, actor_id, class_id):
        actor_id = str(actor_id)
        class_id = str(class_id)
        state = self.save.rpg_state.actor_progression[actor_id]
        if class_id not in state.unlocked_class_ids:
            raise GameSessionError(f"class is locked: {class_id}")
        primary = (state.active_class_ids or state.unlocked_class_ids)[:1]
        values = tuple(dict.fromkeys((*primary, class_id)))
        return self.set_active_classes(actor_id, values[:2])

    def set_passives(self, actor_id, passive_ids, *, capacity=4):
        actor_id = str(actor_id)
        values = tuple(dict.fromkeys(str(x) for x in passive_ids))
        if len(values) > int(capacity):
            raise GameSessionError("passive loadout exceeds capacity")
        for passive_id in values:
            if passive_id not in self.project.rpg_database.passives:
                raise KeyError(passive_id)
        state = self._ability_state(actor_id)
        state.active_passives = values
        self._store_ability_state(actor_id, state)
        return values

    # -- field menus: item use and equipment from the bag (UI-01) ---------------------------------
    def use_item(self, actor_id, item_id):
        """Use a consumable on a party member outside battle (the canonical
        ``use_inventory_item``)."""
        from dataclasses import replace

        from asteria.gameplay import ResourcePool, StatBlock, TagSet
        from asteria.rpg.items import use_inventory_item

        actor_id, item_id = str(actor_id), str(item_id)
        item = self.project.rpg_database.items.get(item_id)
        snapshot = self.save.rpg_state.actor_snapshots.get(actor_id)
        if item is None or snapshot is None:
            raise GameSessionError(f"cannot use {item_id} on {actor_id}")
        stats = StatBlock.from_data(snapshot.stats)
        resources = ResourcePool.from_data(snapshot.resources)
        tags = TagSet.from_data(snapshot.tags)
        result = use_inventory_item(self.save.rpg_state.inventory, item, stats, resources, tags)
        if result.used:
            self.save.rpg_state.actor_snapshots[actor_id] = replace(
                snapshot, stats=stats.to_data(), resources=resources.to_data(), tags=tags.to_data()
            )
            self.refresh_quests()
        return result

    def equip_from_inventory(self, actor_id, equipment_id, slot_id=None):
        """Move an equipment item from the bag to a slot; whatever was there goes back to the
        bag."""
        actor_id, equipment_id = str(actor_id), str(equipment_id)
        inventory = self.save.rpg_state.inventory
        if inventory.count(equipment_id) < 1:
            raise GameSessionError(f"no {equipment_id} in the bag")
        definition = self.project.rpg_database.equipment[equipment_id]
        slot_id = slot_id or definition.slot
        loadout = self.save.rpg_state.loadouts[actor_id]
        for previous in tuple(loadout.equipped(slot_id)):
            loadout.unequip(slot_id, 0)
            inventory.add(previous.equipment.equipment_id, 1)
        instance = self.equip_definition(actor_id, equipment_id, slot_id=slot_id, replace=True)
        inventory.remove(equipment_id, 1)
        return instance

    def unequip_to_inventory(self, actor_id, slot_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        items = loadout.equipped(str(slot_id))
        if not items:
            return None
        loadout.unequip(str(slot_id), 0)
        self.save.rpg_state.inventory.add(items[0].equipment.equipment_id, 1)
        return items[0].equipment.equipment_id

    def equip_definition(self, actor_id, equipment_id, *, slot_id=None, replace=True):
        actor_id = str(actor_id)
        equipment_id = str(equipment_id)
        definition = self.project.rpg_database.equipment[equipment_id]
        slot_id = str(slot_id or definition.slot)
        loadout = self.save.rpg_state.loadouts[actor_id]
        if replace and loadout.equipped(slot_id):
            loadout.unequip(slot_id, 0)
        instance = EquippedItem(
            definition,
            instance_id=f"{equipment_id}:runtime:{actor_id}:{len(loadout.equipped()) + 1}",
            growth=(
                EquipmentGrowthRuntime(
                    self.project.rpg_database.equipment_growth[definition.growth_id]
                )
                if definition.growth_id
                else None
            ),
        )
        rules = self.durability_rules
        if rules is not None:
            rules.ensure(instance)
        loadout.equip(slot_id, instance, validate_requirements=False)
        return instance

    def upgrade_equipment(self, actor_id, instance_id, node_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        item = next((x for x in loadout.equipped() if x.instance_id == str(instance_id)), None)
        if item is None:
            raise KeyError(instance_id)
        growth = item.ensure_growth(self.project.rpg_database.equipment_growth)
        return growth.unlock(str(node_id))

    def attach_equipment(self, actor_id, instance_id, socket_id, attachment_id):
        loadout = self.save.rpg_state.loadouts[str(actor_id)]
        item = next((x for x in loadout.equipped() if x.instance_id == str(instance_id)), None)
        if item is None:
            raise KeyError(instance_id)
        attachment = self.project.rpg_database.attachments[str(attachment_id)]
        if str(socket_id) in item.attachments:
            item.detach(str(socket_id))
        item.attach(str(socket_id), attachment)
        return attachment

    def resolve_actor_build(self, actor_id):
        actor_id = str(actor_id)
        db = self.project.rpg_database
        base = db.actors[actor_id]
        progress = self.save.rpg_state.actor_progression.get(actor_id)
        definition = base
        if progress is not None and progress.active_class_ids:
            authored = {x.class_id: x for x in base.class_assignments}
            assignments = []
            for index, class_id in enumerate(progress.active_class_ids):
                source = authored.get(class_id)
                assignments.append(
                    ClassAssignment(
                        class_id,
                        assignment_id=(
                            source.assignment_id if source else f"save:{actor_id}:{class_id}"
                        ),
                        role=(
                            source.role if source else ("primary" if index == 0 else "secondary")
                        ),
                        enabled=True,
                        priority=(source.priority if source else 10 - index),
                        progression_track_ids=(source.progression_track_ids if source else ()),
                        tags=(source.tags if source else ()),
                    )
                )
            definition = type(base)(
                base.actor_id,
                base.display_name,
                class_assignments=tuple(assignments),
                base_stats=base.base_stats,
                base_resources=base.base_resources,
                tags=base.tags,
                abilities=base.abilities,
            )
        actor = RpgActorRuntime(definition, class_definitions=db.classes)
        snapshot = self.save.rpg_state.actor_snapshots.get(actor_id)
        if snapshot is not None:
            actor.restore(snapshot)
        return resolve_actor_build(
            actor,
            progression=self.save.rpg_state.progression,
            allocations=self.save.rpg_state.progression_allocations.get(actor_id),
            loadout=self.save.rpg_state.loadouts.get(actor_id),
            passives=db.passives,
            evolution_rules=db.ability_evolutions.values(),
        )

    def _battle_subject(self, stats, resources, tags):
        """A combatant subject that can hold battle states (break, buffs...) from the project's
        state registry."""
        from asteria.gameplay import StateRuntime

        states = StateRuntime(self.project.gameplay_library.states, stats, resources, tags)
        return GameplaySubject(stats, resources, tags, states)

    @property
    def extension_rules(self):
        """Project battle extension rules (taunt, life steal...): the first by id, or ``None``."""
        values = self.project.rpg_database.battle_extension_rules
        return values[sorted(values)[0]] if values else None

    MASTERY_PREFIX = "mastery."

    def _load_mastery(self, extensions):
        """Lifetime ability uses live in the saved world counters; mastery tags follow them."""
        for key, value in self.world.counters.items():
            if key.startswith(self.MASTERY_PREFIX):
                member_id, _, ability_id = key[len(self.MASTERY_PREFIX) :].partition("|")
                extensions.mastery_uses[(member_id, ability_id)] = int(value)
        for member_id in self.battle.members:
            extensions.sync_mastery_tags(self.battle, member_id)

    def _store_mastery(self):
        extensions = None if self.battle is None else self.battle.extensions
        if extensions is None:
            return
        for (member_id, ability_id), uses in extensions.mastery_uses.items():
            if member_id in self.save.rpg_state.actor_progression:
                self.world.counters[f"{self.MASTERY_PREFIX}{member_id}|{ability_id}"] = float(uses)

    def steal(self, actor_id, target_id, *, chance_bonus=0.0):
        """Try to rob an enemy using the project's steal tables; loot goes into the bag."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        extensions = self.battle.extensions
        if extensions is None:
            raise GameSessionError("the project defines no steal tables")
        result = extensions.steal(
            self.battle,
            actor_id,
            target_id,
            self.save.rpg_state.inventory,
            random.Random(f"{self.encounter_id}:{actor_id}:{target_id}:steal"),
            chance_bonus=chance_bonus,
        )
        self._log(
            "steal",
            member_id=str(actor_id),
            target_ids=(str(target_id),),
            data={"stolen": result.stolen, "item_id": result.item_id, "reason": result.reason},
        )
        return result

    @property
    def enemy_level_rules(self):
        """Project enemy level rules (YEP EnemyLevels): the first by id, or ``None``."""
        values = self.project.rpg_database.enemy_level_rules
        return values[sorted(values)[0]] if values else None

    @property
    def difficulty(self):
        """Name of the difficulty slider setting in force (saved in the event variables)."""
        rules = self.enemy_level_rules
        chosen = self.save.event_context.get_variable(self.DIFFICULTY_VARIABLE, "")
        return str(chosen or (rules.default_difficulty if rules else ""))

    def set_difficulty(self, difficulty_id):
        rules = self.enemy_level_rules
        if rules is None or str(difficulty_id) not in {
            x.difficulty_id for x in rules.difficulties
        }:
            raise GameSessionError(f"unknown difficulty: {difficulty_id}")
        self.save.event_context.set_variable(self.DIFFICULTY_VARIABLE, str(difficulty_id))
        return str(difficulty_id)

    def _party_level(self):
        state = self.save.rpg_state
        levels = [
            int(state.actor_progression[x].level)
            for x in state.party_active_actor_ids
            if x in state.actor_progression
        ]
        return max(levels) if levels else 1

    def _scale_enemy(self, subject, member_id):
        rules = self.enemy_level_rules
        if rules is None:
            return 0
        level = rules.level_for(
            self.scene.id,
            random.Random(f"{self.scene.id}:{member_id}:level"),
            self._party_level(),
            self.difficulty or None,
        )
        rules.apply(subject, level, self.difficulty or None)
        return level

    def _actor_member(self, actor_id):
        build = self.resolve_actor_build(actor_id)
        subject = self._battle_subject(build.stats, build.resources, build.tags)
        speed = build.stats.get("speed")
        return PartyMember(
            str(actor_id),
            "heroes",
            subject,
            ability_ids=build.abilities,
            initiative=speed,
            initiative_stat="speed",
        )

    def _enemy_member(self, enemy_id, index):
        definition = self.project.rpg_database.enemies[enemy_id]
        runtime = definition.instantiate()
        subject = self._battle_subject(runtime.stats, runtime.resources, runtime.tags)
        level = self._scale_enemy(subject, f"{enemy_id}:{index}")
        speed = subject.stats.get("speed")
        if level:
            self.enemy_levels[f"{enemy_id}:{index}"] = level
        return PartyMember(
            f"{enemy_id}:{index}",
            "enemies",
            subject,
            ability_ids=definition.abilities,
            initiative=speed,
            initiative_stat="speed",
        )

    def summon(
        self, *, enemy_id=None, actor_id=None, count=1, owner_id=None, join_current_round=True
    ):
        """Bring combatants into the running battle (RPG-08): ``enemy_id`` joins the enemies (a
        boss calling
        minions), ``actor_id`` joins the heroes (a companion from the roster, e.g. one in reserve).
        ``owner_id`` makes them the owner's summons. Returns the new member ids."""
        if self.battle is None:
            raise GameSessionError("summon needs a running battle")
        if (enemy_id is None) == (actor_id is None):
            raise GameSessionError("summon needs exactly one of enemy_id or actor_id")
        battle = self.battle
        added = []
        for _ in range(max(1, int(count))):
            if enemy_id is not None:
                if str(enemy_id) not in self.project.rpg_database.enemies:
                    raise GameSessionError(f"unknown enemy: {enemy_id}")
                index = 1 + sum(1 for m in battle.members if m.split(":", 1)[0] == str(enemy_id))
                while f"{enemy_id}:{index}" in battle.members:
                    index += 1
                member = self._enemy_member(str(enemy_id), index)
            else:
                if str(actor_id) not in self.project.rpg_database.actors:
                    raise GameSessionError(f"unknown actor: {actor_id}")
                if str(actor_id) in battle.members:
                    raise GameSessionError(f"{actor_id} is already in the battle")
                member = self._actor_member(str(actor_id))
            registry = battle.ability_runtime.registry
            for (
                ability_id
            ) in member.ability_ids:  # the newcomer's abilities join the battle's registry
                definition = self.project.gameplay_library.abilities.get(ability_id)
                if definition is not None and registry.get(ability_id) is None:
                    registry.register(definition)
            battle.summon(member, owner_id=owner_id, join_current_round=join_current_round)
            added.append(member.member_id)
            self._log("summoned", member_id=member.member_id, data={"owner_id": owner_id})
        return tuple(added)

    def start_encounter(self, encounter_id):
        if self.mode != "field":
            raise GameSessionError("encounter already active")
        db = self.project.rpg_database
        encounter = db.encounters[str(encounter_id)]
        active = self.save.rpg_state.party_active_actor_ids
        heroes = tuple(self._actor_member(x) for x in active)
        enemies = []
        enemy_definition_ids = []
        serial = 0
        for member in encounter.members:
            for _ in range(member.count):
                serial += 1
                enemies.append(self._enemy_member(member.enemy_id, serial))
                enemy_definition_ids.append(member.enemy_id)

        registry = (
            AbilityRegistry()
        )  # every project ability: items, summons and granted skills can act too
        library = self.project.gameplay_library.abilities
        for ability_id in library.ids():
            registry.register(library.get(ability_id))

        scheduler = next(iter(db.battle_schedulers.values()), None)
        self.battle = BattleRuntime(
            (Party("heroes", heroes), Party("enemies", tuple(enemies))),
            AbilityRuntime(registry),
            is_active=self._is_conscious,
            resource_definitions=db.battle_resources.values(),
            interaction_rules=db.interaction_rules.values(),
            outcome_checks=db.outcome_checks.values(),
            state_policies=db.battle_state_policies.values(),
            targeting_definitions=db.battle_targeting.values(),
            objective_definitions=db.battle_objectives.values(),
            escape_rules=db.escape_rules.values(),
            scheduler_definition=scheduler,
            action_timing_definitions=db.action_timings.values(),
            action_sequence_definitions=db.action_sequences.values(),
            gauge_composition_definitions=db.gauge_compositions.values(),
            reaction_definitions=db.reactions.values(),
            enemy_ai_definitions=db.enemy_ai.values(),
            transaction_policies=db.action_transactions.values(),
            rng_seed=157,
            hooks=self._battle_hook_bus(),
            extensions=self.extension_rules,
        )
        self.opening = "normal"
        extensions = self.battle.extensions
        if extensions is not None:
            self._load_mastery(extensions)
            self.opening = extensions.roll_opening(random.Random(f"{encounter_id}:opening"))
            extensions.apply_opening(self.battle, self.opening, "heroes")
        self.encounter_id = str(encounter_id)
        self._enemy_ids = tuple(enemy_definition_ids)
        self._captured = set()
        self._pets_sent = set()
        for enemy_id in sorted(set(enemy_definition_ids)):
            self.world.note_enemy(enemy_id, "seen")
        self.mode = "battle"
        self.battle_log.clear()
        self._logged_turn = None
        self._log("battle_started", data={"encounter_id": self.encounter_id})
        return self.battle

    def notify(self, text, *, entity=None, duration_ms=1100.0, kind="info"):
        """Queue a short field message the host shows as animated text above ``entity`` (default
        the player)."""
        self.notices.append(
            {
                "text": str(text),
                "entity": entity,
                "duration_ms": float(duration_ms),
                "kind": str(kind),
            }
        )

    def drain_notices(self):
        values, self.notices = tuple(self.notices), []
        return values

    def _configure_inventory(self):
        """The project's inventory rules (RPG-01; the first by id) apply to every way items
        arrive."""
        db = self.project.rpg_database
        rules = getattr(db, "inventory_rules", {})
        chosen = rules[sorted(rules)[0]] if rules else None

        def lookup(item_id):
            return (
                db.items.get(item_id) or db.equipment.get(item_id) or db.attachments.get(item_id)
            )

        self.save.rpg_state.inventory.configure(chosen, lookup)

    @property
    def inventory_overflow(self):
        """``(item_id, amount)`` that did not fit in the bag, newest last (for "bag full"
        messages)."""
        return self.save.rpg_state.inventory.overflow

    @property
    def rules(self):
        """Project battle session rules; the first by id, or inert defaults."""
        values = self.project.rpg_database.battle_session_rules
        return values[sorted(values)[0]] if values else BattleSessionRules("default")

    def _is_conscious(self, member):
        resource = self.rules.knockout_resource_id
        if not resource or resource not in member.subject.resources.to_data()["values"]:
            return True
        return member.subject.resources.current(resource) > 0

    def ability_relation(self, ability_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        definition = self.battle.targeting.definition_for(ability_id)
        return TargetRelation.OPPONENT if definition is None else definition.relation

    def default_targets(self, actor_id, ability_id):
        """Targets a manual selection would default to, from the ability's targeting data."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        definition = self.battle.targeting.definition_for(ability_id)
        if definition is not None and definition.relation == TargetRelation.SELF:
            return (str(actor_id),)
        candidates = self.battle.targeting.candidates(actor_id, ability_id)
        maximum = 1 if definition is None else max(1, definition.maximum_targets)
        return tuple(candidates[:maximum])

    def max_boost_level(self, actor_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        rules = self.rules
        if not rules.boost_enabled:
            return 0
        available = self.battle.battle_resources.current(actor_id, rules.boost_resource_id)
        return min(rules.boost_max_level, int(available // rules.boost_cost_per_level))

    def use_ability(self, actor_id, ability_id, target_ids=None, *, boost_level=0):
        """Run one player action through project rules: targeting, boost and hit gauges.

        Each boost level spends ``boost_cost_per_level`` of the boost resource
        and repeats the action once more. Every action against opponents emits
        ``hit_trigger`` into all project gauge compositions.
        """
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        rules = self.rules
        boost_level = int(boost_level)
        if boost_level < 0 or boost_level > self.max_boost_level(actor_id):
            raise GameSessionError(f"boost level {boost_level} is not available")
        definition = self.battle.ability_runtime.registry.get(ability_id)
        if definition is not None and definition.concoct_station:
            raise GameSessionError(
                f"{ability_id} concocts: use concoct() with the chosen ingredients"
            )
        if definition is not None and ability_id in self.battle.member(actor_id).ability_ids:
            reason = self.ability_unavailable(actor_id, ability_id)
            if reason and not reason.startswith(
                ("Ready in", "Blocked by")
            ):  # those keep their own errors
                raise GameSessionError(f"{ability_id}: {reason}")
        targets = (
            tuple(target_ids)
            if target_ids is not None
            else self.default_targets(actor_id, ability_id)
        )
        if not targets:
            raise GameSessionError(f"{ability_id} has no valid targets")
        offensive = self.ability_relation(ability_id) == TargetRelation.OPPONENT
        battle_costs = dict(getattr(definition, "battle_costs", None) or {})
        if boost_level:  # boost and the ability's own battle costs come from the same gauges
            key = rules.boost_resource_id
            battle_costs[key] = (
                battle_costs.get(key, 0.0) + boost_level * rules.boost_cost_per_level
            )
        for resource_id, amount in battle_costs.items():
            have = self.battle.battle_resources.current(actor_id, resource_id)
            if have < amount:
                raise GameSessionError(f"{ability_id} needs {amount:g} {resource_id} ({have:g})")
        for resource_id, amount in (getattr(definition, "battle_costs", None) or {}).items():
            self.battle.battle_resources.spend(
                actor_id, resource_id, amount, trigger="rpg.session.ability_cost"
            )
        if boost_level:
            self.battle.battle_resources.spend(
                actor_id,
                rules.boost_resource_id,
                boost_level * rules.boost_cost_per_level,
                trigger="rpg.session.boost",
            )
        timing = self.battle.action_timing.definition_for(ability_id)
        if (
            timing.windup > 0 and rules.action_timing == "timeline"
        ):  # GP-02: the cast resolves later
            return self._begin_cast(actor_id, ability_id, targets, timing)
        ability_tags = set(getattr(definition, "tags", ()) or ())
        repeats = boost_level + 1
        if "boost.power" in ability_tags or (
            rules.boost_mode == "power" and "boost.repeat" not in ability_tags
        ):
            repeats = 1  # one stronger action: interaction rules read the boost tags
        boost_tags = ("boost", f"boost.{boost_level}") if boost_level else ()
        actor_tags = self.battle.member(actor_id).subject.tags
        added = [t for t in boost_tags if not actor_tags.contains(t)]
        for tag in added:
            actor_tags.add(tag)
        try:
            results = self._repeat_action(actor_id, ability_id, targets, offensive, repeats)
        finally:
            for tag in added:
                actor_tags.remove(tag)
        if any(getattr(r, "success", True) for r in results):
            self._after_ability(actor_id, definition, targets)
        return results

    def _after_ability(self, actor_id, definition, targets):
        """An ability's battle extras once it landed: battle resource gains (e.g. giving boost
        points to an
        ally) and world commands (e.g. SUMMON a companion)."""
        from asteria.events import WorldCommand

        if definition is None:
            return
        battle = self.battle
        side = battle.member(actor_id).side
        for gain in definition.battle_resource_gains:
            if gain["to"] == "self":
                members = (actor_id,)
            elif gain["to"] == "targets":
                members = tuple(targets)
            else:
                members = tuple(
                    m.member_id
                    for m in battle.members.values()
                    if m.side == side and battle.is_active(m)
                )
            for member_id in members:
                if battle.battle_resources.get(member_id, gain["resource"]) is not None:
                    battle.battle_resources.change(
                        member_id, gain["resource"], gain["amount"], trigger="rpg.session.gain"
                    )
                    self._log("resource_gain", member_id=str(member_id), data=dict(gain))
        for entry in definition.apply_states:
            if entry["to"] == "self":
                members = (actor_id,)
            elif entry["to"] == "targets":
                members = tuple(targets)
            else:
                members = tuple(
                    m.member_id
                    for m in battle.members.values()
                    if m.side == side and battle.is_active(m)
                )
            for member_id in members:
                if not battle.is_active(battle.member(member_id)):
                    continue
                if entry["remove"]:
                    states = battle.member(member_id).subject.states
                    if states is not None and states.get(entry["state"]) is not None:
                        states.remove(entry["state"])
                        self._log(
                            "state_removed",
                            member_id=str(member_id),
                            data={"state": entry["state"]},
                        )
                else:
                    result = battle.apply_state(entry["state"], actor_id, member_id)
                    self._log(
                        "state_applied",
                        member_id=str(member_id),
                        data={"state": entry["state"], "applied": result.applied},
                    )
        for command in definition.commands:
            first = targets[0] if targets else ""
            args = {
                k: (
                    v.replace("@actor", str(actor_id)).replace("@target", str(first))
                    if isinstance(v, str)
                    else v
                )
                for k, v in command["args"].items()
            }
            self.world_commands.dispatch(WorldCommand(command["command"], args))

    def ability_unavailable(self, actor_id, ability_id):
        """Why ``actor_id`` cannot use ``ability_id`` now ("" when it can): a blocking state, a
        cooldown,
        battle costs (boost points...), resource costs, unmet conditions (e.g. weapons it needs),
        or no
        ingredients to concoct. Menus show this as the disabled reason."""
        from asteria.gameplay.conditions import GameplayConditionContext

        battle = self.battle
        if battle is None:
            return "Not in battle"
        definition = battle.ability_runtime.registry.get(ability_id)
        if definition is None:
            return f"Unknown ability {ability_id}"
        member = battle.member(actor_id)
        availability = battle.ability_availability(actor_id, ability_id)
        if not availability.allowed:
            return "Blocked by " + ", ".join(availability.blocking_states)
        wait = battle.cooldown_remaining(actor_id, ability_id)
        if wait:
            return f"Ready in {wait} turn" + ("" if wait == 1 else "s")
        for resource_id, amount in definition.battle_costs.items():
            have = battle.battle_resources.current(actor_id, resource_id)
            if have < amount:
                return f"Needs {amount:g} {resource_id.replace('_', ' ')} (has {have:g})"
        wanted = getattr(definition, "requires_pet", "")
        if wanted:
            pet = self.active_pet()
            if pet is None or wanted not in ("any", pet.species_id):
                species = self.project.rpg_database.pet_species.get(wanted)
                return "Needs " + (species.display_name if species else "a pet")
        items = self.save.rpg_state.inventory
        for item_id, count in (getattr(definition, "requires_items", None) or {}).items():
            if items.count(item_id) < count:
                record = self.project.rpg_database.items.get(item_id)
                name = record.display_name if record is not None else item_id
                return f"Needs {name}" + (f" x{count}" if count > 1 else "")
        resources = member.subject.resources
        for cost in definition.costs:
            terms = cost.amount.terms
            if not terms or any(t.source.value != "constant" for t in terms):
                continue  # formulas reading stats: the action itself checks them
            amount = sum(t.coefficient for t in terms)
            if resources.contains(cost.resource) and resources.current(cost.resource) < amount:
                return f"Needs {amount:g} {cost.resource.replace('_', ' ')}"
        try:
            met = definition.conditions.evaluate(GameplayConditionContext(member.subject, None))
        except Exception:  # conditions about a target are checked against the chosen target
            met = True
        if not met:
            return "Needs " + describe_condition(definition.conditions)
        if definition.concoct_station and not self.concoct_ingredients(definition.concoct_station):
            return "No ingredients"
        return ""

    def concoct_ingredients(self, station):
        """Items in the bag that a recipe of ``station`` uses (what a concoct ability can pick
        from)."""
        db = self.project.rpg_database
        used = set()
        for recipe in db.composition_recipes.values():
            if recipe.station != station:
                continue
            for selection in recipe.selections:
                used.update(getattr(selection, "item_ids", ()) or ())
        inventory = self.save.rpg_state.inventory
        return tuple(sorted(i for i in used if inventory.count(i) > 0))

    def concoct(self, actor_id, ability_id, ingredients, target_ids=None, *, rng=None):
        """Use a concoct ability: the recipe of its station matching ``ingredients`` (``{slot:
        [item ids]}``)
        consumes them and its product - an item with a ``battle_ability`` - acts at once on the
        targets."""
        from asteria.rpg import CompositionRuntime

        definition = self.battle.ability_runtime.registry.require(ability_id)
        if not definition.concoct_station:
            raise GameSessionError(f"{ability_id} does not concoct")
        reason = self.ability_unavailable(actor_id, ability_id)
        if reason:
            raise GameSessionError(reason)
        recipes = [
            r
            for r in self.project.rpg_database.composition_recipes.values()
            if r.station == definition.concoct_station
        ]
        runtime = CompositionRuntime(recipes)
        recipe = runtime.resolve(ingredients)
        if recipe is None:
            raise GameSessionError("these ingredients make nothing")
        state = self.save.rpg_state
        before = {o.item_id: state.inventory.count(o.item_id) for o in recipe.outputs}
        result = runtime.craft(
            state.inventory, ingredients, station=definition.concoct_station, rng=rng
        )
        self.learn_recipe(result.recipe_id)
        made = [k for k, n in before.items() if state.inventory.count(k) > n]
        self._log(
            "concocted",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            data={"recipe": recipe.recipe_id},
        )
        if not made:
            return ()  # the recipe failed (success chance): materials are gone, nothing acts
        return self.use_battle_item(actor_id, made[0], target_ids)

    def use_battle_item(self, actor_id, item_id, target_ids=None):
        """Use an item in battle: its ``battle_ability`` runs for ``actor_id`` (targets,
        interaction rules, gauges,
        VFX); the item is consumed. Items without one apply their use effects to the target
        member."""
        from asteria.gameplay.effects import apply_effect

        item = self.project.rpg_database.items.get(str(item_id))
        if item is None:
            raise GameSessionError(f"unknown item {item_id}")
        inventory = self.save.rpg_state.inventory
        if inventory.count(item.item_id) < 1:
            raise GameSessionError(f"no {item.display_name} left")
        battle = self.battle
        if item.battle_ability:
            targets = (
                tuple(target_ids)
                if target_ids
                else self.default_targets(actor_id, item.battle_ability)
            )
            offensive = self.ability_relation(item.battle_ability) == TargetRelation.OPPONENT
            inventory.remove(item.item_id, 1)
            battle.granted_abilities = {(str(actor_id), item.battle_ability)}
            try:
                results = self._repeat_action(actor_id, item.battle_ability, targets, offensive, 1)
            finally:
                battle.granted_abilities = set()
            if any(getattr(r, "success", True) for r in results):  # its states, gains, commands
                definition = battle.ability_runtime.registry.get(item.battle_ability)
                self._after_ability(actor_id, definition, targets)
            self._log("item_used", member_id=str(actor_id), data={"item": item.item_id})
            return results
        targets = tuple(target_ids) if target_ids else (actor_id,)
        inventory.remove(item.item_id, 1)
        for target_id in targets:
            subject = battle.member(target_id).subject
            for effect in item.use_effects:
                apply_effect(effect, subject.stats, subject.resources, subject.tags)
        self._log("item_used", member_id=str(actor_id), data={"item": item.item_id})
        return ()

    # -- pets ---------------------------------------------------------------------------------
    def pets(self):
        """The owned pets (``rpg.pets.PetRecord``)."""
        return tuple(self.save.rpg_state.pets)

    def pet_species(self, pet):
        return self.project.rpg_database.pet_species.get(pet.species_id)

    def active_pet(self):
        """The pet that abilities send out: the chosen one, else the first owned."""
        state = self.save.rpg_state
        for pet in state.pets:
            if pet.instance_id == state.active_pet_id:
                return pet
        return state.pets[0] if state.pets else None

    def add_pet(self, species_id, *, level=1, nickname=""):
        from asteria.rpg.pets import PetRecord

        if species_id not in self.project.rpg_database.pet_species:
            raise GameSessionError(f"unknown pet species {species_id}")
        state = self.save.rpg_state
        taken = {p.instance_id for p in state.pets}
        serial = 1
        while f"{species_id}#{serial}" in taken:
            serial += 1
        pet = PetRecord(f"{species_id}#{serial}", species_id, nickname, level)
        state.pets.append(pet)
        if not state.active_pet_id:
            state.active_pet_id = pet.instance_id
        return pet

    def _pet(self, instance_id):
        for pet in self.save.rpg_state.pets:
            if pet.instance_id == str(instance_id):
                return pet
        raise GameSessionError(f"unknown pet {instance_id}")

    def rename_pet(self, instance_id, nickname):
        pet = self._pet(instance_id)
        pet.nickname = str(nickname or "").strip()[:24]
        return pet

    def set_active_pet(self, instance_id):
        pet = self._pet(instance_id)
        self.save.rpg_state.active_pet_id = pet.instance_id
        return pet

    def pet_stats(self, pet=None):
        """``{"pet_<stat>": value, "pet_level": n}`` of a pet (default: the active one)."""
        pet = pet or self.active_pet()
        species = self.pet_species(pet) if pet is not None else None
        if species is None:
            return {}
        values = {f"pet_{k}": v for k, v in species.stats_at(pet.level).items()}
        values["pet_level"] = float(pet.level)
        return values

    def _send_out_pet(self, actor_id, definition):
        """Before an ability that needs a pet: its stats become the user's ``pet_*`` stats, and
        the pet will share the win's experience."""
        if not getattr(definition, "requires_pet", ""):
            return
        pet = self.active_pet()
        if pet is None:
            return
        stats = self.battle.member(actor_id).subject.stats
        for name, value in self.pet_stats(pet).items():
            stats.set(name, value)
        self._pets_sent.add(pet.instance_id)

    def _pets_gain_experience(self):
        for instance_id in sorted(self._pets_sent):
            pet = next((p for p in self.save.rpg_state.pets if p.instance_id == instance_id), None)
            species = self.pet_species(pet) if pet is not None else None
            if species is None:
                continue
            gained = pet.gain(species, species.exp_per_battle)
            self._log(
                "pet_experience",
                member_id=pet.instance_id,
                data={"gained": gained, "level": pet.level, "species": pet.species_id},
            )
        self._pets_sent = set()

    def _repeat_action(self, actor_id, ability_id, targets, offensive, repeats):
        definition = self.battle.ability_runtime.registry.get(ability_id)
        self._send_out_pet(actor_id, definition)
        hits = tuple(getattr(definition, "hits", ()) or ()) or ({"tags": [], "power": 1.0},)
        results = []
        actor_tags = self.battle.member(actor_id).subject.tags
        for _ in range(repeats):
            for (
                hit
            ) in hits:  # each hit lands on its own: its damage types meet weaknesses and shields
                added = [t for t in hit["tags"] if not actor_tags.contains(t)]
                for tag in added:
                    actor_tags.add(tag)
                self.battle.action_scale = hit["power"]
                try:
                    targets = self._one_hit(actor_id, ability_id, targets, offensive, results)
                finally:
                    self.battle.action_scale = 1.0
                    for tag in added:
                        actor_tags.remove(tag)
                if not targets:
                    return tuple(results)
        return tuple(results)

    def _one_hit(self, actor_id, ability_id, targets, offensive, results):
        rules = self.rules
        if offensive:
            targets = tuple(t for t in targets if self.battle.is_active(self.battle.member(t)))
            if not targets:
                return ()
        before = self._knockout_values(targets)
        result = self.execute(actor_id, ability_id, targets)
        results.append(result)
        outcomes = (
            self._action_outcomes(actor_id, ability_id, targets, before) if offensive else ()
        )
        self._log(
            "action",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            target_ids=tuple(targets),
            outcomes=outcomes,
        )
        weak = self.rules.weakness_outcome_tag
        for target_id, outcome in outcomes:
            if (
                weak and weak in outcome.outcome_tags
            ):  # a weakness hit reveals its rule for that enemy kind
                kind = str(target_id).split(":", 1)[0]
                self.revealed_weaknesses.update((kind, r) for r in outcome.value.matched_rules)
            for composition_id in sorted(self.battle.gauge_compositions.definitions):
                gauge = self.battle.apply_gauge_impact(
                    composition_id,
                    actor_id,
                    target_id,
                    trigger=rules.hit_trigger,
                    outcome=outcome,
                )
                if getattr(gauge, "thresholds", ()):
                    self._log("gauge", member_id=str(target_id), data=gauge)
        return targets

    def current_turn_actor(self):
        """Member whose turn it is under the battle's scheduler; starts new rounds as needed."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        if not self.active_enemy_ids() or not self.active_hero_ids():
            return None
        self.resolve_casts()
        if not self.active_enemy_ids() or not self.active_hero_ids():
            return None
        actor = (
            self.battle.next_actor()
        )  # members who cannot act (asleep, broken...) are skipped there
        if actor is None:
            self.battle.start_next_round()
            actor = self.battle.next_actor()
        if actor is None:
            return None
        key = (self.battle.turn_queue.round_index, actor.member_id)
        if key != self._logged_turn:
            self._logged_turn = key
            self._log("turn", member_id=actor.member_id)
        return actor.member_id

    def turn_prevented(self, member_id):
        """States of ``member_id`` whose battle policy prevents acting (``prevent_action``); empty
        when free."""
        subject = self.battle.member(member_id).subject
        if subject.states is None:
            return ()
        policies = self.battle.battle_states.policies
        return tuple(
            sorted(
                a.state_id
                for a in subject.states.active_states()
                if getattr(policies.get(a.state_id), "prevent_action", False)
            )
        )

    def end_turn(self):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        self._logged_turn = None
        delay, self._turn_delay = getattr(self, "_turn_delay", 0.0), 0.0
        return self.battle.advance_turn(recovery=delay)

    def enemy_act(self, member_id):
        """One enemy action: its bound AI, else its first ability on default targets."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        enemy_id = str(member_id).split(":", 1)[0]
        binding = self.project.rpg_database.enemy_behavior_bindings.get(enemy_id)
        if binding is not None:
            return self.enemy_turn(member_id, binding.ai_id)
        definition = self.project.rpg_database.enemies.get(enemy_id)
        if definition is None or not definition.abilities:
            return None
        ability_id = definition.abilities[0]
        targets = self.default_targets(member_id, ability_id)
        if not targets:
            return None
        before = self._knockout_values(targets)
        result = self.execute(member_id, ability_id, targets)
        self._log(
            "action",
            member_id=str(member_id),
            ability_id=ability_id,
            target_ids=targets,
            outcomes=self._action_outcomes(member_id, ability_id, targets, before),
        )
        if getattr(
            result, "success", True
        ):  # enemy abilities apply their states, gains and commands too
            self._after_ability(
                member_id, self.battle.ability_runtime.registry.get(ability_id), targets
            )
        return result

    def run_enemy_turns(self, *, limit=1000):
        """Advance through enemy turns until a hero must act or the battle is decided.

        Returns ``(hero_id_or_None, ((enemy_member_id, result_or_error), ...))``.
        """
        log = []
        for _ in range(int(limit)):
            actor_id = self.current_turn_actor()
            if actor_id is None or self.battle.member(actor_id).side != "enemies":
                if not self.active_hero_ids():
                    self._log(
                        "battle_finished",
                        data={"winning_sides": ("enemies",), "defeated_sides": ("heroes",)},
                    )
                return actor_id, tuple(log)
            try:
                outcome = self.enemy_act(actor_id)
            except Exception as exc:
                outcome = exc
            log.append((actor_id, outcome))
            self.end_turn()
        raise GameSessionError("enemy turns did not yield to a hero")

    def _log(self, kind, **values):
        self._log_sequence += 1
        entry = BattleLogEntry(self._log_sequence, kind, **values)
        self.battle_log.append(entry)
        return entry

    def drain_battle_log(self):
        """Return and clear battle facts recorded since the last drain."""
        values = tuple(self.battle_log)
        self.battle_log.clear()
        return values

    def _knockout_values(self, target_ids):
        resource = self.rules.knockout_resource_id
        values = {}
        for target_id in target_ids:
            pool = self.battle.member(target_id).subject.resources
            if resource and resource in pool.to_data()["values"]:
                values[target_id] = pool.current(resource)
        return values

    def _action_outcomes(self, actor_id, ability_id, target_ids, before=None):
        """Interaction outcomes for opponent targets, valued by the observed knockout-resource
        change.

        Outcome tags/disposition come from the non-mutating interaction resolver;
        ``value.resolved_value`` is replaced by how much the knockout resource
        actually dropped (when ``before`` was measured), so presentation shows
        what happened rather than a multiplier.
        """
        if self.ability_relation(ability_id) != TargetRelation.OPPONENT:
            return ()
        action = BattleAction(actor_id, ability_id, tuple(target_ids))
        after = self._knockout_values(target_ids)
        outcomes = []
        for target_id in target_ids:
            outcome = self.battle.resolve_interaction(action, target_id, 1.0)
            if before is not None and target_id in before and target_id in after:
                observed = max(0.0, before[target_id] - after[target_id])
                outcome = replace(outcome, value=replace(outcome.value, resolved_value=observed))
            outcomes.append((target_id, outcome))
        return tuple(outcomes)

    def preview(self, actor_id, ability_id, target_ids):
        """Predicted resource changes of an action (same pipeline as execute; nothing mutates)."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        return self.battle.preview_action(BattleAction(actor_id, ability_id, tuple(target_ids)))

    def execute(self, actor_id, ability_id, target_ids):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        result = self.battle.execute(BattleAction(actor_id, ability_id, target_ids))
        if self.rules.action_timing == "timeline":
            recovery = self.battle.action_timing.definition_for(ability_id).recovery
            self._turn_delay = max(
                getattr(self, "_turn_delay", 0.0), recovery
            )  # applied when the turn ends
        return result

    def _begin_cast(self, actor_id, ability_id, targets, timing):
        """Start a cast (ActionTimingDefinition startup + cast time): validated now, resolved
        later by
        ``resolve_casts``; the caster's next turn moves back by the cast time and recovery."""
        battle = self.battle
        action = battle._validate_action(BattleAction(actor_id, ability_id, targets))
        current = float(getattr(battle.turn_queue, "current_time", 0.0) or 0.0)
        ready = battle.turn_queue.peek()
        if ready is not None and ready.member_id == action.actor_id:
            current = max(current, float(getattr(ready, "ready_time", current)))
        pending = battle.action_timing.begin(action, current_time=current)
        self._turn_delay = max(getattr(self, "_turn_delay", 0.0), timing.windup + timing.recovery)
        self._log(
            "cast_started",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            target_ids=tuple(action.target_ids),
            data={"resolve_at": pending.resolve_at, "cast_time": timing.windup},
        )
        return ()

    def resolve_casts(self):
        """Resolve every cast whose time has come (before the next member acts)."""
        if self.battle is None or not self.battle.action_timing.pending():
            return ()
        results = self.battle.resolve_due_actions()
        for result in results:
            action = result.action
            self._log(
                "action",
                member_id=action.actor_id,
                ability_id=action.ability_id,
                target_ids=action.target_ids,
            )
        return results

    def enemy_turn(self, member_id, ai_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        decision = self.battle.enemy_ai.decide(self.battle, ai_id, member_id, rng=self.battle.rng)
        if decision is None:
            return None
        before = self._knockout_values(decision.target_ids)
        result = self.battle.enemy_ai.execute_decision(self.battle, decision, rng=self.battle.rng)
        ability_id = (
            decision.payload.get("ability_id") if decision.action_kind == "ability" else None
        )
        if ability_id:
            self._log(
                "action",
                member_id=str(member_id),
                ability_id=str(ability_id),
                target_ids=tuple(decision.target_ids),
                outcomes=self._action_outcomes(member_id, ability_id, decision.target_ids, before),
            )
            if self.battle is not None and getattr(result, "success", True):
                definition = self.battle.ability_runtime.registry.get(ability_id)
                self._after_ability(member_id, definition, tuple(decision.target_ids))
        return result

    def active_enemy_ids(self):
        if self.battle is None:
            return ()
        return tuple(
            m.member_id for m in self.battle.parties["enemies"].members if self.battle.is_active(m)
        )

    def active_hero_ids(self):
        if self.battle is None:
            return ()
        return tuple(
            m.member_id for m in self.battle.parties["heroes"].members if self.battle.is_active(m)
        )

    def _write_battle_heroes_to_save(self):
        for member in self.battle.parties["heroes"].members:
            old = self.save.rpg_state.actor_snapshots.get(member.member_id)
            ability_state = None if old is None else old.ability_state
            self.save.rpg_state.actor_snapshots[member.member_id] = RpgActorSnapshot(
                member.member_id,
                member.subject.stats.to_data(),
                member.subject.resources.to_data(),
                member.subject.tags.to_data(),
                ability_state,
            )

    # --- economy and quests -------------------------------------------------

    def _reward_runtime(self):
        return RewardRuntime(
            inventory=self.save.rpg_state.inventory,
            progression=self.save.rpg_state.progression,
            currencies=self.save.rpg_state.currencies,
        )

    @property
    def shops(self):
        state = self.save.rpg_state
        return ShopRuntime(
            self.project.rpg_database.shops,
            inventory=state.inventory,
            currencies=state.currencies,
            stock=state.shop_stock,
        )

    @property
    def quest_log(self):
        def grant(reward: RewardDefinition):
            self._reward_runtime().apply(roll_reward(reward, random.Random(0)))

        return QuestLog(
            self.project.rpg_database.quests,
            self.save.rpg_state.quests,
            inventory=self.save.rpg_state.inventory,
            switches=self.save.event_context.get_switch,
            grant_reward=grant,
        )

    def recipe_known(self, recipe_id):
        recipe = self.project.rpg_database.composition_recipes[str(recipe_id)]
        return not recipe.requires_discovery or recipe.recipe_id in self.world.known_recipes

    def known_recipes(self, station=None):
        """Recipes the player can see, optionally only those usable at ``station``."""
        recipes = self.project.rpg_database.composition_recipes
        return tuple(
            r
            for k, r in sorted(recipes.items())
            if self.recipe_known(k) and (station is None or not r.station or r.station == station)
        )

    def learn_recipe(self, recipe_id):
        recipe_id = str(recipe_id)
        if recipe_id not in self.project.rpg_database.composition_recipes:
            raise GameSessionError(f"unknown recipe: {recipe_id}")
        newly = recipe_id not in self.world.known_recipes
        if newly:
            self.world.known_recipes.append(recipe_id)
            self.save.event_context.set_switch(f"recipe.{recipe_id}.known", True)
        return newly

    def craft(self, payload, *, station="", quality_bonus=0.0, rng=None):
        """Craft with the project's recipes against the saved inventory and progression.

        Crafting the exact materials of an undiscovered recipe discovers it.
        """
        from asteria.rpg import CompositionRuntime

        runtime = CompositionRuntime(self.project.rpg_database.composition_recipes.values())
        state = self.save.rpg_state
        result = runtime.craft(
            state.inventory,
            payload,
            station=station,
            rng=rng,
            quality_bonus=quality_bonus,
            progression=state.progression,
        )
        self.learn_recipe(result.recipe_id)
        self.refresh_quests()
        return result

    def open_shop(self, shop_id):
        shop_id = str(shop_id)
        if shop_id not in self.project.rpg_database.shops:
            raise GameSessionError(f"unknown shop: {shop_id}")
        self.open_shop_id = shop_id
        return shop_id

    def close_shop(self):
        self.open_shop_id = None

    def buy(self, item_id, quantity=1, *, shop_id=None):
        result = self.shops.buy(shop_id or self.open_shop_id, item_id, quantity)
        self.refresh_quests()
        return result

    def sell(self, item_id, quantity=1, *, shop_id=None):
        result = self.shops.sell(shop_id or self.open_shop_id, item_id, quantity)
        self.refresh_quests()
        return result

    def _quest_switches(self):
        for quest_id, progress in self.save.rpg_state.quests.items():
            for status in ("active", "completed", "failed"):
                self.save.event_context.set_switch(
                    f"quest.{quest_id}.{status}", progress.status == status
                )

    def _quest_call(self, method, *args):
        log = self.quest_log
        result = getattr(log, method)(*args)
        self._quest_switches()
        self.refresh_achievements()
        return result

    # --- world record: reputation, relationships, counters, achievements, bestiary

    @property
    def world(self):
        return self.save.rpg_state.world

    def refresh_achievements(self):
        db = self.project.rpg_database
        log = QuestLog(db.quests, self.save.rpg_state.quests)
        unlocked = self.world.unlock_ready(
            db.achievements,
            factions=db.factions,
            switches=self.save.event_context.get_switch,
            quest_status=log.status,
        )
        for achievement_id in unlocked:
            self.save.event_context.set_switch(f"achievement.{achievement_id}.unlocked", True)
        return unlocked

    # -- world interactions (RPG-07) --------------------------------------------------------------
    def perform_interaction(self, interaction_id):
        """Run a world interaction: capability, requirements, cost, check, outcome, follow-up
        event.

        Returns ``(outcome, detail)`` with outcome ``success`` / ``failure`` / ``refused``; the
        outcome is
        also stored in the event variable ``interaction.<id>`` so the calling event can branch on
        it.
        """
        import random

        from asteria.events.conditions import EventCondition

        db = self.project.rpg_database
        interaction = db.world_interactions.get(str(interaction_id))
        if interaction is None:
            raise GameSessionError(f"unknown world interaction {interaction_id}")
        ctx = self.save.event_context
        state = self.save.rpg_state
        key = f"interaction.{interaction.interaction_id}"

        def finish(outcome, detail=""):
            ctx.set_variable(key, outcome)
            return outcome, detail

        if not interaction.repeatable and ctx.get_switch(f"{key}.done"):
            return finish("refused", "already done")
        party = [a for a in state.party_active_actor_ids if a in db.actors]
        if interaction.actor_tag and not any(
            interaction.actor_tag in db.actors[a].tags for a in party
        ):
            return finish("refused", f"needs a party member with {interaction.actor_tag}")
        if interaction.required_item and state.inventory.count(interaction.required_item) < 1:
            return finish("refused", f"needs {interaction.required_item}")
        for requirement in interaction.requirements:
            condition = EventCondition(
                requirement["source"],
                requirement["name"],
                requirement["operator"],
                requirement["value"],
            )
            if not condition.evaluate(ctx):
                return finish(
                    "refused",
                    f"requires {requirement['name']} {requirement['operator']} "
                    f"{requirement['value']}",
                )
        for item_id, quantity in interaction.cost_items.items():
            if state.inventory.count(item_id) < quantity:
                return finish("refused", f"not enough {item_id}")
        for currency_id, amount in interaction.cost_currencies.items():
            if state.currencies.get(currency_id, 0.0) < amount:
                return finish("refused", f"not enough {currency_id}")
        for item_id, quantity in interaction.cost_items.items():
            state.inventory.remove(item_id, int(quantity))
        for currency_id, amount in interaction.cost_currencies.items():
            state.currencies[currency_id] = state.currencies.get(currency_id, 0.0) - amount
        best = 0.0
        if interaction.check_stat:
            values = [
                state.actor_snapshots[a].stats["values"].get(interaction.check_stat, 0.0)
                for a in party
                if a in state.actor_snapshots
            ]
            best = max(values, default=0.0)
        attempts = int(ctx.get_variable(f"{key}.attempts", 0) or 0) + 1
        ctx.set_variable(f"{key}.attempts", attempts)
        roll = random.Random(
            f"{interaction.interaction_id}:{attempts}"
        ).random()  # deterministic per attempt
        if roll < interaction.chance(best):
            for item_id, quantity in interaction.success_items.items():
                state.inventory.add(item_id, int(quantity))
            for currency_id, amount in interaction.success_currencies.items():
                state.currencies[currency_id] = state.currencies.get(currency_id, 0.0) + amount
            for faction_id, amount in interaction.reputation.items():
                self.change_reputation(faction_id, amount)
            if interaction.success_switch:
                ctx.set_switch(interaction.success_switch, True)
            if not interaction.repeatable:
                ctx.set_switch(f"{key}.done", True)
            if interaction.success_event:
                self.pending_followups.append(interaction.success_event)
            self.refresh_quests()
            return finish("success")
        if interaction.failure_switch:
            ctx.set_switch(interaction.failure_switch, True)
        if interaction.failure_event:
            self.pending_followups.append(interaction.failure_event)
        self.refresh_quests()
        return finish("failure")

    def change_reputation(self, faction_id, amount):
        faction = self.project.rpg_database.factions.get(str(faction_id))
        if faction is None:
            raise GameSessionError(f"unknown faction: {faction_id}")
        value = self.world.change_reputation(faction, amount)
        self.save.event_context.set_variable(f"reputation.{faction.faction_id}", value)
        self.refresh_achievements()
        return value

    def change_relationship(self, subject_id, amount):
        value = self.world.change_relationship(subject_id, amount)
        self.save.event_context.set_variable(f"relationship.{subject_id}", value)
        return value

    def add_counter(self, counter_id, amount=1):
        value = self.world.add_counter(counter_id, amount)
        self.refresh_achievements()
        return value

    def capture_chance(self, target_id):
        """Chance (0–1) that capturing ``target_id`` succeeds now, or None if it cannot be
        captured."""
        if self.mode != "battle" or str(target_id) not in self.active_enemy_ids():
            return None
        rule = self.project.rpg_database.capture_rules.get(str(target_id).rsplit(":", 1)[0])
        if rule is None:
            return None
        resources = self.battle.member(str(target_id)).subject.resources
        resource = self.rules.knockout_resource_id
        ratio = 1.0
        if (
            resource
            and resource in resources.to_data()["values"]
            and resources.maximum(resource) > 0
        ):
            ratio = resources.current(resource) / resources.maximum(resource)
        return rule.chance(ratio)

    def capture_targets(self):
        """``(member_id, chance, item_id)`` for every enemy that can be captured right now."""
        result = []
        for member_id in self.active_enemy_ids():
            chance = self.capture_chance(member_id)
            if chance is not None:
                rule = self.project.rpg_database.capture_rules[member_id.rsplit(":", 1)[0]]
                result.append((member_id, chance, rule.item_id))
        return tuple(result)

    def attempt_capture(self, actor_id, target_id, *, rng=None):
        """Try to capture enemy ``target_id``; on success it leaves battle and its actor joins the
        roster."""
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        target_id = str(target_id)
        if target_id not in self.active_enemy_ids():
            raise GameSessionError(f"{target_id} cannot be captured now")
        enemy_id = target_id.rsplit(":", 1)[0]
        rule = self.project.rpg_database.capture_rules.get(enemy_id)
        if rule is None:
            raise GameSessionError(f"{enemy_id} cannot be captured")
        state = self.save.rpg_state
        if rule.item_id and not state.inventory.remove(rule.item_id, 1):
            raise GameSessionError(f"capturing needs {rule.item_id}")
        roll = (rng or self.battle.rng).random()
        success = roll < self.capture_chance(target_id)
        self._log(
            "capture",
            member_id=str(actor_id),
            target_ids=(target_id,),
            data={"success": success, "actor_id": rule.actor_id},
        )
        if not success:
            return False
        self.battle.remove_combatant(target_id, state_id="captured", reason="captured")
        self._captured.add(target_id)
        self.world.note_enemy(enemy_id, "captured")
        if rule.pet_item_id:  # a pet item: kept in the bag, sent out by an ability that needs it
            state.inventory.add(rule.pet_item_id, 1)
        if rule.pet_species_id:  # an owned creature with its own level and nickname
            self.add_pet(rule.pet_species_id, level=rule.pet_level)
        if rule.actor_id and rule.actor_id not in state.party_actor_ids:
            state.party_actor_ids = state.party_actor_ids + (rule.actor_id,)
        if rule.actor_id:
            self.ensure_actor_progression(rule.actor_id)
        self.refresh_achievements()
        return True

    def start_quest(self, quest_id):
        return self._quest_call("start", quest_id)

    def advance_quest(self, quest_id, objective_id, amount=1):
        return self._quest_call("advance", quest_id, objective_id, amount)

    def complete_quest(self, quest_id):
        return self._quest_call("complete", quest_id)

    def fail_quest(self, quest_id):
        return self._quest_call("fail", quest_id)

    def refresh_quests(self):
        return self._quest_call("refresh")

    LOOT_LUCK_VARIABLE = "loot.luck"
    DIFFICULTY_VARIABLE = "difficulty.setting"

    @property
    def loot_luck(self):
        """Luck applied to loot rolls; events set it through the ``loot.luck`` variable."""
        try:
            return float(self.save.event_context.get_variable(self.LOOT_LUCK_VARIABLE, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def capture_hero_state(self):
        """Level, stats and abilities of the active heroes (before / after a reward step)."""
        state = self.save.rpg_state
        result = {}
        for actor_id in state.party_active_actor_ids:
            build = self.resolve_actor_build(actor_id)
            progress = state.actor_progression.get(actor_id)
            result[actor_id] = {
                "level": int(progress.level) if progress is not None else 1,
                "stats": {name: build.stats.get(name) for name in build.stats.names()},
                "abilities": tuple(build.abilities),
            }
        return result

    def build_aftermath(self, applied, before, experience=None):
        """The victory results (rewards, level changes) for the battle just won."""
        from asteria.rpg.victory import build_aftermath

        db = self.project.rpg_database
        names = {x: db.actors[x].display_name for x in before if x in db.actors}
        notes = []
        extensions = None if self.battle is None else self.battle.extensions
        if extensions is not None:
            for member_id in sorted(extensions.overkill):
                scale = extensions.overkill_scale(self.battle, member_id)
                if scale > 1.0:
                    notes.append(f"Overkill x{scale:.2g}")
        return build_aftermath(
            applied,
            before,
            self.capture_hero_state(),
            defeated=tuple(self._last_defeated),
            names=names,
            experience=experience,
            bonus_notes=tuple(dict.fromkeys(notes)),
        )

    def _scaled_reward(self, reward, member_id):
        """Currency and experience grow with the enemy's level and with overkill damage."""
        scale = 1.0
        rules = self.enemy_level_rules
        level = self.enemy_levels.get(member_id)
        if rules is not None and level:
            scale *= rules.reward_multiplier(level, self.difficulty or None)
        extensions = None if self.battle is None else self.battle.extensions
        if extensions is not None and member_id in self.battle.members:
            scale *= extensions.overkill_scale(self.battle, member_id)
        if scale == 1.0:
            return reward
        return type(reward)(
            {k: v * scale for k, v in reward.currencies.items()},
            {k: v * scale for k, v in reward.experience.items()},
            reward.items,
        )

    def finish_victory(self):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        if self.active_enemy_ids():
            raise GameSessionError("encounter is not defeated")
        self._write_battle_heroes_to_save()
        db = self.project.rpg_database
        reward_runtime = RewardRuntime(
            inventory=self.save.rpg_state.inventory,
            progression=self.save.rpg_state.progression,
            currencies=self.save.rpg_state.currencies,
        )
        applied = []
        rng = random.Random(157)
        # Captured enemies joined the party: they give no reward and do not count as defeated.
        defeated = tuple(
            enemy_id
            for serial, enemy_id in enumerate(self._enemy_ids, 1)
            if f"{enemy_id}:{serial}" not in self._captured
        )
        member_ids = tuple(
            f"{enemy_id}:{serial}"
            for serial, enemy_id in enumerate(self._enemy_ids, 1)
            if f"{enemy_id}:{serial}" not in self._captured
        )
        for enemy_id, member_id in zip(defeated, member_ids, strict=True):
            definition = db.enemies[enemy_id].reward
            reward = roll_reward(
                definition, rng, luck=self.loot_luck, switches=self.save.event_context.get_switch
            )
            if definition.drop_table_id:
                from asteria.rpg.drop_tables import roll_drop_table

                extra = roll_drop_table(
                    db.drop_tables[definition.drop_table_id],
                    rng,
                    counters=self.world.counters,  # pity counters are saved with the world state
                    luck=self.loot_luck,
                    switches=self.save.event_context.get_switch,
                )
                items = dict(reward.items)
                for item_id, amount in extra.items():
                    items[item_id] = items.get(item_id, 0) + amount
                reward = type(reward)(reward.currencies, reward.experience, items)
            reward = self._scaled_reward(reward, member_id)
            applied.append(reward_runtime.apply(reward))
        self._store_mastery()
        self._award_job_points(len(defeated))
        self._last_defeated = defeated
        self._log(
            "battle_finished", data={"winning_sides": ("heroes",), "defeated_sides": ("enemies",)}
        )
        self.save.event_context.set_switch(f"encounter.{self.encounter_id}.defeated", True)
        log = self.quest_log
        for enemy_id in defeated:
            log.record_defeat(enemy_id)
            self.world.note_enemy(enemy_id, "defeated")
        self._quest_switches()
        self.refresh_achievements()
        self._pets_gain_experience()
        self.mode = "field"
        self.battle = None
        self.encounter_id = None
        self._enemy_ids = ()
        self.interaction.reset()
        return tuple(applied)

    def sync_world_state(self):
        t = self.player.get(Transform)
        self.save.scene_id = self.scene.id
        self.save.player_entity_id = self.player.id
        self.save.player_facing = self.facing
        self.save.player_position = (t.x, t.y)
        self.save.active_event = self.events.snapshot()
        from asteria.runtime.npc_state import npc_entities

        for npc_id, entity in npc_entities(self.scene).items():
            if entity.enabled and npc_id in self.world.npcs:
                self._record_npc(entity)  # keep where moved NPCs stand
        return self.save


def describe_condition(condition):
    """Plain words for an ability condition (menus: why it cannot be used)."""
    from asteria.gameplay.conditions import (
        ConditionGroup,
        NumericCondition,
        StateCondition,
        TagCondition,
    )

    if isinstance(condition, TagCondition):
        text = (
            condition.tag.split(".", 1)[-1].replace("_", " ")
            if condition.tag.startswith("equip.")
            else condition.tag
        )
        return text if condition.present else f"no {text}"
    if isinstance(condition, ConditionGroup):
        parts = [describe_condition(c) for c in condition.conditions]
        joiner = (
            " or " if str(getattr(condition.mode, "value", condition.mode)) == "any" else " + "
        )
        return joiner.join(parts) if parts else "conditions"
    if isinstance(condition, StateCondition):
        return f"state {getattr(condition, 'state_id', '')}"
    if isinstance(condition, NumericCondition):
        return f"{condition.key} {condition.operator} {condition.value:g}"
    return "conditions"
