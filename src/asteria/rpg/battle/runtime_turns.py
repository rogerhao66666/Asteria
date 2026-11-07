"""A battle's turns: who acts next, cooldowns, the next turn and round, snapshots, the
outcome."""

from __future__ import annotations

from asteria.core.lifecycle import emit_hook
from asteria.rpg.battle.runtime_types import BattleOutcome
from asteria.rpg.battle.scheduler import BattleSchedulerMode
from asteria.rpg.battle.snapshot import capture_battle_snapshot, restore_battle_snapshot


class BattleTurnsMixin:
    """``BattleRuntime``'s turns: next actor, cooldowns, rounds, snapshots, the outcome."""

    def snapshot(self):
        return capture_battle_snapshot(self)

    def restore_snapshot(self, snapshot):
        restore_battle_snapshot(self, snapshot)
        emit_hook(self.hooks, "rpg.battle.snapshot_restored", data={"battle": self})
        return self

    def next_actor(self):
        skipped = 0
        while True:
            entry = self.turn_queue.peek()
            if (
                self.scheduler is not None
                and self.scheduler.mode == BattleSchedulerMode.CONTINUOUS
                and entry is not None
            ):
                self.resolve_due_actions(entry.ready_time)
                entry = self.turn_queue.peek()
            while entry is not None and not self.can_act(entry.member_id):
                self.turn_queue.pop()
                entry = self.turn_queue.peek()
            if entry is None:
                return None
            actor = self.member(entry.member_id)
            ready_key = (
                self.turn_queue.round_index,
                entry.member_id,
                getattr(entry, "ready_time", None),
            )
            if self._resource_ready_entry != ready_key:
                self.battle_resources.apply_trigger("rpg.battle.turn_ready", (actor.member_id,))
                self.battle_states.apply_trigger("rpg.battle.turn_ready", (actor,))
                self._resource_ready_entry = ready_key
            availability = self.battle_states.ability_availability(actor.subject, ())
            if not availability.allowed:
                emit_hook(
                    self.hooks,
                    "rpg.battle.turn_skipped",
                    source=actor.member_id,
                    data={
                        "actor": actor,
                        "blocking_states": availability.blocking_states,
                        "round_index": self.turn_queue.round_index,
                    },
                )
                self.advance_turn()
                skipped += 1
                if skipped > 10000:
                    raise RuntimeError("battle scheduler could not find an actionable combatant")
                continue
            emit_hook(
                self.hooks,
                "rpg.battle.turn_ready",
                source=actor.member_id,
                data={
                    "actor": actor,
                    "round_index": self.turn_queue.round_index,
                    "timeline_time": getattr(self.turn_queue, "current_time", None),
                },
            )
            return actor

    def cooldown_remaining(self, member_id, ability_id):
        """Turns of ``member_id`` before ``ability_id`` can be used again (0 = ready)."""
        return self.cooldowns.get(str(member_id), {}).get(str(ability_id), 0)

    def _start_cooldown(self, member_id, ability_id):
        definition = self.ability_runtime.registry.get(ability_id)
        turns = getattr(definition, "cooldown_turns", 0) if definition is not None else 0
        if turns and (member_id, ability_id) not in self._used_this_turn:
            self.cooldowns.setdefault(member_id, {})[ability_id] = int(turns)
        self._used_this_turn.add((member_id, ability_id))

    def _tick_cooldowns(self, member_id):
        """End of ``member_id``'s turn: its cooldowns count down, except those started in this
        turn."""
        member_id = str(member_id)
        waiting = self.cooldowns.get(member_id, {})
        for ability_id in list(waiting):
            if (member_id, ability_id) not in self._used_this_turn:
                waiting[ability_id] -= 1
                if waiting[ability_id] <= 0:
                    del waiting[ability_id]
        self._used_this_turn = {x for x in self._used_this_turn if x[0] != member_id}

    def advance_turn(self, *, recovery=0.0):
        entry = self.turn_queue.pop()
        if entry is not None:
            self._tick_cooldowns(entry.member_id)
        if entry is not None and recovery and self.scheduler is not None:
            self.scheduler.shift_member(entry.member_id, float(recovery))
        if entry is not None:
            self._resource_ready_entry = None
            self.battle_resources.apply_trigger("rpg.battle.turn_ended", (entry.member_id,))
            self.battle_states.apply_trigger(
                "rpg.battle.turn_ended", (self.member(entry.member_id),)
            )
            emit_hook(
                self.hooks,
                "rpg.battle.turn_ended",
                source=entry.member_id,
                data={"entry": entry, "round_index": self.turn_queue.round_index},
            )
        return entry

    def _on_stage(self):
        """Every member but the benched ones (their states wait with them)."""
        return tuple(m for k, m in self.members.items() if k not in self.benched)

    def start_next_round(self):
        self.battle_resources.apply_trigger("rpg.battle.round_ended")
        self.battle_states.apply_trigger("rpg.battle.round_ended", self._on_stage())
        emit_hook(
            self.hooks,
            "rpg.battle.round_ended",
            data={"round_index": self.turn_queue.round_index},
        )
        entries = self.turn_queue.start_round()
        self._resource_ready_entry = None
        self.battle_resources.apply_trigger("rpg.battle.round_started")
        self.battle_states.apply_trigger("rpg.battle.round_started", self._on_stage())
        emit_hook(
            self.hooks,
            "rpg.battle.round_started",
            data={"round_index": self.turn_queue.round_index},
        )
        return entries

    def resolve_outcome(self):
        objective_results = self.objectives.evaluate(self)
        completed = []
        for objective_id, status in objective_results:
            if status not in {"succeeded", "failed"}:
                continue
            definition = self.objectives.definitions[objective_id]
            if status == "succeeded":
                outcome = BattleOutcome(
                    True,
                    tuple(sorted(definition.winning_sides)),
                    tuple(sorted(definition.defeated_sides)),
                    tuple(sorted(self._escaped_sides)),
                    (objective_id,),
                )
            else:
                outcome = BattleOutcome(
                    True,
                    tuple(sorted(definition.failure_winning_sides)),
                    tuple(sorted(definition.failure_defeated_sides)),
                    tuple(sorted(self._escaped_sides)),
                    (objective_id,),
                )
            completed.append(outcome)
        if completed:
            outcome = completed[0]
        elif self._escaped_sides:
            outcome = BattleOutcome(
                True,
                (),
                (),
                tuple(sorted(self._escaped_sides)),
                (),
            )
        elif self.objectives.definitions:
            outcome = BattleOutcome(False, (), (), (), ())
        else:
            active_sides = []
            defeated = []
            for side, party in self.parties.items():
                if any(
                    member.member_id in self.members
                    and member.member_id not in self.outcome_exempt
                    and (
                        self.is_active(member)
                        or (member.member_id in self.benched and self.standing(member))
                    )
                    for member in party.members
                ):
                    active_sides.append(side)
                else:
                    defeated.append(side)
            finished = len(active_sides) <= 1
            outcome = BattleOutcome(
                finished,
                tuple(sorted(active_sides)) if finished else (),
                tuple(sorted(defeated)),
                tuple(sorted(self._escaped_sides)),
                (),
            )
        emit_hook(self.hooks, "rpg.battle.outcome_resolved", data={"outcome": outcome})
        if outcome.finished and not self._resources_finished:
            self.battle_resources.apply_trigger("rpg.battle.finished")
            self.battle_resources.finish()
            self._resources_finished = True
            emit_hook(self.hooks, "rpg.battle.finished", data={"outcome": outcome})
        return outcome
