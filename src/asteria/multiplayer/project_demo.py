"""Project-backed authoritative multiplayer: the authored ECS simulation runs once per scene.

Each connected player owns a separate GameSessionRuntime save and an entity cloned from
GameStart. Project actors are definitions; their mutable RPG contexts are never shared.
SQLite stores character saves, contributions, XP and pickup claims. Scene simulation,
unclaimed ground drops, spawn timers and AI state are transient and start afresh when
the server process starts; character defeat switches still suppress remembered bosses.
"""

from __future__ import annotations

import random
import uuid
from collections.abc import Mapping
from dataclasses import asdict, replace
from math import hypot, isfinite
from pathlib import Path

from asteria.core import Transform
from asteria.core.serialization import deserialize_entity, serialize_entity, serialize_scene
from asteria.project import Project
from asteria.runtime.action_combat import ActionCombatComponent
from asteria.runtime.character_control import (
    AIController2DComponent,
    CharacterController2DComponent,
)
from asteria.runtime.combat import CombatantComponent
from asteria.runtime.component_registry import default_component_registry
from asteria.runtime.game_save import GameRuntimeSave
from asteria.runtime.game_session import GameSessionRuntime
from asteria.runtime.input import InputSnapshot
from asteria.runtime.loot import LootComponent, LooterComponent

from .adapter import AdapterUpdate
from .rules import default_rules, validate_rules


class _EntityScene:
    """Restrict an AI system's query to one entity, keeping real scene lookups/mutations."""

    def __init__(self, scene, entity):
        self.scene, self.entity = scene, entity

    def __getattr__(self, name):
        return getattr(self.scene, name)

    def query(self, *types):
        return tuple(row for row in self.scene.query(*types) if row[0] is self.entity)


class ProjectDemoAdapter:
    network_tick_interval = 1 / 30
    SAVE_NAMESPACE = "project_demo"

    def __init__(self, store, project, *, project_root=None, rules=None, random_source=None):
        self.store, self.project = store, project
        self.project_root = Path(project_root) if project_root is not None else None
        self.rules = validate_rules(rules or default_rules())
        self.random = random_source or random.Random()
        for policy in self.rules["rewards"].values():
            drops = policy.get("drops", {})
            source = drops.get("source", "authored")
            if source not in {"authored", "configured"}:
                raise ValueError("drop source must be authored or configured")
            if source == "configured":
                for item_id in drops.get("items", []):
                    if (
                        item_id not in project.rpg_database.items
                        and item_id not in project.rpg_database.equipment
                    ):
                        raise ValueError(f"configured drop item does not exist: {item_id}")
        self.registry = default_component_registry()
        self.players = {}
        self.inputs = {}
        self.systems = {}
        self.hosts = {}
        self.events = []
        self._rewards = {}
        self._damage_logs = {}
        self._drop_owners = {}
        self._run_id = uuid.uuid4().hex[:16]
        self._sequence = 0
        self._save_elapsed = 0.0
        self.runtime_options = self.rules.get("project_runtime", {})
        self._template_scene = project.scene(
            project.game_start.scene_id or project.startup_scene_id
        )
        template = self._template_scene.get_entity(project.game_start.player_entity_id)
        if template is None:
            raise ValueError("project GameStart must identify a player")
        self._template = serialize_entity(template)
        # The authored player is a template. Only authenticated participant clones can act.
        self._template_scene.remove_entity(template)

    def _op(self, label):
        self._sequence += 1
        return f"project:{self._run_id}:{self._sequence}:{label}"[:160]

    def _player_id(self, entity_id):
        return next((pid for pid, s in self.players.items() if s.player.id == entity_id), None)

    def _snapshot(self, entity):
        pid = self._player_id(entity.id)
        session = self.players.get(pid)
        if session and (
            session.event_busy or session.open_shop_id or session.open_crafting_station
        ):
            return InputSnapshot({})
        return self.inputs.get(pid, InputSnapshot({}))

    def _session(self, player_id):
        if player_id not in self.players:
            raise ValueError("player is not in this project session")
        return self.players[player_id]

    def _actor(self, session):
        actor_id = session._actor_of(session.player)
        if not actor_id:
            raise ValueError("player has no RPG actor")
        return actor_id

    def _save_data(self, pid):
        session = self.players[pid]
        controller = session.player.try_get(CharacterController2DComponent)
        if controller is not None:
            session.facing = controller.facing
        session.sync_world_state()
        return {
            "save": session.save.to_data(),
            "combatant": self._combat_data(session.player),
            "bindings": session.player.get(ActionCombatComponent).bindings,
            "reward_experience": self.store.get_player(pid)["experience"],
        }

    def _save(self, pid):
        self.store.save_player_state(
            pid, self.SAVE_NAMESPACE, self._save_data(pid), self._op("save")
        )

    def _combat_data(self, entity):
        spec = entity.try_get(CombatantComponent)
        if spec is None:
            return None
        systems = self.systems.get(entity.scene.id)
        state = systems["combat"].state(entity) if systems else spec.state
        if state is None:
            return None
        return {
            "resources": state.resources.to_data(),
            "stats": state.stats.to_data(),
            "tags": state.tags.to_data(),
            "dead": state.dead,
            "poise": state.poise,
            "down_phase": state.down_phase,
            "down_left": state.down_left,
            "states": state.states.snapshot() if state.states is not None else None,
        }

    def initial_state(self):
        from .project_snapshot import pack_scene_data

        scene = next((s.scene for s in self.players.values()), self._template_scene)
        combatants = {}
        for active in self.project.scenes():
            for entity, _spec in active.query(CombatantComponent):
                data = self._combat_data(entity)
                if data is not None:
                    combatants[entity.id] = data
        rows = []
        for pid, session in self.players.items():
            session.sync_world_state()
            record = self.store.get_player(pid)
            save_data = session.save.to_data()
            actor_id = self._actor(session)
            current = combatants.get(session.player.id)
            transform = session.player.get(Transform)
            health = {}
            spec = session.player.try_get(CombatantComponent)
            if spec is not None:
                runtime = self.systems[session.scene.id]["combat"].state(session.player)
                if runtime.resources.contains(spec.life_resource):
                    health = {
                        "hp": runtime.resources.current(spec.life_resource),
                        "max_hp": runtime.resources.maximum(spec.life_resource),
                    }
            if current and actor_id in save_data["rpg_state"]["actor_snapshots"]:
                # Presentation reflects live resources without folding build bonuses into the save.
                save_data["rpg_state"]["actor_snapshots"][actor_id]["resources"] = current[
                    "resources"
                ]
            rows.append(
                {
                    "player_id": pid,
                    "entity_id": session.player.id,
                    "x": transform.x,
                    "y": transform.y,
                    **health,
                    "game_save": save_data,
                    "inventory": session.save.rpg_state.inventory.to_data()["counts"],
                    "experience": record["experience"],
                    "open_shop_id": session.open_shop_id,
                    "open_crafting_station": session.open_crafting_station,
                    "pending_dialogue": session.pending_dialogue.to_data()
                    if session.pending_dialogue
                    else None,
                    "event_busy": session.event_busy,
                }
            )
        return {
            "schema": "asteria.multiplayer.project_state",
            "scene": pack_scene_data(serialize_scene(scene)),
            "scenes": [pack_scene_data(serialize_scene(s)) for s in self.project.scenes()],
            "controllers": {
                e.id: {"facing": c.facing, "intent_x": c.intent_x, "intent_y": c.intent_y}
                for s in self.project.scenes()
                for e, c in s.query(CharacterController2DComponent)
            },
            "actions": {
                eid: {
                    "timeline_id": run.timeline.timeline_id,
                    "time": run.time,
                    "end": run.end,
                    "source": run.source,
                }
                for systems in self.systems.values()
                for eid, run in systems["actions"].running.items()
            },
            "cooldowns": [
                {"entity_id": eid, "ability_id": ability, "left": left}
                for systems in self.systems.values()
                for (eid, ability), left in systems["action_combat"].cooldowns.items()
            ],
            "targets": {
                e.id: spec.lock_target_id
                for scene in self.project.scenes()
                for e, spec in scene.query(ActionCombatComponent)
            },
            "projectiles": [
                asdict(v)
                for systems in self.systems.values()
                for v in systems["projectiles"].views()
            ],
            "players": rows,
            "combatants": combatants,
            "loot_owners": dict(self._drop_owners),
        }

    def _update(self):
        events, self.events = tuple(self.events), []
        return AdapterUpdate(self.initial_state(), events)

    def on_player_joined(self, player_id, display_name):
        if player_id in self.players:
            raise ValueError("player already joined")
        self.store.register_player(player_id, display_name)
        record = self.store.get_player(player_id)
        saved = record["game_state"].get(self.SAVE_NAMESPACE)
        entity_data = dict(self._template)
        entity_data["id"] = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{self.project.id}:{player_id}"))
        entity_data["name"] = display_name
        entity = deserialize_entity(entity_data, self.registry)
        scene_id = (
            saved["save"]["scene_id"]
            if saved
            else self.runtime_options.get("start_scene", self._template_scene.id)
        )
        scene_id = next((s.id for s in self.project.scenes() if s.name == scene_id), scene_id)
        scene = self.project.scene(scene_id)
        scene.add_entity(entity)
        if saved:
            data = dict(saved["save"])
            data["player_entity_id"] = entity.id
            save = GameRuntimeSave.from_data(data, self.project)
        else:
            # GameStart validation requires the template entity. Clone id substitutes it here.
            start = self.project.game_start.to_data()
            from asteria.runtime.game_start import GameStartDefinition

            start["player_entity_id"] = entity.id
            start["scene_id"] = scene_id
            if "start_position" in self.runtime_options:
                start["player_position"] = list(self.runtime_options["start_position"])
            position = start["player_position"]
            if position is not None:
                start["player_position"] = [position[0] + len(self.players) * 18, position[1]]
            save = GameStartDefinition.from_data(start).instantiate(self.project)
        session = GameSessionRuntime(self.project, save)
        session.prepare_action_player()
        from asteria.rpg import RpgActorRuntime

        for actor_id in session.save.rpg_state.party_actor_ids:
            if actor_id not in session.save.rpg_state.actor_snapshots:
                actor = RpgActorRuntime(
                    self.project.rpg_database.actors[actor_id],
                    class_definitions=self.project.rpg_database.classes,
                )
                session.save.rpg_state.actor_snapshots[actor_id] = actor.snapshot()
        if saved and saved.get("bindings"):
            session.player.get(ActionCombatComponent).bindings = saved["bindings"]
        # Same actor definition across players must not refresh another player's runtime stats.
        session.refresh_actor_combatants = lambda actor_id: session.refresh_combatant(
            session.player
        )
        self.players[player_id] = session
        self.inputs[player_id] = InputSnapshot({})
        self._systems(session)
        if not saved:
            classes = self.runtime_options.get("initial_classes")
            cycle = self.runtime_options.get("initial_class_cycle")
            if cycle:
                classes = [cycle[(len(self.players) - 1) % len(cycle)]]
            if classes:
                session.set_classes(self._actor(session), classes)
            points = self.runtime_options.get("initial_points", {})
            if points:
                session.grant_actor_points(self._actor(session), **points)
        if saved and saved.get("combatant"):
            from asteria.gameplay import ResourcePool

            state = self.systems[scene.id]["combat"].state(entity)
            state.resources = ResourcePool.from_data(saved["combatant"]["resources"])
            state.dead = bool(saved["combatant"].get("dead", False))
            if state.states is not None and saved["combatant"].get("states"):
                state.states.restore(saved["combatant"]["states"])
            if state.dead:
                session.player_down = max(session.combat_scene.respawn_delay, 0.01)
        if saved:
            missing_experience = record["experience"] - int(saved.get("reward_experience", 0))
            if missing_experience > 0:
                session.grant_actor_experience(
                    self._actor(session), missing_experience, **session.action_progression
                )
                session.refresh_combatant(session.player)
        self._save(player_id)
        self.events.append({"kind": "joined", "player_id": player_id, "entity_id": entity.id})
        return self._update()

    def _systems(self, session):
        scene = session.scene
        previous_scene = getattr(session, "_multiplayer_prepared_scene", None)
        if previous_scene != scene.id:
            session.prepare_action_player()
            controller = session.player.try_get(CharacterController2DComponent)
            if controller is not None:
                controller.set_intent()
                controller.velocity_y = 0.0
                controller.push_x = controller.push_y = 0.0
                controller.grounded, controller.ground_id = False, None
                controller.hit_wall = controller.hit_ceiling = False
                controller.jump_held = controller.cut_armed = controller.climbing = False
                controller.air_time = controller.buffer_left = controller.drop_left = 0.0
                controller.speed_override = 0.0
                if controller.mode == "side" and controller.facing in {"up", "down"}:
                    session.set_player_facing("right")
            if previous_scene in self.systems:
                old_scene = self.project.scene(previous_scene)
                self.systems[previous_scene]["actions"].cancel(
                    session.player.id, old_scene, force=True
                )
                from asteria.runtime.character_control import Hitbox2DComponent

                hitbox = session.player.try_get(Hitbox2DComponent)
                if hitbox is not None:
                    hitbox.active = False
            position = session.player.get(Transform)
            session._action_spawn.setdefault(scene.id, (position.x, position.y))
            session._multiplayer_prepared_scene = scene.id
        if scene.id not in self.systems:
            systems = session._field_systems()
            self.systems[scene.id] = systems
            self.hosts[scene.id] = session
            systems["player_input"].entity_snapshot_provider = self._snapshot
            systems["action_combat"].entity_snapshot_provider = self._snapshot
            combat = systems["combat"]
            combat.stats_provider = lambda e, c: (
                self.players[self._player_id(e.id)]._actor_combat_state(e, c)
                if self._player_id(e.id)
                else None
            )
            action = systems["action_combat"]
            action.known_abilities = lambda e: (
                self.players[self._player_id(e.id)]._known_abilities(e)
                if self._player_id(e.id)
                else None
            )
            action.inventory = lambda e: (
                self.players[self._player_id(e.id)].save.rpg_state.inventory
                if self._player_id(e.id)
                else None
            )
            # Remove the original single-player listeners, including its automatic drop path.
            combat.listeners[:] = [self._combat_event]

            def nearest_target(active_scene, spec, cache):
                target = self._nearest(active_scene, spec.entity)
                return target.get(Transform) if target else None

            systems["ai"]._target_of = nearest_target
            systems["loot"].collect = self._collect
            if self.project_root:
                from asteria.runtime.tilemap_field import AssetResources, tilemap_binding
                from asteria.runtime.tilequery import TileMapQuery

                binding = tilemap_binding(scene)
                if binding:
                    tilemap = AssetResources(self.project, self.project_root).get(
                        binding.tilemap_asset_id, "tilemap"
                    )
                    session.set_tile_blocking(TileMapQuery(tilemap))
        systems = self.systems[scene.id]
        session._field_simulation[scene.id] = systems
        systems["combat"].protected.add(session.player.id)
        return systems

    def handle_input(self, player_id, input_state):
        self._session(player_id)
        if not isinstance(input_state, Mapping):
            raise ValueError("input must be an object")
        actions = dict(input_state.get("actions", {}))
        actions.update({k: v for k, v in input_state.items() if k != "actions"})
        for axis, neg, pos in (
            ("move_x", "move_left", "move_right"),
            ("move_y", "move_up", "move_down"),
        ):
            if axis in actions:
                value = actions.pop(axis)
                if (
                    isinstance(value, bool)
                    or not isinstance(value, (float, int))
                    or not isfinite(value)
                ):
                    raise ValueError("input axis must be finite")
                actions[neg], actions[pos] = max(0, -value), max(0, value)
        if len(actions) > 64 or any(
            not isinstance(k, str)
            or not isinstance(v, (float, int))
            or not isfinite(v)
            or abs(v) > 1
            for k, v in actions.items()
        ):
            raise ValueError("input actions must be finite values between -1 and 1")
        self.inputs[player_id] = InputSnapshot(actions)
        return None

    def _collect(self, entity, loot, equipment):
        pid = self._player_id(entity.id)
        if pid is None:
            return False
        owner = self._drop_owners.get(loot.entity.id)
        if owner and owner != pid:
            return False
        session = self.players[pid]
        before = session.save.rpg_state.to_data()
        try:
            if not session._collect_loot(entity, loot, equipment):
                return False
            if loot.entity.id in self._drop_owners:
                if not self.store.claim_world_drop(
                    loot.entity.id,
                    pid,
                    self._op("pickup"),
                    state_namespace=self.SAVE_NAMESPACE,
                    player_state=self._save_data(pid),
                ):
                    from asteria.rpg import RpgRuntimeState

                    session.save.rpg_state = RpgRuntimeState.from_data(
                        before, self.project.rpg_database
                    )
                    session._configure_inventory()
                    return False
                self._drop_owners.pop(loot.entity.id, None)
            else:
                self._save(pid)
            return True
        except Exception:
            from asteria.rpg import RpgRuntimeState

            session.save.rpg_state = RpgRuntimeState.from_data(before, self.project.rpg_database)
            session._configure_inventory()
            raise

    def _encounter(self, target_id):
        return f"project:{self._run_id}:{target_id}"

    def _combat_event(self, event):
        self.events.append({"kind": "combat", **asdict(event)})
        pid = self._player_id(event.attacker_id)
        victim_pid = self._player_id(event.target_id)
        if event.kind == "damage" and pid and not victim_pid and event.amount > 0:
            encounter = self._encounter(event.target_id)
            self.store.begin_encounter(encounter, "project_enemy")
            self.store.record_damage(
                encounter, pid, max(1, round(event.amount)), self._op("damage")
            )
            log = self._damage_logs.setdefault(event.target_id, [])
            log.append(
                {
                    "order": len(log) + 1,
                    "player_id": pid,
                    "entity_id": event.attacker_id,
                    "attack_id": event.attack_id,
                    "damage": event.amount,
                }
            )
        if event.kind == "death":
            if victim_pid:
                self.players[victim_pid]._player_fell(event)
                return
            encounter = self._encounter(event.target_id)
            self.store.begin_encounter(encounter, "project_enemy")
            contributors = self.store.get_encounter_contributors(encounter)
            eligible = sorted(contributors)
            policy = self.rules["rewards"]["boss"]
            if not event.data.get("defeat_switch"):
                policy = self.rules["rewards"].get(
                    "monster",
                    {
                        **policy,
                        "experience": {
                            "policy": "full_amount_per_eligible_player",
                            "amount": int(event.data.get("experience", 0)),
                        },
                    },
                )
            if policy.get("eligibility") == "any_session_participant":
                eligible = sorted(self.players)
            self._rewards[event.target_id] = {
                "encounter": encounter,
                "eligible": eligible,
                "damage": contributors,
                "policy": policy,
                "event": event,
                "is_boss": bool(event.data.get("defeat_switch")),
            }
            switch = event.data.get("defeat_switch")
            if switch:
                for session in self.players.values():
                    session.save.event_context.set_switch(switch, True)
            if policy["drops"].get("source", "authored") == "configured":
                items = {}
                for item_id in policy["drops"]["items"]:
                    items[item_id] = items.get(item_id, 0) + 1
                self._combat_event(replace(event, kind="drop", data={"items": items}))
                self._rewards[event.target_id]["configured_emitted"] = True
        elif event.kind == "drop":
            reward = self._rewards.get(event.target_id)
            if not reward or not reward["eligible"] or reward.get("configured_emitted"):
                return
            policy, eligible = reward["policy"], reward["eligible"]
            assignment = policy["drops"]["assignment"]
            if assignment == "highest_damage_player":
                owners = [max(eligible, key=lambda p: reward["damage"].get(p, 0))]
            elif assignment == "every_eligible_player":
                owners = eligible
            else:
                owners = [None]
            claim_policy = (
                "owner_only" if reward["is_boss"] else self.rules["world_pickup"]["policy"]
            )
            if claim_policy == "personal":
                owners = eligible
            scene = getattr(self, "_active_combat_scene", None)
            if scene is None:
                return
            loot_system = self.systems[scene.id]["loot"]
            for owner in owners:
                for entity in loot_system.drop(
                    scene,
                    event.x,
                    event.y,
                    items=event.data.get("items"),
                    currencies=event.data.get("currencies"),
                    level=event.data.get("level", 1),
                    luck=event.data.get("luck", 0),
                ):
                    assigned = owner if owner is not None else self.random.choice(eligible)
                    if claim_policy in {"first_valid_claim", "round_robin"}:
                        assigned = None
                    spec = entity.get(LootComponent)
                    self.store.create_world_drop(
                        entity.id,
                        reward["encounter"],
                        spec.item_id,
                        spec.amount,
                        owner_player_id=None if claim_policy == "personal" else assigned,
                        policy=claim_policy,
                        eligible_player_ids=(
                            [assigned]
                            if claim_policy == "personal"
                            else eligible
                            if claim_policy in {"round_robin", "random_eligible_player"}
                            else []
                        ),
                    )
                    record = self.store.get_world_drop(entity.id)
                    self._drop_owners[entity.id] = (
                        assigned if claim_policy == "personal" else record["owner_player_id"]
                    )

    def _finish_rewards(self):
        for target_id, reward in self._rewards.items():
            amount = int(reward["policy"]["experience"]["amount"])
            experience = {pid: amount for pid in reward["eligible"]}
            result = {
                "target_id": target_id,
                "eligible": reward["eligible"],
                "kill_credit": self._player_id(reward["event"].attacker_id),
                "combat_log": self._damage_logs.get(target_id, []),
            }
            if self.store.complete_encounter(
                reward["encounter"],
                experience_by_player=experience,
                item_grants=[],
                result=result,
            ):
                for pid in experience:
                    if pid in self.players:
                        s = self.players[pid]
                        s.grant_actor_experience(self._actor(s), amount, **s.action_progression)
                        s.refresh_combatant(s.player)
                        self._save(pid)
                self.events.append(
                    {
                        "kind": "enemy_rewards",
                        "target_id": target_id,
                        "experience_by_player": experience,
                        "kill_credit": result["kill_credit"],
                    }
                )
        if self._rewards:
            # Defeat switches also belong to connected players who did not earn combat XP.
            for pid in self.players:
                self._save(pid)
        for target_id in self._rewards:
            self._damage_logs.pop(target_id, None)
        self._rewards.clear()

    def _nearest(self, scene, entity):
        x, y = entity.get(Transform).x, entity.get(Transform).y
        targets = [
            s.player
            for s in self.players.values()
            if s.scene is scene
            and not (
                s.player.get(CombatantComponent).state
                and s.player.get(CombatantComponent).state.dead
            )
        ]
        return min(
            targets,
            key=lambda e: hypot(e.get(Transform).x - x, e.get(Transform).y - y),
            default=None,
        )

    def network_tick(self, dt):
        if not isinstance(dt, (int, float)) or not isfinite(dt) or dt <= 0:
            raise ValueError("tick duration must be finite and positive")
        for session in tuple(self.players.values()):
            controller = session.player.try_get(CharacterController2DComponent)
            if controller is not None:
                session.facing = controller.facing
            session.set_field_input(self._snapshot(session.player).actions)
            if session.player_down:
                session.player_down = max(0, session.player_down - dt)
                if session.player_down == 0:
                    session._respawn_player()
            session.field_step(session.field_input.actions)
            session.update_events(dt)
            self._systems(session)
        for scene_id, systems in tuple(self.systems.items()):
            scene = self.project.scene(scene_id)
            if not any(s.scene is scene for s in self.players.values()):
                continue
            host = self.hosts[scene_id]
            host._frame_collision_world = None
            systems["player_input"].update(scene, dt)
            systems["spawn"].update(scene, dt)
            systems["ai"].update(scene, dt)
            for entity, _spec in list(scene.query(AIController2DComponent)):
                target = self._nearest(scene, entity)
                systems["behavior"].target_id = target.id if target else ""
                systems["behavior"].update(_EntityScene(scene, entity), dt)
            host._frame_collision_world = None
            for name in (
                "action_combat",
                "actions",
                "controllers",
                "hits",
                "projectiles",
                "combat",
                "loot",
            ):
                if name == "combat":
                    self._active_combat_scene = scene
                systems[name].update(scene, dt)
        self._finish_rewards()
        self._save_elapsed += dt
        if self._save_elapsed >= 1:
            self._save_elapsed = 0
            for pid in self.players:
                self._save(pid)
        return self._update() if self.players else None

    def handle_command(self, player_id, command, payload):
        session = self._session(player_id)
        if not isinstance(payload, Mapping):
            raise ValueError("command payload must be an object")
        actor = self._actor(session)
        try:
            if command == "save":
                pass
            elif command == "equip":
                if "index" in payload:
                    session.equip_from_bag(actor, int(payload["index"]), payload.get("slot_id"))
                else:
                    session.equip_from_inventory(
                        actor, str(payload["equipment_id"]), payload.get("slot_id")
                    )
            elif command == "unequip":
                session.unequip_to_bag(actor, str(payload["slot_id"]))
            elif command in {"allocate", "allocate_attribute", "unlock_skill"}:
                session.allocate_progression(
                    actor, payload["graph_id"], payload["node_id"], payload.get("count", 1)
                )
            elif command == "change_class":
                session.set_active_classes(
                    actor, payload.get("class_ids", [payload.get("class_id", "")])
                )
            elif command == "bind_skill":
                from asteria.runtime.action_combat import ActionCombatComponent, parse_bindings

                action, ability = str(payload["action"]), str(payload["ability_id"])
                if action not in {
                    "attack",
                    "skill_1",
                    "skill_2",
                    "skill_3",
                    "skill_4",
                    "skill_5",
                    "skill_6",
                    "dodge",
                    "potion",
                }:
                    raise ValueError("unsupported binding action")
                if ability not in session._known_abilities(session.player):
                    raise ValueError("ability is not learned")
                spec = session.player.get(ActionCombatComponent)
                bindings = parse_bindings(spec.bindings)
                bindings[action] = ability
                spec.bindings = ";".join(f"{a}={b}" for a, b in bindings.items())
            elif command in {"buy", "sell"}:
                shop_id = payload.get("shop_id") or session.open_shop_id
                if not shop_id or shop_id != session.open_shop_id:
                    raise ValueError("shop is not open through a project interaction")
                getattr(session, command)(
                    str(payload["item_id"]), int(payload.get("quantity", 1)), shop_id=shop_id
                )
            elif command == "craft":
                station = str(payload.get("station") or session.open_crafting_station or "")
                if not session.open_crafting_station or station != session.open_crafting_station:
                    raise ValueError("crafting station is not open through a project interaction")
                session.craft(payload["payload"], station=station, rng=self.random)
            elif command == "close_shop":
                session.close_shop()
            elif command == "close_crafting":
                session.open_crafting_station = None
            elif command == "dialogue_ack":
                session.acknowledge_dialogue()
            elif command == "choose":
                session.choose(int(payload["index"]))
            elif command == "passive":
                old = session._ability_state(actor)
                wanted = tuple(str(x) for x in payload["passive_ids"])
                if any(x not in session.project.rpg_database.passives for x in wanted):
                    raise ValueError("unknown passive")
                old.active_passives = wanted
                session._store_ability_state(actor, old)
                session.refresh_combatant(session.player)
            elif command == "use_item":
                from asteria.rpg.items import use_inventory_item

                item_id = str(payload["item_id"])
                ability = self.project.gameplay_library.abilities.get(item_id)
                if ability and any(cost.resource == f"item:{item_id}" for cost in ability.costs):
                    # Authored ARPG consumables may heal through a timeline/state, rather than
                    # inventory use_effects. Use the same cooldown and item-cost path as input.
                    outcome = session.action_combat.use(
                        session.player, item_id, scene=session.scene
                    )
                    if outcome not in {"used", "combo"}:
                        raise ValueError(f"item ability unavailable: {outcome}")
                else:
                    state = session.combat.state(session.player)
                    definition = self.project.rpg_database.items[item_id]
                    result = use_inventory_item(
                        session.save.rpg_state.inventory,
                        definition,
                        state.stats,
                        state.resources,
                        state.tags,
                    )
                    if not result.used:
                        raise ValueError("item cannot be used")
                session.refresh_quests()
            elif command == "upgrade":
                item = session.save.rpg_state.loadouts[actor].equipped(str(payload["slot_id"]))[0]
                session.upgrade_equipment(actor, item.instance_id, payload["node_id"])
                session.refresh_combatant(session.player)
            elif command == "active_party":
                session.set_active_party(payload["actor_ids"], payload.get("placements"))
            elif command == "load":
                record = self.store.get_player(player_id)["game_state"].get(self.SAVE_NAMESPACE)
                if record is None:
                    raise ValueError("no saved player state")
                data = dict(record["save"])
                data["player_entity_id"] = session.player.id
                restored = GameRuntimeSave.from_data(data, self.project)
                session.transfer_player(
                    restored.scene_id,
                    *(restored.player_position or (None, None)),
                    facing=restored.player_facing,
                )
                session = GameSessionRuntime(self.project, restored)
                session.refresh_actor_combatants = lambda actor_id: session.refresh_combatant(
                    session.player
                )
                self.players[player_id] = session
                self._systems(session)
                session.refresh_combatant(session.player)
                if record.get("bindings"):
                    session.player.get(ActionCombatComponent).bindings = record["bindings"]
                if record.get("combatant"):
                    from asteria.gameplay import ResourcePool

                    state = session.combat.state(session.player)
                    state.resources = ResourcePool.from_data(record["combatant"]["resources"])
                    state.dead = bool(record["combatant"].get("dead", False))
                    if state.states is not None and record["combatant"].get("states"):
                        state.states.restore(record["combatant"]["states"])
                    if state.dead:
                        session.player_down = max(session.combat_scene.respawn_delay, 0.01)
            elif command == "pickup":
                loot_id = payload.get("loot_id")
                if loot_id:
                    entity = session.scene.get_entity(str(loot_id))
                    if entity is None or not entity.has(LootComponent):
                        raise ValueError("loot does not exist")
                    radius = session.player.get(LooterComponent).pickup_radius
                    p, t = session.player.get(Transform), entity.get(Transform)
                    if hypot(p.x - t.x, p.y - t.y) > radius:
                        raise ValueError("loot is out of reach")
                    if not session.loot.pick_up(session.scene, session.player, entity):
                        raise ValueError("loot cannot be picked up")
                else:
                    session.loot.pick_up_nearest(session.scene, session.player)
            elif command in {"interact", "transfer"}:
                controller = session.player.try_get(CharacterController2DComponent)
                if controller is not None:
                    session.facing = controller.facing
                # Only authored reachable interaction/touch triggers can transfer a player.
                if session.field_step({"interact": 1}) is None:
                    raise ValueError("no reachable project interaction")
                self._systems(session)
            else:
                raise ValueError(f"unsupported project command: {command}")
        except (KeyError, IndexError, TypeError, RuntimeError) as exc:
            raise ValueError(str(exc)) from exc
        self._save(player_id)
        self.events.append({"kind": "command", "player_id": player_id, "command": command})
        return self._update()

    def on_player_left(self, player_id):
        session = self._session(player_id)
        self._save(player_id)
        session.scene.remove_entity(session.player)
        self.players.pop(player_id)
        self.inputs.pop(player_id, None)
        self.events.append({"kind": "left", "player_id": player_id})
        return self._update()


def build_project_adapter(*, store, rules=None, project_path=None, project_root=None, **kwargs):
    configured = (rules or {}).get("project_runtime", {}).get("project_file")
    repo = Path(__file__).resolve().parents[3]
    path = (
        Path(project_path or configured)
        if (project_path or configured)
        else repo / "reference_projects" / "diablo_multiplayer_demo" / "project.asteria.json"
    )
    if not path.is_absolute():
        path = repo / path
    project = Project.load_json(path, default_component_registry())
    return ProjectDemoAdapter(
        store, project, project_root=project_root or path.parent, rules=rules, **kwargs
    )
