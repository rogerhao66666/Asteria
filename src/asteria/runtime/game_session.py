from __future__ import annotations

import random
from dataclasses import dataclass, replace

from asteria.core import Transform
from asteria.core.lifecycle import LifecycleHookBus
from asteria.core.scene_transition import carry_persistent_entities
from asteria.events import EventRunner, EventScheduler, SceneEventRuntime, WorldCommandRouter
from asteria.gameplay import AbilityRegistry, AbilityRuntime, GameplaySubject
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
from asteria.runtime.input import InputSnapshot
from asteria.runtime.interaction import InteractionController
from asteria.runtime.world_command_handlers import move_entity_to_scene, register_standard_world_commands


class GameSessionError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class BattleLogEntry:
    """One canonical battle fact, in order, for presentation adapters to consume.

    kinds: ``battle_started``, ``turn``, ``action``, ``gauge``, ``capture``, ``summoned``, ``battle_finished``.
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
        self.notices = []  # short messages for the field (CMP-03 popups): {"text", "entity", "duration_ms"}
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
        self.battle_log = []
        self._log_sequence = 0
        self._logged_turn = None
        # Event programs run here: one foreground runner for interactions plus
        # the current scene's autorun/parallel scheduler.
        self.presentation_requests = []
        self.event_errors = []
        self.world_commands = register_standard_world_commands(WorldCommandRouter(), self)
        self.events = EventRunner(
            project.event_programs, context=runtime_save.event_context, world_commands=self.world_commands
        )
        self.events.sequence_host = self
        if runtime_save.active_event is not None:
            self.events.restore(runtime_save.active_event)
        # Project-wide common events (EVT-03): autorun / parallel ones run while their switch is on.
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
        self._frame_collision_world = None
        from asteria.runtime.profiler import NullProfiler

        self.profiler = NullProfiler()
        self.field_input = None  # InputSnapshot for real-time control this frame (set_field_input)
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
        return self.facing

    def field_step(self, actions=None):
        """Feed field input; an interaction starts its event program in the foreground runner."""
        if self.mode != "field":
            raise GameSessionError("field input unavailable outside field mode")
        if self.event_busy:
            return None
        trigger = self.interaction.step(InputSnapshot(dict(actions or {})), self.scene, self.player, self.facing)
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
                return world.blocking_query(exclude={entity.id, self.player.id})

            systems = (
                SpawnSystem(
                    self.project.prefabs,
                    build_preview_registry(),
                    switches=self.save.event_context.get_switch,
                    rng=random.Random(f"{scene.id}:spawn"),
                ),
                FieldAISystem(blocking, rng=random.Random(f"{scene.id}:ai"), default_target_id=self.player.id),
            )
            from asteria.runtime.behavior_tree import BehaviorTreeSystem
            from asteria.runtime.character_control import CharacterControllerSystem, HitboxSystem
            from asteria.runtime.combat import CombatSystem
            from asteria.runtime.entity_actions import EntityActionSystem

            hits = HitboxSystem()
            library = self.project.gameplay_library
            # ASTERIA_SPEC §20: landed hits -> damage, poise, super armor, knockdown, knockback, hitstop, death, drops
            combat = CombatSystem(
                library.attacks,
                hits=hits,
                formulas=library.formulas,
                drop_tables=self.project.rpg_database.drop_tables,
                rng=random.Random(f"{scene.id}:combat"),
                counters=self.world.counters,  # drop table pity is saved with the world state
                switches=self.save.event_context.get_switch,
                states=library.states,  # poison, burn, buffs tick in real time
            )
            from asteria.runtime.projectiles import ProjectileSystem

            def frame_world():
                world = self._frame_collision_world
                if world is None or world.stale:
                    with self.profiler.section("collision"):
                        world = self._frame_collision_world = CollisionWorld.from_scene(scene)
                return world

            projectiles = ProjectileSystem(
                library.projectiles, hits=hits, combat=combat, world=frame_world, paused=combat.paused
            )
            actions = EntityActionSystem(hitboxes=hits, paused=combat.paused, armor=combat, projectiles=projectiles)
            combat.actions = actions
            from asteria.core.prefab import instantiate
            from asteria.runtime.action_combat import ActionCombatSystem

            def summon(prefab_id, x, y):
                entity = instantiate(self.project.prefabs, prefab_id, build_preview_registry())
                if not entity.has(Transform):
                    entity.add_component(Transform())
                entity.get(Transform).x, entity.get(Transform).y = x, y
                return scene.add_entity(entity)

            # ASTERIA_SPEC §20: abilities used in real time (input bindings, combos, cancels, cooldowns, lock-on)
            action_combat = ActionCombatSystem(
                library.abilities,
                library.timelines,
                actions=actions,
                combat=combat,
                formulas=library.formulas,
                snapshot_provider=lambda: self.field_input,
            )
            behavior = BehaviorTreeSystem(
                self.project.rpg_database.behavior_trees,  # RPG-09
                target_id=self.player.id,
                switches=self.save.event_context.get_switch,
                set_switch=self.save.event_context.set_switch,
                start_encounter=lambda encounter_id: setattr(self, "_pending_tree_encounter", encounter_id),
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
                self.project.rpg_database, rng=random.Random(f"{scene.id}:loot"), collect=self._collect_loot
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
            # ENG-02 / ENG-17 / ANI-05 / RPG-09: behavior trees, entity action timelines, controllers, hits
            spawn, ai = systems
            systems = {
                "spawn": spawn,
                "ai": ai,
                "behavior": behavior,
                "action_combat": action_combat,
                "actions": actions,
                # controllers build the frame's world after AI, keep it current as they move, projectiles reuse it
                "controllers": CharacterControllerSystem(paused=combat.paused, world=frame_world),
                "hits": hits,
                "projectiles": projectiles,
                "combat": combat,
                "loot": loot,
            }
            self._field_simulation[scene.id] = systems
        return systems

    def field_update(self, dt):
        """Advance field enemies and spawn zones, then start any touched visible encounter."""
        if self.mode != "field" or self.event_busy:
            return None
        systems = self._field_systems()
        with self.profiler.section("spawn"):
            systems["spawn"].update(self.scene, float(dt))
        self._frame_collision_world = None
        with self.profiler.section("ai"):
            systems["ai"].update(self.scene, float(dt))
            systems["behavior"].update(self.scene, float(dt))
        self._frame_collision_world = None
        systems["action_combat"].update(self.scene, float(dt))
        systems["actions"].update(self.scene, float(dt))
        with self.profiler.section("collision"):
            systems["controllers"].update(self.scene, float(dt))
            systems["hits"].update(self.scene, float(dt))
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
        """Start a project action timeline (gameplay library) on a field entity — scripts and PLAY_ACTION."""
        timeline = self.project.gameplay_library.timelines.get(str(timeline_id))
        if timeline is None:
            raise GameSessionError(f"unknown action timeline {timeline_id}")
        entity = self._sequence_entity(entity_key)
        self.entity_actions.play(entity.id, timeline)
        return entity.id

    @property
    def loot(self):
        """Loot on the ground (ASTERIA_SPEC §35): ``drop``, ``pick_up_nearest``, ``labels``."""
        return self._field_systems()["loot"]

    def _collect_loot(self, looter, loot, equipment):
        """A picked-up stack goes into the save: currencies, the inventory, or the equipment bag."""
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
        """This frame's input actions for real-time control (``ActionCombat`` bindings, lock-on); ``None`` = none."""
        from asteria.runtime.input import InputSnapshot

        self.field_input = None if actions is None else InputSnapshot(dict(actions))

    @property
    def action_combat(self):
        """Real-time ability use (ASTERIA_SPEC §20) for the current scene: ``use``, cooldowns, lock-on."""
        return self._field_systems()["action_combat"]

    @property
    def combat(self):
        """Real-time combat resolution (ASTERIA_SPEC §20) for the current scene; ``combat.events`` per update."""
        return self._field_systems()["combat"]

    @property
    def projectiles(self):
        """Projectiles in flight (ASTERIA_SPEC §20) for the current scene; ``fire`` / ``views()`` / ``events``."""
        return self._field_systems()["projectiles"]

    @property
    def hits(self):
        """Hitbox / hurtbox detection (ENG-17) for the current scene; ``hits.events`` per update."""
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
        """Fast-forward skippable cutscenes to their end state (moves land, world commands still run)."""
        skipped = sum(r.skip_sequences() for r in self._all_runners())
        self.update_events(0.0)
        return skipped

    def _sequence_entity(self, key):
        key = str(key)
        if key in ("player", "@player", self.player.id):
            return self.player
        entity = self.scene.get_entity(key) or next((e for e in self.scene.entities() if e.name == key), None)
        if entity is None or not entity.has(Transform):
            raise GameSessionError(f"sequence: no entity {key} with a position in {self.scene.name}")
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

    # -- NPC state (WLD-02) ------------------------------------------------------------------------
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
        """Change an NPC's saved state: visible, alive, mood, stage or flag.<name>; applied to the scene now."""
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
        """Relocate an NPC (possibly to another scene); it appears there when that scene is entered."""
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

    # -- battle events (EVT-03) --------------------------------------------------------------------
    def _battle_hook_bus(self):
        """A fresh hook bus per battle; project lifecycle bindings on ``rpg.battle.*`` hooks run as battle events."""
        from asteria.events import LifecycleEventBridge

        bus = LifecycleHookBus()
        bus.subscribe("rpg.battle.turn_skipped", self._turn_skipped)  # asleep, stunned, broken...: shown in battle
        bindings = [b for b in self.project.lifecycle_event_bindings if b.hook_name.startswith("rpg.battle.")]
        self.battle_events = LifecycleEventBridge(bus, self.events, bindings) if bindings else None
        self.save.event_context.providers["battle"] = self._battle_value
        return bus

    @property
    def revealed_weaknesses(self):
        """``{(enemy kind, interaction rule id)}`` found by hitting a weakness (kept for the whole session)."""
        values = getattr(self, "_revealed_weaknesses", None)
        if values is None:
            values = self._revealed_weaknesses = set()
        return values

    def shield_resource(self):
        """The battle resource shown as shields: the rules' ``shield_resource_id``, else the first break gauge's."""
        if self.rules.shield_resource_id:
            return self.rules.shield_resource_id
        for composition_id in sorted(self.battle.gauge_compositions.definitions):
            for impact in self.battle.gauge_compositions.definitions[composition_id].impacts:
                return impact.resource_id
        return ""

    def weaknesses(self, member_id):
        """The member's weaknesses for the battle screen: ``[(label, revealed)]`` from the interaction rules whose
        outcome is the weakness tag and whose target tags the member carries (labels from their source tags)."""
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
        self._log("turn_skipped", member_id=str(event.source), data={"states": tuple(data.get("blocking_states", ()))})

    def _battle_value(self, name):
        """Values battle-event conditions can read: ``round``, ``hp_ratio:<member or enemy id>``, ``alive:<id>``."""
        battle = self.battle
        if battle is None:
            return None
        if name == "round":
            return battle.turn_queue.round_index
        kind, _, key = str(name).partition(":")
        members = [m for m in battle.members.values() if m.member_id == key or m.member_id.split(":", 1)[0] == key]
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
                mode = EventScheduleMode.AUTORUN if common.trigger == "autorun" else EventScheduleMode.PARALLEL
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
        return runner.dialogue.dialogue or runner.dialogue.choice

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
        """Advance running event programs. Failures stop that event and are kept in event_errors."""
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
        self.touch.arm(destination, self.player)  # arriving on a door must not send the player back
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
        return values

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
        return allocation.allocate(str(graph_id), str(node_id), int(count))

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
        """The actor's progression record, created at level 1 with its authored classes when it joins later
        (a captured companion, a guest) - so every party member can level up."""
        actor_id = str(actor_id)
        records = self.save.rpg_state.actor_progression
        if actor_id not in records:
            actor = self.project.rpg_database.actors[actor_id]
            classes = tuple(a.class_id for a in actor.class_assignments)
            primary = tuple(a.class_id for a in actor.class_assignments if a.role == "primary") or classes[:1]
            records[actor_id] = ActorProgressionState(unlocked_class_ids=classes, active_class_ids=primary)
        return records[actor_id]

    def grant_actor_experience(
        self, actor_id, amount, *, level_threshold=1000.0, ap_per_level=2.0, ability_points_per_level=1.0
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
            points["ability_points"] = points.get("ability_points", 0.0) + gained * float(ability_points_per_level)
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

    # -- field menus: item use and equipment from the bag (UI-01) ----------------------------------
    def use_item(self, actor_id, item_id):
        """Use a consumable on a party member outside battle (the canonical ``use_inventory_item``)."""
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
        """Move an equipment item from the bag to a slot; whatever was there goes back to the bag."""
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
                EquipmentGrowthRuntime(self.project.rpg_database.equipment_growth[definition.growth_id])
                if definition.growth_id
                else None
            ),
        )
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
                        assignment_id=(source.assignment_id if source else f"save:{actor_id}:{class_id}"),
                        role=(source.role if source else ("primary" if index == 0 else "secondary")),
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
        """A combatant subject that can hold battle states (break, buffs...) from the project's state registry."""
        from asteria.gameplay import StateRuntime

        states = StateRuntime(self.project.gameplay_library.states, stats, resources, tags)
        return GameplaySubject(stats, resources, tags, states)

    def _actor_member(self, actor_id):
        build = self.resolve_actor_build(actor_id)
        subject = self._battle_subject(build.stats, build.resources, build.tags)
        speed = build.stats.get("speed")
        return PartyMember(
            str(actor_id), "heroes", subject, ability_ids=build.abilities, initiative=speed, initiative_stat="speed"
        )

    def _enemy_member(self, enemy_id, index):
        definition = self.project.rpg_database.enemies[enemy_id]
        runtime = definition.instantiate()
        subject = self._battle_subject(runtime.stats, runtime.resources, runtime.tags)
        speed = runtime.stats.get("speed")
        return PartyMember(
            f"{enemy_id}:{index}",
            "enemies",
            subject,
            ability_ids=definition.abilities,
            initiative=speed,
            initiative_stat="speed",
        )

    def summon(self, *, enemy_id=None, actor_id=None, count=1, owner_id=None, join_current_round=True):
        """Bring combatants into the running battle (RPG-08): ``enemy_id`` joins the enemies (a boss calling
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
            for ability_id in member.ability_ids:  # the newcomer's abilities join the battle's registry
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

        registry = AbilityRegistry()  # every project ability: items, summons and granted skills can act too
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
        )
        self.encounter_id = str(encounter_id)
        self._enemy_ids = tuple(enemy_definition_ids)
        self._captured = set()
        for enemy_id in sorted(set(enemy_definition_ids)):
            self.world.note_enemy(enemy_id, "seen")
        self.mode = "battle"
        self.battle_log.clear()
        self._logged_turn = None
        self._log("battle_started", data={"encounter_id": self.encounter_id})
        return self.battle

    def notify(self, text, *, entity=None, duration_ms=1100.0, kind="info"):
        """Queue a short field message the host shows as animated text above ``entity`` (default the player)."""
        self.notices.append({"text": str(text), "entity": entity, "duration_ms": float(duration_ms), "kind": str(kind)})

    def drain_notices(self):
        values, self.notices = tuple(self.notices), []
        return values

    def _configure_inventory(self):
        """The project's inventory rules (RPG-01; the first by id) apply to every way items arrive."""
        db = self.project.rpg_database
        rules = getattr(db, "inventory_rules", {})
        chosen = rules[sorted(rules)[0]] if rules else None

        def lookup(item_id):
            return db.items.get(item_id) or db.equipment.get(item_id) or db.attachments.get(item_id)

        self.save.rpg_state.inventory.configure(chosen, lookup)

    @property
    def inventory_overflow(self):
        """``(item_id, amount)`` that did not fit in the bag, newest last (for "bag full" messages)."""
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
            raise GameSessionError(f"{ability_id} concocts: use concoct() with the chosen ingredients")
        if definition is not None and ability_id in self.battle.member(actor_id).ability_ids:
            reason = self.ability_unavailable(actor_id, ability_id)
            if reason and not reason.startswith(("Ready in", "Blocked by")):  # those keep their own errors
                raise GameSessionError(f"{ability_id}: {reason}")
        targets = tuple(target_ids) if target_ids is not None else self.default_targets(actor_id, ability_id)
        if not targets:
            raise GameSessionError(f"{ability_id} has no valid targets")
        offensive = self.ability_relation(ability_id) == TargetRelation.OPPONENT
        battle_costs = dict(getattr(definition, "battle_costs", None) or {})
        if boost_level:  # boost and the ability's own battle costs come from the same gauges
            key = rules.boost_resource_id
            battle_costs[key] = battle_costs.get(key, 0.0) + boost_level * rules.boost_cost_per_level
        for resource_id, amount in battle_costs.items():
            have = self.battle.battle_resources.current(actor_id, resource_id)
            if have < amount:
                raise GameSessionError(f"{ability_id} needs {amount:g} {resource_id} ({have:g})")
        for resource_id, amount in (getattr(definition, "battle_costs", None) or {}).items():
            self.battle.battle_resources.spend(actor_id, resource_id, amount, trigger="rpg.session.ability_cost")
        if boost_level:
            self.battle.battle_resources.spend(
                actor_id,
                rules.boost_resource_id,
                boost_level * rules.boost_cost_per_level,
                trigger="rpg.session.boost",
            )
        timing = self.battle.action_timing.definition_for(ability_id)
        if timing.windup > 0 and rules.action_timing == "timeline":  # GP-02: the cast resolves later
            return self._begin_cast(actor_id, ability_id, targets, timing)
        ability_tags = set(getattr(definition, "tags", ()) or ())
        repeats = boost_level + 1
        if "boost.power" in ability_tags or (rules.boost_mode == "power" and "boost.repeat" not in ability_tags):
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
        """An ability's battle extras once it landed: battle resource gains (e.g. giving boost points to an
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
                members = tuple(m.member_id for m in battle.members.values() if m.side == side and battle.is_active(m))
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
                members = tuple(m.member_id for m in battle.members.values() if m.side == side and battle.is_active(m))
            for member_id in members:
                if not battle.is_active(battle.member(member_id)):
                    continue
                if entry["remove"]:
                    states = battle.member(member_id).subject.states
                    if states is not None and states.get(entry["state"]) is not None:
                        states.remove(entry["state"])
                        self._log("state_removed", member_id=str(member_id), data={"state": entry["state"]})
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
                k: (v.replace("@actor", str(actor_id)).replace("@target", str(first)) if isinstance(v, str) else v)
                for k, v in command["args"].items()
            }
            self.world_commands.dispatch(WorldCommand(command["command"], args))

    def ability_unavailable(self, actor_id, ability_id):
        """Why ``actor_id`` cannot use ``ability_id`` now ("" when it can): a blocking state, a cooldown,
        battle costs (boost points...), resource costs, unmet conditions (e.g. weapons it needs), or no
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
        """Items in the bag that a recipe of ``station`` uses (what a concoct ability can pick from)."""
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
        """Use a concoct ability: the recipe of its station matching ``ingredients`` (``{slot: [item ids]}``)
        consumes them and its product - an item with a ``battle_ability`` - acts at once on the targets."""
        from asteria.rpg import CompositionRuntime

        definition = self.battle.ability_runtime.registry.require(ability_id)
        if not definition.concoct_station:
            raise GameSessionError(f"{ability_id} does not concoct")
        reason = self.ability_unavailable(actor_id, ability_id)
        if reason:
            raise GameSessionError(reason)
        recipes = [
            r for r in self.project.rpg_database.composition_recipes.values() if r.station == definition.concoct_station
        ]
        runtime = CompositionRuntime(recipes)
        recipe = runtime.resolve(ingredients)
        if recipe is None:
            raise GameSessionError("these ingredients make nothing")
        state = self.save.rpg_state
        before = {o.item_id: state.inventory.count(o.item_id) for o in recipe.outputs}
        result = runtime.craft(state.inventory, ingredients, station=definition.concoct_station, rng=rng)
        self.learn_recipe(result.recipe_id)
        made = [k for k, n in before.items() if state.inventory.count(k) > n]
        self._log("concocted", member_id=str(actor_id), ability_id=str(ability_id), data={"recipe": recipe.recipe_id})
        if not made:
            return ()  # the recipe failed (success chance): materials are gone, nothing acts
        return self.use_battle_item(actor_id, made[0], target_ids)

    def use_battle_item(self, actor_id, item_id, target_ids=None):
        """Use an item in battle: its ``battle_ability`` runs for ``actor_id`` (targets, interaction rules, gauges,
        VFX); the item is consumed. Items without one apply their use effects to the target member."""
        from asteria.gameplay.effects import apply_effect

        item = self.project.rpg_database.items.get(str(item_id))
        if item is None:
            raise GameSessionError(f"unknown item {item_id}")
        inventory = self.save.rpg_state.inventory
        if inventory.count(item.item_id) < 1:
            raise GameSessionError(f"no {item.display_name} left")
        battle = self.battle
        if item.battle_ability:
            targets = tuple(target_ids) if target_ids else self.default_targets(actor_id, item.battle_ability)
            offensive = self.ability_relation(item.battle_ability) == TargetRelation.OPPONENT
            inventory.remove(item.item_id, 1)
            battle.granted_abilities = {(str(actor_id), item.battle_ability)}
            try:
                results = self._repeat_action(actor_id, item.battle_ability, targets, offensive, 1)
            finally:
                battle.granted_abilities = set()
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

    def _repeat_action(self, actor_id, ability_id, targets, offensive, repeats):
        definition = self.battle.ability_runtime.registry.get(ability_id)
        hits = tuple(getattr(definition, "hits", ()) or ()) or ({"tags": [], "power": 1.0},)
        results = []
        actor_tags = self.battle.member(actor_id).subject.tags
        for _ in range(repeats):
            for hit in hits:  # each hit lands on its own: its damage types meet weaknesses and shields
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
        outcomes = self._action_outcomes(actor_id, ability_id, targets, before) if offensive else ()
        self._log(
            "action",
            member_id=str(actor_id),
            ability_id=str(ability_id),
            target_ids=tuple(targets),
            outcomes=outcomes,
        )
        weak = self.rules.weakness_outcome_tag
        for target_id, outcome in outcomes:
            if weak and weak in outcome.outcome_tags:  # a weakness hit reveals its rule for that enemy kind
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
        actor = self.battle.next_actor()  # members who cannot act (asleep, broken...) are skipped there
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
        """States of ``member_id`` whose battle policy prevents acting (``prevent_action``); empty when free."""
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
        if getattr(result, "success", True):  # enemy abilities apply their states, gains and commands too
            self._after_ability(member_id, self.battle.ability_runtime.registry.get(ability_id), targets)
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
                    self._log("battle_finished", data={"winning_sides": ("enemies",), "defeated_sides": ("heroes",)})
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
        """Interaction outcomes for opponent targets, valued by the observed knockout-resource change.

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
            self._turn_delay = max(getattr(self, "_turn_delay", 0.0), recovery)  # applied when the turn ends
        return result

    def _begin_cast(self, actor_id, ability_id, targets, timing):
        """Start a cast (ActionTimingDefinition startup + cast time): validated now, resolved later by
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
            self._log("action", member_id=action.actor_id, ability_id=action.ability_id, target_ids=action.target_ids)
        return results

    def enemy_turn(self, member_id, ai_id):
        if self.mode != "battle":
            raise GameSessionError("no active battle")
        decision = self.battle.enemy_ai.decide(self.battle, ai_id, member_id, rng=self.battle.rng)
        if decision is None:
            return None
        before = self._knockout_values(decision.target_ids)
        result = self.battle.enemy_ai.execute_decision(self.battle, decision, rng=self.battle.rng)
        ability_id = decision.payload.get("ability_id") if decision.action_kind == "ability" else None
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
        return tuple(m.member_id for m in self.battle.parties["enemies"].members if self.battle.is_active(m))

    def active_hero_ids(self):
        if self.battle is None:
            return ()
        return tuple(m.member_id for m in self.battle.parties["heroes"].members if self.battle.is_active(m))

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
                self.save.event_context.set_switch(f"quest.{quest_id}.{status}", progress.status == status)

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
            db.achievements, factions=db.factions, switches=self.save.event_context.get_switch, quest_status=log.status
        )
        for achievement_id in unlocked:
            self.save.event_context.set_switch(f"achievement.{achievement_id}.unlocked", True)
        return unlocked

    # -- world interactions (RPG-07) ---------------------------------------------------------------
    def perform_interaction(self, interaction_id):
        """Run a world interaction: capability, requirements, cost, check, outcome, follow-up event.

        Returns ``(outcome, detail)`` with outcome ``success`` / ``failure`` / ``refused``; the outcome is
        also stored in the event variable ``interaction.<id>`` so the calling event can branch on it.
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
        if interaction.actor_tag and not any(interaction.actor_tag in db.actors[a].tags for a in party):
            return finish("refused", f"needs a party member with {interaction.actor_tag}")
        if interaction.required_item and state.inventory.count(interaction.required_item) < 1:
            return finish("refused", f"needs {interaction.required_item}")
        for requirement in interaction.requirements:
            condition = EventCondition(
                requirement["source"], requirement["name"], requirement["operator"], requirement["value"]
            )
            if not condition.evaluate(ctx):
                return finish(
                    "refused", f"requires {requirement['name']} {requirement['operator']} {requirement['value']}"
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
        roll = random.Random(f"{interaction.interaction_id}:{attempts}").random()  # deterministic per attempt
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
        """Chance (0–1) that capturing ``target_id`` succeeds now, or None if it cannot be captured."""
        if self.mode != "battle" or str(target_id) not in self.active_enemy_ids():
            return None
        rule = self.project.rpg_database.capture_rules.get(str(target_id).rsplit(":", 1)[0])
        if rule is None:
            return None
        resources = self.battle.member(str(target_id)).subject.resources
        resource = self.rules.knockout_resource_id
        ratio = 1.0
        if resource and resource in resources.to_data()["values"] and resources.maximum(resource) > 0:
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
        """Try to capture enemy ``target_id``; on success it leaves battle and its actor joins the roster."""
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
        if rule.actor_id not in state.party_actor_ids:
            state.party_actor_ids = state.party_actor_ids + (rule.actor_id,)
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

    @property
    def loot_luck(self):
        """Luck applied to loot rolls; events set it through the ``loot.luck`` variable."""
        try:
            return float(self.save.event_context.get_variable(self.LOOT_LUCK_VARIABLE, 0.0) or 0.0)
        except (TypeError, ValueError):
            return 0.0

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
        for enemy_id in defeated:
            definition = db.enemies[enemy_id].reward
            reward = roll_reward(definition, rng, luck=self.loot_luck, switches=self.save.event_context.get_switch)
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
            applied.append(reward_runtime.apply(reward))
        self._log("battle_finished", data={"winning_sides": ("heroes",), "defeated_sides": ("enemies",)})
        self.save.event_context.set_switch(f"encounter.{self.encounter_id}.defeated", True)
        log = self.quest_log
        for enemy_id in defeated:
            log.record_defeat(enemy_id)
            self.world.note_enemy(enemy_id, "defeated")
        self._quest_switches()
        self.refresh_achievements()
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
    from asteria.gameplay.conditions import ConditionGroup, NumericCondition, StateCondition, TagCondition

    if isinstance(condition, TagCondition):
        text = (
            condition.tag.split(".", 1)[-1].replace("_", " ") if condition.tag.startswith("equip.") else condition.tag
        )
        return text if condition.present else f"no {text}"
    if isinstance(condition, ConditionGroup):
        parts = [describe_condition(c) for c in condition.conditions]
        joiner = " or " if str(getattr(condition.mode, "value", condition.mode)) == "any" else " + "
        return joiner.join(parts) if parts else "conditions"
    if isinstance(condition, StateCondition):
        return f"state {getattr(condition, 'state_id', '')}"
    if isinstance(condition, NumericCondition):
        return f"{condition.key} {condition.operator} {condition.value:g}"
    return "conditions"
