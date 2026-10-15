from __future__ import annotations

from dataclasses import dataclass

from asteria.gameplay import ResourcePool, StatBlock, TagSet

from .ability_build import AbilityGrant
from .actors import RpgActorRuntime


@dataclass(frozen=True, slots=True)
class BuildContribution:
    """Explainable origin for one resolved actor-build contribution."""

    category: str
    key: str
    source_kind: str
    source_id: str
    value: object | None = None


@dataclass(frozen=True, slots=True)
class ResolvedActorBuild:
    """Canonical immutable view consumed by battle, AI, editor and UI layers.

    This object intentionally contains resolved values plus provenance rather
    than mutable gameplay state.  The source ``RpgActorRuntime`` remains the
    owner of intrinsic runtime state.
    """

    actor_id: str
    stats: StatBlock
    resources: ResourcePool
    tags: TagSet
    capabilities: tuple[str, ...]
    abilities: tuple[str, ...]
    ability_grants: tuple[AbilityGrant, ...]
    active_passives: tuple[str, ...]
    class_assignment_ids: tuple[str, ...]
    equipment_instance_ids: tuple[str, ...]
    triggers: tuple[object, ...]
    contributions: tuple[BuildContribution, ...]

    def sources_for(self, category, key):
        category = str(category)
        key = str(key)
        return tuple(x for x in self.contributions if x.category == category and x.key == key)

    def ability_sources(self, ability_id):
        ability_id = str(ability_id)
        return tuple(x for x in self.ability_grants if x.ability_id == ability_id)

    def to_summary_data(self):
        """Portable inspection data; not a save-state format."""
        return {
            "schema": "asteria.rpg.resolved_actor_build_summary",
            "version": 1,
            "actor_id": self.actor_id,
            "stats": self.stats.to_data(),
            "resources": self.resources.to_data(),
            "tags": list(self.tags.values()),
            "capabilities": list(self.capabilities),
            "abilities": list(self.abilities),
            "active_passives": list(self.active_passives),
            "class_assignment_ids": list(self.class_assignment_ids),
            "equipment_instance_ids": list(self.equipment_instance_ids),
            "contributions": [
                {
                    "category": x.category,
                    "key": x.key,
                    "source_kind": x.source_kind,
                    "source_id": x.source_id,
                    "value": x.value,
                }
                for x in self.contributions
            ],
        }


def _copy_resources(pool):
    return ResourcePool.from_data(pool.to_data())


def _apply_resource_bonus(pool, resource_id, amount):
    amount = float(amount)
    if not pool.contains(resource_id):
        maximum = max(0.0, amount)
        pool.define(resource_id, maximum, current=maximum)
        return
    current = pool.get(resource_id)
    maximum = current.maximum + amount
    if maximum < current.minimum:
        maximum = current.minimum
    new_current = min(max(current.current + amount, current.minimum), maximum)
    pool.define(
        resource_id,
        maximum,
        minimum=current.minimum,
        current=new_current,
        replace=True,
    )


def resolve_actor_build(
    actor_runtime: RpgActorRuntime,
    *,
    progression=None,
    allocations=None,
    loadout=None,
    passives=None,
    evolution_rules=(),
):
    """Resolve every Phase-7B actor-build layer through one canonical path."""
    if not isinstance(actor_runtime, RpgActorRuntime):
        raise TypeError("actor_runtime must be RpgActorRuntime")

    passive_map = dict(passives or {})
    contributions = []

    # Intrinsic/class state was already composed into the mutable runtime at
    # construction.  Record definition-level origins separately for inspection.
    for stat, value in actor_runtime.definition.base_stats.items():
        contributions.append(
            BuildContribution("stat", stat, "intrinsic", actor_runtime.definition.actor_id, value)
        )
    for resource_id, raw in actor_runtime.definition.base_resources.items():
        contributions.append(
            BuildContribution(
                "resource",
                resource_id,
                "intrinsic",
                actor_runtime.definition.actor_id,
                raw["maximum"],
            )
        )
    for tag in actor_runtime.definition.tags:
        contributions.append(
            BuildContribution("tag", tag, "intrinsic", actor_runtime.definition.actor_id)
        )

    for assignment in actor_runtime.class_assignments:
        definition = actor_runtime.class_definitions[assignment.class_id]
        for stat, value in definition.stat_bonuses.items():
            contributions.append(
                BuildContribution("stat", stat, "class", assignment.assignment_id, value)
            )
        for resource_id, value in definition.resource_bonuses.items():
            contributions.append(
                BuildContribution(
                    "resource", resource_id, "class", assignment.assignment_id, value
                )
            )
        for tag in definition.granted_tags:
            contributions.append(BuildContribution("tag", tag, "class", assignment.assignment_id))
        for tag in assignment.tags:
            contributions.append(
                BuildContribution("tag", tag, "class_assignment", assignment.assignment_id)
            )

    progression_stats, progression_tags, _ = actor_runtime._progression_contributions(progression)
    for stat, value in progression_stats.items():
        contributions.append(BuildContribution("stat", stat, "progression", "progression", value))
    for tag in sorted(progression_tags):
        contributions.append(BuildContribution("tag", tag, "progression", "progression"))

    allocation_contribution = None if allocations is None else allocations.contribution()
    if allocation_contribution is not None:
        for stat, value in allocation_contribution.stat_bonuses.items():
            contributions.append(
                BuildContribution("stat", stat, "allocation", "allocation", value)
            )
        for resource_id, value in allocation_contribution.resource_bonuses.items():
            contributions.append(
                BuildContribution("resource", resource_id, "allocation", "allocation", value)
            )
        for tag in allocation_contribution.granted_tags:
            contributions.append(BuildContribution("tag", tag, "allocation", "allocation"))
        for capability in allocation_contribution.granted_capabilities:
            contributions.append(
                BuildContribution("capability", capability, "allocation", "allocation")
            )

    if loadout is not None:
        for item in loadout.working():
            for tag in item.equipment.tags:
                contributions.append(BuildContribution("tag", tag, "equipment", item.instance_id))
            growth = item.growth_contribution()
            if growth is not None:
                for tag in growth.granted_tags:
                    contributions.append(
                        BuildContribution("tag", tag, "equipment_growth", item.instance_id)
                    )
                for capability in growth.granted_capabilities:
                    contributions.append(
                        BuildContribution(
                            "capability", capability, "equipment_growth", item.instance_id
                        )
                    )
                for modifier in growth.modifiers:
                    contributions.append(
                        BuildContribution(
                            "stat_modifier",
                            modifier.stat,
                            "equipment_growth",
                            item.instance_id,
                            modifier.modifier_id,
                        )
                    )
            for modifier in item.equipment.modifiers:
                contributions.append(
                    BuildContribution(
                        "stat_modifier",
                        modifier.stat,
                        "equipment",
                        item.instance_id,
                        modifier.modifier_id,
                    )
                )
            for affix in item.rolled_affixes:  # rpg.loot: random affixes rolled on this instance
                for modifier in affix.modifiers(item.instance_id):
                    contributions.append(
                        BuildContribution(
                            "stat_modifier",
                            modifier.stat,
                            "affix",
                            item.instance_id,
                            modifier.modifier_id,
                        )
                    )
            for socket_id in sorted(item.attachments):
                attachment = item.attachments[socket_id]
                source_id = f"{item.instance_id}:{socket_id}"
                for tag in attachment.tags:
                    contributions.append(BuildContribution("tag", tag, "attachment", source_id))
                for modifier in attachment.modifiers:
                    contributions.append(
                        BuildContribution(
                            "stat_modifier",
                            modifier.stat,
                            "attachment",
                            source_id,
                            modifier.modifier_id,
                        )
                    )

    for passive_id in actor_runtime.ability_state.active_passives:
        passive = passive_map.get(passive_id)
        if passive is None:
            continue
        for tag in passive.tags:
            contributions.append(BuildContribution("tag", tag, "passive", passive_id))
        for modifier in passive.modifiers:
            contributions.append(
                BuildContribution(
                    "stat_modifier", modifier.stat, "passive", passive_id, modifier.modifier_id
                )
            )

    stats = actor_runtime.effective_stats(
        progression=progression,
        allocations=allocations,
        loadout=loadout,
        passives=passive_map,
    )
    resources = _copy_resources(actor_runtime.resources)
    if allocation_contribution is not None:
        for resource_id, amount in allocation_contribution.resource_bonuses.items():
            _apply_resource_bonus(resources, resource_id, amount)

    tags = actor_runtime.effective_tags(
        progression=progression,
        allocations=allocations,
        loadout=loadout,
        passives=passive_map,
    )
    capabilities = tuple(sorted(tags.values()))

    ability_resolution = actor_runtime.resolve_abilities(
        progression=progression,
        allocations=allocations,
        loadout=loadout,
        passives=passive_map,
        evolution_rules=evolution_rules,
    )
    for grant in ability_resolution.grants:
        contributions.append(
            BuildContribution("ability", grant.ability_id, grant.source_kind, grant.source_id)
        )

    triggers = []
    if loadout is not None:
        triggers.extend(loadout.triggers())
    for passive_id in actor_runtime.ability_state.active_passives:
        passive = passive_map.get(passive_id)
        if passive is not None:
            triggers.extend(passive.triggers)

    return ResolvedActorBuild(
        actor_id=actor_runtime.definition.actor_id,
        stats=stats,
        resources=resources,
        tags=tags,
        capabilities=capabilities,
        abilities=ability_resolution.abilities,
        ability_grants=ability_resolution.grants,
        active_passives=tuple(actor_runtime.ability_state.active_passives),
        class_assignment_ids=tuple(x.assignment_id for x in actor_runtime.class_assignments),
        equipment_instance_ids=()
        if loadout is None
        else tuple(x.instance_id for x in loadout.equipped()),
        triggers=tuple(triggers),
        contributions=tuple(contributions),
    )


def resolve_actor_from_state(actor_id, database, runtime_state):
    """Convenience resolver for canonical Project + RPG save data."""
    actor_id = str(actor_id)
    if actor_id not in database.actors:
        raise KeyError(f"unknown actor: {actor_id}")
    actor = RpgActorRuntime(database.actors[actor_id], class_definitions=database.classes)
    snapshot = runtime_state.actor_snapshots.get(actor_id)
    if snapshot is not None:
        actor.restore(snapshot)
    allocation = runtime_state.progression_allocations.get(f"actor:{actor_id}")
    if allocation is None:
        allocation = runtime_state.progression_allocations.get(actor_id)
    return resolve_actor_build(
        actor,
        progression=runtime_state.progression,
        allocations=allocation,
        loadout=runtime_state.loadouts.get(actor_id),
        passives=database.passives,
        evolution_rules=database.ability_evolutions.values(),
    )
