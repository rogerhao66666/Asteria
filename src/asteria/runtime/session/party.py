"""The party: transfers, classes, members joining and leaving, abilities, passives, progression and
experience."""

from __future__ import annotations

from asteria.core.scene_transition import carry_persistent_entities
from asteria.rpg import (
    ActorAbilityState,
    ActorProgressionState,
    RpgActorSnapshot,
)
from asteria.runtime.world_command_handlers import (
    move_entity_to_scene,
)

from .support import (  # noqa: F401 - the names the moved methods use
    BattleLogEntry,
    EquipOffer,
    GameSessionError,
    _base_relative,
    _EitherBlocks,
    _merge_casts,
    describe_condition,
)


class PartyMixin:
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
            for class_id in values:
                if class_id not in state.unlocked_class_ids:
                    self._check_class_unlock(state, self.project.rpg_database.classes[class_id])
            unlocked = tuple(dict.fromkeys(state.unlocked_class_ids + values))
            self.save.rpg_state.actor_progression[actor_id] = ActorProgressionState(
                state.level,
                state.experience,
                points=state.points,
                unlocked_class_ids=unlocked,
                active_class_ids=state.active_class_ids,
            )
        return self.set_active_classes(actor_id, values)

    def _check_class_unlock(self, state, definition):
        """A job with unlock rules stays closed until the actor's level and jobs are enough."""
        if state.level < definition.unlock_level:
            raise GameSessionError(
                f"{definition.display_name} needs level {definition.unlock_level}"
            )
        missing = [c for c in definition.unlock_classes if c not in state.unlocked_class_ids]
        if missing:
            names = [self.project.rpg_database.classes[c].display_name for c in missing]
            raise GameSessionError(f"{definition.display_name} needs the job " + ", ".join(names))

    def join_party(self, actor_id, *, active=True):
        """A story event brings ``actor_id`` into the party: the roster, and the active party
        (with the next free formation slot) while there is room."""
        actor_id = str(actor_id)
        db = self.project.rpg_database
        if actor_id not in db.actors:
            raise GameSessionError(f"unknown actor: {actor_id}")
        state = self.save.rpg_state
        if actor_id not in state.party_actor_ids:
            state.party_actor_ids = (*state.party_actor_ids, actor_id)
        self.ensure_actor_progression(actor_id)
        if not active or actor_id in state.party_active_actor_ids:
            return actor_id
        setup = next(iter(db.party_setups.values()), None)
        if setup is not None and len(state.party_active_actor_ids) >= setup.active_capacity:
            return actor_id  # no room: it waits in the roster
        state.party_active_actor_ids = (*state.party_active_actor_ids, actor_id)
        formation = db.formations.get(setup.formation_id) if setup is not None else None
        if formation is not None:
            taken = set(state.party_placements.values())
            free = next((s.slot_id for s in formation.slots if s.slot_id not in taken), None)
            if free is not None:
                state.party_placements[actor_id] = free
        return actor_id

    def rest_party(self):
        """An inn or a camp: every roster member's resources go back to their maximum."""
        from asteria.gameplay import ResourcePool

        snapshots = self.save.rpg_state.actor_snapshots
        for actor_id in self.save.rpg_state.party_actor_ids:
            old = snapshots.get(actor_id)
            if old is None:  # never fought: its next build is already full
                continue
            pool = ResourcePool.from_data(old.resources)
            for name in tuple(pool.to_data()["values"]):
                pool.set_current(name, pool.maximum(name))
            snapshots[actor_id] = RpgActorSnapshot(
                old.actor_id, old.stats, pool.to_data(), old.tags, old.ability_state
            )
        return tuple(self.save.rpg_state.party_actor_ids)

    def leave_party(self, actor_id):
        actor_id = str(actor_id)
        state = self.save.rpg_state
        state.party_actor_ids = tuple(a for a in state.party_actor_ids if a != actor_id)
        state.party_active_actor_ids = tuple(
            a for a in state.party_active_actor_ids if a != actor_id
        )
        state.party_placements.pop(actor_id, None)
        return actor_id

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
        snapshot = self.save.rpg_state.actor_snapshots.get(str(actor_id))
        return (
            ActorAbilityState()
            if snapshot is None or snapshot.ability_state is None
            else ActorAbilityState.from_data(snapshot.ability_state)
        )

    def _store_ability_state(self, actor_id, state):
        actor_id = str(actor_id)
        old = self.save.rpg_state.actor_snapshots.get(actor_id)
        if old is None:  # an actor that was never in a fight: snapshot its base
            base = self._actor_runtime(actor_id)
            old = RpgActorSnapshot(
                actor_id, base.stats.to_data(), base.resources.to_data(), base.tags.to_data()
            )
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
        before = set(self.slot_candidates(actor_id))
        result = allocation.allocate(str(graph_id), str(node_id), int(count))
        for ability_id in self.slot_candidates(actor_id):  # a new skill takes a free slot
            if ability_id not in before:
                try:
                    self.equip_ability(actor_id, ability_id)
                except GameSessionError:
                    break  # the slots are full: the player chooses in the Skill Slots screen
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
        points_per_level=None,
        level_track="",
    ):
        """Generic acceptance/runtime helper for actor-level progression.

        ``level_track`` names a progression track whose milestones are the experience totals of
        each level (a curve the author draws); without it every ``level_threshold`` is a level.

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
        if level_track:
            track = self.project.rpg_database.progression_tracks.get(str(level_track))
            if track is None:
                raise GameSessionError(f"unknown level track {level_track}")
            new_level = max(old_level, track.rank_for(total))
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
            for name, amount in dict(points_per_level or {}).items():  # any named balance
                earned = gained * float(amount)
                points[name] = points.get(name, 0.0) + earned
                if allocation is not None and earned:
                    allocation.grant(name, earned)
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
