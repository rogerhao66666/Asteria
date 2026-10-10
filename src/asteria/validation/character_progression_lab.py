from __future__ import annotations

from dataclasses import dataclass

from asteria.rpg import (
    ActorDefinition,
    ClassAssignment,
    ProgressionMilestone,
    ProgressionRuntime,
    ProgressionTrackDefinition,
    RpgActorRuntime,
)

from .playable_rpg import ReferenceActorScenario, build_reference_actor_scenario


@dataclass(frozen=True, slots=True)
class CharacterProgressionLabSnapshot:
    level_rank: int
    experience_total: float
    unlocked_jobs: tuple[str, ...]
    class_assignments: tuple[tuple[str, str, str], ...]
    skill_balances: tuple[tuple[str, float], ...]
    allocated_nodes: tuple[tuple[str, str, int], ...]
    active_passives: tuple[str, ...]
    resolved_abilities: tuple[str, ...]


class CharacterProgressionLab:
    """Operable reference-project controller over canonical RPG runtimes.

    Job-slot policy and unlock policy live here, not in the engine. Canonical
    Asteria class definitions, actor runtime, progression runtimes, allocation
    runtime and ability/passive state perform the actual state transitions.
    """

    def __init__(self, scenario: ReferenceActorScenario | None = None):
        self.scenario = scenario or build_reference_actor_scenario()
        self.class_catalog = dict(self.scenario.actor.class_definitions)
        self._base_definition = self.scenario.actor.definition
        self._slot_order = ("primary", "secondary")
        self._slot_jobs = {
            "primary": self.scenario.actor.class_assignments[0].class_id,
            "secondary": (
                self.scenario.actor.class_assignments[1].class_id
                if len(self.scenario.actor.class_assignments) > 1
                else None
            ),
        }
        self.unlocked_jobs = {self._slot_jobs["primary"]}

        # Reference-project level/EXP track. The engine mechanism is generic.
        self.progression = ProgressionRuntime(
            (
                ProgressionTrackDefinition(
                    "character_level",
                    milestones=(
                        ProgressionMilestone(1, 0),
                        ProgressionMilestone(2, 100),
                        ProgressionMilestone(3, 250),
                        ProgressionMilestone(4, 450),
                    ),
                ),
            )
        )

        # Make the lab genuinely operable from a clean allocation state.
        for graph_id, ranks in list(self.scenario.allocations.allocations.items()):
            for node_id, rank in list(ranks.items()):
                if rank:
                    self.scenario.allocations.refund(graph_id, node_id, rank, refund_ratio=1.0)

        # Preserve learned abilities/passives but rebuild job assignments through
        # the same canonical actor runtime path.
        self._rebuild_actor()

    @property
    def level(self):
        return self.progression.rank("character_level")

    @property
    def experience(self):
        return self.progression.total("character_level")

    def award_experience(self, amount):
        return self.progression.add("character_level", amount)

    def unlock_job(self, class_id):
        class_id = str(class_id)
        if class_id not in self.class_catalog:
            raise KeyError(class_id)
        self.unlocked_jobs.add(class_id)
        return class_id

    def set_job(self, slot_id, class_id):
        slot_id = str(slot_id)
        class_id = str(class_id)
        if slot_id not in self._slot_order:
            raise KeyError(slot_id)
        if class_id not in self.class_catalog:
            raise KeyError(class_id)
        if class_id not in self.unlocked_jobs:
            raise ValueError(f"job is locked: {class_id}")
        for other_slot, other_class in self._slot_jobs.items():
            if other_slot != slot_id and other_class == class_id:
                raise ValueError("same job cannot occupy two reference-lab slots")
        self._slot_jobs[slot_id] = class_id
        self._rebuild_actor()
        return self.scenario.actor

    def clear_job(self, slot_id):
        slot_id = str(slot_id)
        if slot_id == "primary":
            raise ValueError("reference lab requires a primary job")
        if slot_id not in self._slot_order:
            raise KeyError(slot_id)
        self._slot_jobs[slot_id] = None
        self._rebuild_actor()
        return self.scenario.actor

    def allocate_node(self, graph_id, node_id, count=1):
        return self.scenario.allocations.allocate(graph_id, node_id, count)

    def refund_node(self, graph_id, node_id, count=1, *, refund_ratio=1.0):
        return self.scenario.allocations.refund(graph_id, node_id, count, refund_ratio=refund_ratio)

    def equip_passive(self, passive_id, *, capacity=2):
        passive_id = str(passive_id)
        if passive_id not in self.scenario.passives:
            raise KeyError(passive_id)
        return self.scenario.actor.ability_state.equip_passive(passive_id, capacity=capacity)

    def unequip_passive(self, passive_id):
        self.scenario.actor.ability_state.unequip_passive(passive_id)

    def resolve(self):
        return self.scenario.resolve()

    def _rebuild_actor(self):
        old_state = self.scenario.actor.ability_state.to_data()
        assignments = []
        for priority, slot_id in enumerate(self._slot_order):
            class_id = self._slot_jobs.get(slot_id)
            if class_id is None:
                continue
            assignments.append(
                ClassAssignment(
                    class_id,
                    assignment_id=f"job:{slot_id}",
                    role=slot_id,
                    priority=priority,
                )
            )
        definition = ActorDefinition(
            self._base_definition.actor_id,
            self._base_definition.display_name,
            class_assignments=tuple(assignments),
            base_stats=self._base_definition.base_stats,
            base_resources=self._base_definition.base_resources,
            tags=self._base_definition.tags,
            abilities=self._base_definition.abilities,
        )
        actor = RpgActorRuntime(definition, class_definitions=self.class_catalog)
        actor.ability_state = type(actor.ability_state).from_data(old_state)
        self.scenario.actor = actor

    def snapshot(self):
        allocations = []
        for graph_id in sorted(self.scenario.allocations.allocations):
            for node_id, rank in sorted(self.scenario.allocations.allocations[graph_id].items()):
                allocations.append((graph_id, node_id, int(rank)))
        assignments = tuple((x.assignment_id, x.role, x.class_id) for x in self.scenario.actor.class_assignments)
        build = self.resolve()
        return CharacterProgressionLabSnapshot(
            self.level,
            self.experience,
            tuple(sorted(self.unlocked_jobs)),
            assignments,
            tuple(sorted(self.scenario.allocations.balances.items())),
            tuple(allocations),
            tuple(self.scenario.actor.ability_state.active_passives),
            tuple(build.abilities),
        )
