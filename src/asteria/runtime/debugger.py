"""Live runtime debugger (EDT-10, ASTERIA_SPEC §34).

Inspection: stats/resources, position, states/effects, abilities, animation,
AI, quest/world state, variables/switches, inventory and currencies.
Debug actions: give/remove item, change stats/resources, add/remove state,
teleport, trigger event, spawn/kill enemy, change quest/world state.

``RuntimeDebugger`` works on a live ``GameSessionRuntime`` (and, when given,
the ``PlayableTestRuntime`` host). Every action goes through the session's
own canonical APIs — the debugger adds no game rules. ``execute(command,
args)`` is the single entry point used by the editor over the debug server.
"""

from __future__ import annotations

from dataclasses import replace


class DebuggerError(ValueError):
    pass


def _resources(pool_data):
    return {k: {"current": v["current"], "maximum": v["maximum"]} for k, v in sorted(pool_data["values"].items())}


class RuntimeDebugger:
    def __init__(self, session, host=None):
        self.session = session
        self.host = host
        self.log = []  # (command, args, ok, message)

    @property
    def game(self):
        return self.host.game if self.host is not None else self.session

    # -- inspection ------------------------------------------------------------------
    def snapshot(self):
        from asteria.core import Transform

        game = self.game
        state = game.save.rpg_state
        ctx = game.save.event_context
        transform = game.player.get(Transform)
        data = {
            "mode": game.mode,
            "scene": {"id": game.scene.id, "name": game.scene.name},
            "player": {
                "entity_id": game.player.id,
                "position": list(game.save.player_position or (transform.x, transform.y)),
                "facing": game.facing,
            },
            "party": {},
            "inventory": dict(sorted(state.inventory.to_data()["counts"].items())),
            "currencies": dict(sorted(state.currencies.items())),
            "switches": dict(sorted(ctx.switches.items())),
            "variables": dict(sorted((k, v) for k, v in ctx.variables.items())),
            "quests": {k: v.to_data() for k, v in sorted(state.quests.items())},
            "world": state.world.to_data(),
            "field_entities": [],
            "battle": None,
        }
        for actor_id in state.party_actor_ids:
            snap = state.actor_snapshots.get(actor_id)
            entry = {"active": actor_id in state.party_active_actor_ids}
            if snap is not None:
                entry["stats"] = dict(sorted(snap.stats["values"].items()))
                entry["resources"] = _resources(snap.resources)
                entry["abilities"] = list((snap.ability_state or {}).get("learned_abilities", ()))
            data["party"][actor_id] = entry
        ai_states = {}
        simulation = getattr(game, "_field_simulation", {}).get(game.scene.id)
        if simulation:
            ai_states = {k: v.mode for k, v in simulation["ai"].states.items()}
            ai_states.update({k: f"tree:{v}" for k, v in simulation["behavior"].status.items()})
        for entity in game.scene.entities():
            if not entity.has(Transform) or entity is game.player:
                continue
            t = entity.get(Transform)
            data["field_entities"].append(
                {"id": entity.id, "name": entity.name, "position": [t.x, t.y], "ai": ai_states.get(entity.id)}
            )
        if game.battle is not None:
            adapter = getattr(self.host, "_battle_presentation", None) if self.host is not None else None
            members = {}
            for side, party in game.battle.parties.items():
                for member in party.members:
                    subject = member.subject
                    animation = None
                    screen = getattr(adapter, "screen", None)
                    if screen is not None:
                        try:
                            role = screen.animation.combatant(member.member_id).role
                            animation = str(getattr(role, "value", role))
                        except KeyError:
                            animation = None
                    members[member.member_id] = {
                        "side": side,
                        "active": game.battle.is_active(member),
                        "stats": dict(sorted(subject.stats.to_data()["values"].items())),
                        "resources": _resources(subject.resources.to_data()),
                        "states": [s.state_id for s in subject.states.active_states()] if subject.states else [],
                        "abilities": list(member.ability_ids),
                        "animation": animation,
                    }
            data["battle"] = {"encounter_id": game.encounter_id, "members": members}
        return data

    # -- actions ---------------------------------------------------------------------
    def execute(self, command, args=None):
        args = dict(args or {})
        handler = getattr(self, f"cmd_{command}", None)
        if handler is None or command.startswith("_"):
            raise DebuggerError(f"unknown debug command {command}")
        try:
            result = handler(**args)
        except DebuggerError as exc:
            self.log.append((command, args, False, str(exc)))
            raise
        except (KeyError, TypeError, ValueError) as exc:
            self.log.append((command, args, False, str(exc)))
            raise DebuggerError(f"{command}: {exc}") from exc
        self.log.append((command, args, True, ""))
        return result

    def cmd_snapshot(self):
        return self.snapshot()

    def cmd_give_item(self, item_id, quantity=1):
        if item_id not in self.game.project.rpg_database.items:
            raise DebuggerError(f"unknown item {item_id}")
        self.game.save.rpg_state.inventory.add(item_id, int(quantity))
        self.game.refresh_quests()
        return self.game.save.rpg_state.inventory.count(item_id)

    def cmd_remove_item(self, item_id, quantity=1):
        if not self.game.save.rpg_state.inventory.remove(item_id, int(quantity)):
            raise DebuggerError(f"not enough {item_id}")
        return self.game.save.rpg_state.inventory.count(item_id)

    def cmd_set_currency(self, currency_id, amount):
        if float(amount) < 0:
            raise DebuggerError("currency cannot be negative")
        self.game.save.rpg_state.currencies[str(currency_id)] = float(amount)
        return float(amount)

    def _battle_member(self, member_id):
        battle = self.game.battle
        if battle is None or member_id not in battle.members:
            return None
        return battle.member(member_id)

    def cmd_set_resource(self, member_id, resource_id, value):
        member = self._battle_member(member_id)
        if member is not None:
            member.subject.resources.set_current(resource_id, float(value))
            return member.subject.resources.current(resource_id)
        snapshots = self.game.save.rpg_state.actor_snapshots
        if member_id not in snapshots:
            raise DebuggerError(f"unknown member {member_id}")
        snap = snapshots[member_id]
        resources = {**snap.resources, "values": {k: dict(v) for k, v in snap.resources["values"].items()}}
        entry = resources["values"].get(resource_id)
        if entry is None:
            raise DebuggerError(f"{member_id} has no resource {resource_id}")
        entry["current"] = max(entry.get("minimum", 0.0), min(entry["maximum"], float(value)))
        snapshots[member_id] = replace(snap, resources=resources)
        return entry["current"]

    def cmd_set_stat(self, member_id, stat, value):
        member = self._battle_member(member_id)
        if member is not None:
            member.subject.stats.set(stat, float(value))
            return member.subject.stats.get(stat)
        snapshots = self.game.save.rpg_state.actor_snapshots
        if member_id not in snapshots:
            raise DebuggerError(f"unknown member {member_id}")
        snap = snapshots[member_id]
        if stat not in snap.stats["values"]:
            raise DebuggerError(f"{member_id} has no stat {stat}")
        stats = {**snap.stats, "values": {**snap.stats["values"], stat: float(value)}}
        snapshots[member_id] = replace(snap, stats=stats)
        return float(value)

    def cmd_add_state(self, member_id, state_id, source_id=None):
        battle = self.game.battle
        if battle is None or member_id not in battle.members:
            raise DebuggerError("states can be added to battle members only")
        result = battle.apply_state(state_id, source_id or member_id, member_id)
        return getattr(result, "applied", True)

    def cmd_remove_state(self, member_id, state_id):
        member = self._battle_member(member_id)
        if member is None or member.subject.states is None:
            raise DebuggerError("states exist on battle members only")
        return member.subject.states.remove(state_id, run_remove_effects=True)

    def cmd_teleport(self, x, y, scene_id=None):
        game = self.game
        if game.mode != "field":
            raise DebuggerError("teleport is only available in the field")
        if scene_id and scene_id != game.scene.id:
            game.transfer_player(scene_id, float(x), float(y))
        else:
            game.set_player_position(float(x), float(y))
        return list(game.save.player_position)

    def cmd_trigger_event(self, program_id):
        game = self.game
        if program_id not in game.project.event_programs.ids():
            raise DebuggerError(f"unknown event program {program_id}")
        game.events.start(program_id, replace=True)
        game.update_events(0.0)
        return game.events.active.program_id if game.events.active else None

    def cmd_spawn_enemy(self, enemy_id=None, prefab_id=None, x=0.0, y=0.0):
        game = self.game
        if game.battle is not None and enemy_id:
            index = len(game.battle.members) + 1
            member = game._enemy_member(enemy_id, index)
            game.battle.summon(member, join_current_round=True)
            return member.member_id
        if prefab_id:
            from asteria.core import Transform
            from asteria.core.prefab import instantiate
            from asteria.runtime.preview import build_preview_registry

            entity = instantiate(game.project.prefabs, prefab_id, build_preview_registry())
            if not entity.has(Transform):
                entity.add_component(Transform())
            entity.get(Transform).x, entity.get(Transform).y = float(x), float(y)
            game.scene.add_entity(entity)
            return entity.id
        raise DebuggerError("spawn needs enemy_id (in battle) or prefab_id (in the field)")

    def cmd_kill_enemy(self, target_id):
        game = self.game
        member = self._battle_member(target_id)
        if member is not None:
            resource = game.rules.knockout_resource_id
            if not resource:
                raise DebuggerError("project has no knockout resource")
            member.subject.resources.set_current(resource, 0.0)
            return not game.battle.is_active(member)
        entity = game.scene.get_entity(target_id)
        if entity is None or entity is game.player:
            raise DebuggerError(f"unknown enemy {target_id}")
        game.scene.remove_entity(entity)
        return True

    def cmd_set_switch(self, name, value=True):
        self.game.save.event_context.set_switch(name, bool(value))
        self.game.refresh_quests()
        return bool(value)

    def cmd_set_variable(self, name, value):
        self.game.save.event_context.set_variable(name, value)
        return value

    def cmd_quest(self, action, quest_id, objective_id=None, amount=1):
        game = self.game
        if action == "start":
            return game.start_quest(quest_id)
        if action == "complete":
            return bool(game.complete_quest(quest_id))
        if action == "fail":
            game.fail_quest(quest_id)
            return "failed"
        if action == "advance":
            return game.advance_quest(quest_id, objective_id, int(amount))
        raise DebuggerError(f"unknown quest action {action}")

    def cmd_reputation(self, faction_id, amount):
        return self.game.change_reputation(faction_id, float(amount))
