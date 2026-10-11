from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from asteria.gameplay import ModifierSet, ResourcePool, StatBlock, TagSet

from .ability_build import AbilityGrant, AbilityResolution, ActorAbilityState


def _id(value, label):
    value = str(value).strip()
    if not value:
        raise ValueError(f"{label} is required")
    return value


def _numbers(values, label):
    result = {}
    for key, value in dict(values).items():
        key = _id(key, label)
        value = float(value)
        if not isfinite(value):
            raise ValueError(f"{label} values must be finite")
        result[key] = value
    return result


def _resources(values):
    result = {}
    for key, raw in dict(values).items():
        key = _id(key, "resource")
        if isinstance(raw, (int, float)):
            maximum = float(raw)
            minimum = 0.0
            current = maximum
        else:
            raw = dict(raw)
            if set(raw) - {"minimum", "maximum", "current"}:
                raise ValueError("invalid resource definition")
            minimum = float(raw.get("minimum", 0.0))
            maximum = float(raw["maximum"])
            current = float(raw.get("current", maximum))
        if not all(isfinite(x) for x in (minimum, maximum, current)):
            raise ValueError("resource values must be finite")
        if maximum < minimum:
            raise ValueError("resource maximum must be >= minimum")
        current = min(max(current, minimum), maximum)
        result[key] = {"minimum": minimum, "maximum": maximum, "current": current}
    return result


@dataclass(frozen=True, slots=True)
class ClassDefinition:
    class_id: str
    display_name: str
    stat_bonuses: dict[str, float] = field(default_factory=dict)
    resource_bonuses: dict[str, float] = field(default_factory=dict)
    granted_tags: tuple[str, ...] = ()
    granted_abilities: tuple[str, ...] = ()

    def __init__(
        self,
        class_id,
        display_name=None,
        *,
        stat_bonuses=None,
        resource_bonuses=None,
        granted_tags=(),
        granted_abilities=(),
    ):
        class_id = _id(class_id, "class_id")
        object.__setattr__(self, "class_id", class_id)
        object.__setattr__(self, "display_name", str(display_name or class_id))
        object.__setattr__(self, "stat_bonuses", _numbers(stat_bonuses or {}, "stat"))
        object.__setattr__(self, "resource_bonuses", _numbers(resource_bonuses or {}, "resource"))
        object.__setattr__(
            self,
            "granted_tags",
            tuple(sorted({_id(x, "tag").lower() for x in granted_tags})),
        )
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in granted_abilities)),
        )

    def to_data(self):
        return {
            "schema": "asteria.rpg.class",
            "version": 1,
            "class_id": self.class_id,
            "display_name": self.display_name,
            "stat_bonuses": dict(sorted(self.stat_bonuses.items())),
            "resource_bonuses": dict(sorted(self.resource_bonuses.items())),
            "granted_tags": list(self.granted_tags),
            "granted_abilities": list(self.granted_abilities),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.class" or data.get("version") != 1:
            raise ValueError("unsupported class definition")
        return cls(
            data["class_id"],
            data["display_name"],
            stat_bonuses=data["stat_bonuses"],
            resource_bonuses=data["resource_bonuses"],
            granted_tags=data["granted_tags"],
            granted_abilities=data["granted_abilities"],
        )


@dataclass(frozen=True, slots=True)
class ClassAssignment:
    """One project-defined class/job layer attached to an actor.

    Roles are opaque project data.  The engine never assumes that values such
    as ``primary`` or ``secondary`` have special semantics.  ``priority`` is
    used only to make contribution order deterministic (lower values first).
    """

    class_id: str
    assignment_id: str
    role: str
    enabled: bool
    priority: int
    progression_track_ids: tuple[str, ...]
    tags: tuple[str, ...]

    def __init__(
        self,
        class_id,
        *,
        assignment_id=None,
        role="class",
        enabled=True,
        priority=0,
        progression_track_ids=(),
        tags=(),
    ):
        class_id = _id(class_id, "class_id")
        assignment_id = _id(assignment_id or class_id, "assignment_id")
        role = _id(role, "class role")
        object.__setattr__(self, "class_id", class_id)
        object.__setattr__(self, "assignment_id", assignment_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "enabled", bool(enabled))
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(
            self,
            "progression_track_ids",
            tuple(dict.fromkeys(_id(x, "progression track id") for x in progression_track_ids)),
        )
        object.__setattr__(
            self,
            "tags",
            tuple(sorted({_id(x, "tag").lower() for x in tags})),
        )

    def to_data(self):
        return {
            "schema": "asteria.rpg.class_assignment",
            "version": 1,
            "class_id": self.class_id,
            "assignment_id": self.assignment_id,
            "role": self.role,
            "enabled": self.enabled,
            "priority": self.priority,
            "progression_track_ids": list(self.progression_track_ids),
            "tags": list(self.tags),
        }

    @classmethod
    def from_data(cls, data):
        expected = {
            "schema",
            "version",
            "class_id",
            "assignment_id",
            "role",
            "enabled",
            "priority",
            "progression_track_ids",
            "tags",
        }
        if set(data) != expected or data.get("schema") != "asteria.rpg.class_assignment" or data.get("version") != 1:
            raise ValueError("unsupported class assignment")
        return cls(
            data["class_id"],
            assignment_id=data["assignment_id"],
            role=data["role"],
            enabled=data["enabled"],
            priority=data["priority"],
            progression_track_ids=data["progression_track_ids"],
            tags=data["tags"],
        )


@dataclass(frozen=True, slots=True)
class ActorDefinition:
    actor_id: str
    display_name: str
    class_assignments: tuple[ClassAssignment, ...]
    base_stats: dict[str, float]
    base_resources: dict[str, dict[str, float]]
    tags: tuple[str, ...]
    abilities: tuple[str, ...]

    def __init__(
        self,
        actor_id,
        display_name=None,
        *,
        class_id=None,
        class_assignments=None,
        base_stats=None,
        base_resources=None,
        tags=(),
        abilities=(),
    ):
        actor_id = _id(actor_id, "actor_id")
        if class_assignments is not None and class_id is not None:
            raise ValueError("use class_id or class_assignments, not both")
        if class_assignments is None:
            assignments = () if class_id is None else (ClassAssignment(class_id, role="primary"),)
        else:
            assignments = tuple(
                x if isinstance(x, ClassAssignment) else ClassAssignment.from_data(x) for x in class_assignments
            )
        ids = [x.assignment_id for x in assignments]
        if len(ids) != len(set(ids)):
            raise ValueError("class assignment ids must be unique per actor")
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "display_name", str(display_name or actor_id))
        object.__setattr__(self, "class_assignments", assignments)
        object.__setattr__(self, "base_stats", _numbers(base_stats or {}, "stat"))
        object.__setattr__(self, "base_resources", _resources(base_resources or {}))
        object.__setattr__(self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags})))
        object.__setattr__(
            self,
            "abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in abilities)),
        )

    @property
    def class_id(self):
        """Backward-compatible single-class view.

        Returns the first enabled assignment in deterministic contribution
        order.  New code should use ``class_assignments``.
        """
        enabled = self.enabled_class_assignments()
        return None if not enabled else enabled[0].class_id

    def enabled_class_assignments(self):
        return tuple(
            sorted(
                (x for x in self.class_assignments if x.enabled),
                key=lambda x: (x.priority, x.assignment_id, x.class_id),
            )
        )

    def to_data(self):
        return {
            "schema": "asteria.rpg.actor",
            "version": 2,
            "actor_id": self.actor_id,
            "display_name": self.display_name,
            "class_assignments": [x.to_data() for x in self.class_assignments],
            "base_stats": dict(sorted(self.base_stats.items())),
            "base_resources": {k: self.base_resources[k] for k in sorted(self.base_resources)},
            "tags": list(self.tags),
            "abilities": list(self.abilities),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.actor" or data.get("version") not in {1, 2}:
            raise ValueError("unsupported actor definition")
        if data["version"] == 1:
            return cls(
                data["actor_id"],
                data["display_name"],
                class_id=data["class_id"],
                base_stats=data["base_stats"],
                base_resources=data["base_resources"],
                tags=data["tags"],
                abilities=data["abilities"],
            )
        return cls(
            data["actor_id"],
            data["display_name"],
            class_assignments=[ClassAssignment.from_data(x) for x in data["class_assignments"]],
            base_stats=data["base_stats"],
            base_resources=data["base_resources"],
            tags=data["tags"],
            abilities=data["abilities"],
        )


@dataclass(slots=True)
class RpgActorBuild:
    stats: StatBlock
    resources: ResourcePool
    tags: TagSet
    abilities: tuple[str, ...]
    class_assignments: tuple[ClassAssignment, ...] = ()


def _resolve_class_definitions(actor, class_definition=None, class_definitions=None):
    if class_definition is not None and class_definitions is not None:
        raise ValueError("use class_definition or class_definitions, not both")
    if class_definitions is None:
        if class_definition is None:
            definitions = {}
        else:
            definitions = {class_definition.class_id: class_definition}
    elif isinstance(class_definitions, dict):
        definitions = dict(class_definitions)
    else:
        definitions = {x.class_id: x for x in class_definitions}

    enabled = actor.enabled_class_assignments()
    missing = [x.class_id for x in enabled if x.class_id not in definitions]
    if missing:
        raise ValueError("actor class definition mismatch: " + ", ".join(sorted(set(missing))))
    return enabled, definitions


def build_actor(
    actor: ActorDefinition,
    class_definition: ClassDefinition | None = None,
    *,
    class_definitions=None,
):
    assignments, definitions = _resolve_class_definitions(
        actor, class_definition=class_definition, class_definitions=class_definitions
    )
    stats = StatBlock(actor.base_stats)
    resources = ResourcePool()
    for key, raw in actor.base_resources.items():
        resources.define(key, raw["maximum"], minimum=raw["minimum"], current=raw["current"])
    tags = TagSet(actor.tags)
    abilities = list(actor.abilities)
    for assignment in assignments:
        definition = definitions[assignment.class_id]
        for key, value in definition.stat_bonuses.items():
            stats.add(key, value)
        for key, value in definition.resource_bonuses.items():
            if not resources.contains(key):
                resources.define(key, max(0.0, value), current=max(0.0, value))
            else:
                r = resources.get(key)
                new_maximum = r.maximum + value
                new_current = r.current + value
                resources.define(
                    key,
                    new_maximum,
                    minimum=r.minimum,
                    current=new_current,
                    replace=True,
                )
        for tag in definition.granted_tags:
            tags.add(tag)
        for tag in assignment.tags:
            tags.add(tag)
        abilities.extend(definition.granted_abilities)
    return RpgActorBuild(stats, resources, tags, tuple(dict.fromkeys(abilities)), assignments)


@dataclass(frozen=True, slots=True)
class RpgActorSnapshot:
    actor_id: str
    stats: dict
    resources: dict
    tags: dict
    ability_state: dict | None = None

    def to_data(self):
        return {
            "schema": "asteria.rpg.actor_snapshot",
            "version": 2,
            "actor_id": self.actor_id,
            "stats": self.stats,
            "resources": self.resources,
            "tags": self.tags,
            "ability_state": self.ability_state,
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.actor_snapshot" or data.get("version") not in {1, 2}:
            raise ValueError("unsupported actor runtime snapshot")
        version = data["version"]
        expected = {"schema", "version", "actor_id", "stats", "resources", "tags"}
        if version == 2:
            expected = expected | {"ability_state"}
        if set(data) != expected:
            raise ValueError("unsupported actor runtime snapshot")
        return cls(
            _id(data["actor_id"], "actor_id"),
            data["stats"],
            data["resources"],
            data["tags"],
            data.get("ability_state"),
        )


class RpgActorRuntime:
    """Mutable actor state plus derived progression/equipment contributions.

    `stats/resources/tags` are the actor's mutable intrinsic runtime state.
    Equipment and progression are evaluated on demand and never baked into that
    intrinsic state, so unequipping or changing rank cannot leave stale values.
    """

    def __init__(self, actor, class_definition=None, *, class_definitions=None):
        self.definition = actor
        assignments, definitions = _resolve_class_definitions(
            actor, class_definition=class_definition, class_definitions=class_definitions
        )
        self.class_assignments = assignments
        self.class_definitions = definitions
        self.class_definition = definitions[assignments[0].class_id] if len(assignments) == 1 else None
        build = build_actor(actor, class_definitions=definitions)
        self.stats = build.stats
        self.resources = build.resources
        self.tags = build.tags
        self.abilities = build.abilities
        self.ability_state = ActorAbilityState()

    def snapshot(self):
        return RpgActorSnapshot(
            self.definition.actor_id,
            self.stats.to_data(),
            self.resources.to_data(),
            self.tags.to_data(),
            self.ability_state.to_data(),
        )

    def restore(self, snapshot):
        if isinstance(snapshot, dict):
            snapshot = RpgActorSnapshot.from_data(snapshot)
        if not isinstance(snapshot, RpgActorSnapshot):
            raise TypeError("snapshot must be RpgActorSnapshot")
        if snapshot.actor_id != self.definition.actor_id:
            raise ValueError("actor snapshot definition mismatch")
        self.stats = StatBlock.from_data(snapshot.stats)
        self.resources = ResourcePool.from_data(snapshot.resources)
        self.tags = TagSet.from_data(snapshot.tags)
        self.ability_state = (
            ActorAbilityState()
            if snapshot.ability_state is None
            else ActorAbilityState.from_data(snapshot.ability_state)
        )
        return self

    def _progression_contributions(self, progression):
        bonuses = {}
        tags = set()
        abilities = []
        if progression is None:
            return bonuses, tags, abilities
        assigned_tracks = {
            track_id for assignment in self.class_assignments for track_id in assignment.progression_track_ids
        }
        # Phase 7A actors did not record progression ownership. Preserve that
        # behavior when no assignment declares tracks; new multi-job actors can
        # bind each job to independent progression tracks explicitly.
        track_ids = assigned_tracks or set(progression.definitions)
        for track_id in sorted(track_ids):
            if track_id not in progression.definitions:
                continue
            definition = progression.definitions[track_id]
            total = progression.total(track_id)
            for milestone in definition.milestones:
                if milestone.required_total > total:
                    break
                for stat, value in milestone.stat_bonuses.items():
                    bonuses[stat] = bonuses.get(stat, 0.0) + value
                tags.update(milestone.granted_tags)
                abilities.extend(milestone.granted_abilities)
        return bonuses, tags, abilities

    def effective_stats(self, *, progression=None, allocations=None, loadout=None, passives=None):
        values = StatBlock.from_data(self.stats.to_data())
        bonuses, _, _ = self._progression_contributions(progression)
        for stat, value in bonuses.items():
            values.add(stat, value)
        if allocations is not None:
            for stat, value in allocations.contribution().stat_bonuses.items():
                values.add(stat, value)
        tags = self.effective_tags(progression=progression, allocations=allocations, loadout=loadout, passives=passives)
        if loadout is not None:
            values = loadout.modifier_set().evaluate_block(values, tags=tags)
        if passives is not None:
            values = self.effective_passive_modifiers(passives).evaluate_block(values, tags=tags)
        return values

    def effective_tags(self, *, progression=None, allocations=None, loadout=None, passives=None):
        result = TagSet(self.tags.values())
        _, progression_tags, _ = self._progression_contributions(progression)
        for tag in progression_tags:
            result.add(tag)
        if allocations is not None:
            contribution = allocations.contribution()
            for tag in contribution.granted_tags:
                result.add(tag)
            for capability in contribution.granted_capabilities:
                result.add(capability)
        if loadout is not None:
            for tag in loadout.tags():
                result.add(tag)
        if passives is not None:
            for tag in self.effective_passive_tags(passives):
                result.add(tag)
        return result

    def effective_capabilities(self, *, progression=None, allocations=None, loadout=None, passives=None):
        """Return the generic capability vocabulary used by equipment rules.

        Capabilities intentionally share the canonical tag namespace.  This lets
        actor/class/progression/passive/equipment/state-like contributions grant
        permissions without introducing weapon-specific engine enums.
        """
        return self.effective_tags(
            progression=progression,
            allocations=allocations,
            loadout=loadout,
            passives=passives,
        ).values()

    def equipment_eligibility(self, loadout, slot_id, item, *, progression=None, allocations=None, passives=None):
        return loadout.check_equip(
            slot_id,
            item,
            capabilities=self.effective_capabilities(
                progression=progression,
                allocations=allocations,
                loadout=loadout,
                passives=passives,
            ),
        )

    def equip_item(self, loadout, slot_id, item, *, progression=None, allocations=None, passives=None):
        return loadout.equip(
            slot_id,
            item,
            capabilities=self.effective_capabilities(
                progression=progression,
                allocations=allocations,
                loadout=loadout,
                passives=passives,
            ),
        )

    def resolve_abilities(
        self,
        *,
        progression=None,
        allocations=None,
        loadout=None,
        passives=None,
        evolution_rules=(),
    ):
        grants = []

        def add(ability_id, source_kind, source_id):
            grants.append(AbilityGrant(str(ability_id), str(source_kind), str(source_id)))

        for ability_id in self.definition.abilities:
            add(ability_id, "intrinsic", self.definition.actor_id)
        for assignment in self.class_assignments:
            definition = self.class_definitions[assignment.class_id]
            for ability_id in definition.granted_abilities:
                add(ability_id, "class", assignment.assignment_id)
        _, _, progression_abilities = self._progression_contributions(progression)
        for ability_id in progression_abilities:
            add(ability_id, "progression", "progression")
        if allocations is not None:
            for ability_id, source_id in allocations.contribution().ability_grants:
                add(ability_id, "allocation", source_id)
        for ability_id in self.ability_state.learned_abilities:
            add(ability_id, "learned", self.definition.actor_id)
        if loadout is not None:
            for item in loadout.equipped():
                for ability_id in item.equipment.granted_abilities:
                    add(ability_id, "equipment", item.instance_id)
                growth = item.growth_contribution()
                if growth is not None:
                    for ability_id in growth.granted_abilities:
                        add(ability_id, "equipment_growth", item.instance_id)
                for socket_id in sorted(item.attachments):
                    attachment = item.attachments[socket_id]
                    for ability_id in attachment.granted_abilities:
                        add(ability_id, "attachment", f"{item.instance_id}:{socket_id}")
        passive_map = dict(passives or {})
        for passive_id in self.ability_state.active_passives:
            passive = passive_map.get(passive_id)
            if passive is None:
                continue
            for ability_id in passive.granted_abilities:
                add(ability_id, "passive", passive_id)

        ordered = []
        for grant in grants:
            if grant.ability_id not in ordered:
                ordered.append(grant.ability_id)

        rules = tuple(evolution_rules)
        by_source = {}
        for rule in rules:
            if not rule.matches(progression):
                continue
            by_source.setdefault(rule.source_ability_id, []).append(rule)
        for source in list(ordered):
            candidates = by_source.get(source, [])
            selected_id = self.ability_state.selected_evolutions.get(source)
            if selected_id is not None:
                candidates = [x for x in candidates if x.rule_id == selected_id]
            if not candidates:
                continue
            chosen = sorted(candidates, key=lambda x: (-x.priority, x.rule_id))[0]
            if not chosen.retain_source:
                ordered = [x for x in ordered if x != source]
            if chosen.result_ability_id not in ordered:
                ordered.append(chosen.result_ability_id)
            add(chosen.result_ability_id, "evolution", chosen.rule_id)
        return AbilityResolution(tuple(ordered), tuple(grants))

    def effective_abilities(
        self, *, progression=None, allocations=None, loadout=None, passives=None, evolution_rules=()
    ):
        return self.resolve_abilities(
            progression=progression,
            allocations=allocations,
            loadout=loadout,
            passives=passives,
            evolution_rules=evolution_rules,
        ).abilities

    def effective_passive_modifiers(self, passives):
        result = ModifierSet()
        for passive_id in self.ability_state.active_passives:
            passive = dict(passives or {}).get(passive_id)
            if passive is not None:
                for modifier in passive.modifiers:
                    result.add(modifier)
        return result

    def effective_passive_tags(self, passives):
        result = set()
        for passive_id in self.ability_state.active_passives:
            passive = dict(passives or {}).get(passive_id)
            if passive is not None:
                result.update(passive.tags)
        return tuple(sorted(result))


class RpgDatabase:
    def __init__(self):
        self.actors = {}
        self.classes = {}
        self.items = {}
        self.equipment = {}
        self.attachments = {}
        self.enemies = {}
        self.encounters = {}
        self.progression_tracks = {}
        self.passives = {}
        self.ability_evolutions = {}
        self.progression_graphs = {}
        self.equipment_growth = {}
        self.battle_resources = {}
        self.interaction_rules = {}
        self.outcome_checks = {}
        self.battle_state_policies = {}
        self.formations = {}
        self.battle_targeting = {}
        self.battle_objectives = {}
        self.escape_rules = {}
        self.battle_schedulers = {}
        self.action_timings = {}
        self.action_sequences = {}
        self.gauge_compositions = {}
        self.reactions = {}
        self.enemy_ai = {}
        self.action_transactions = {}
        self.composition_recipes = {}
        self.party_setups = {}
        self.party_presentation_policies = {}
        self.enemy_behavior_bindings = {}
        self.battle_session_rules = {}
        self.shops = {}
        self.equipment_sets = {}
        self.factions = {}
        self.achievements = {}
        self.capture_rules = {}
        self.world_interactions = {}
        self.drop_tables = {}
        self.behavior_trees = {}
        self.quests = {}

    def add_actor(self, value):
        if not isinstance(value, ActorDefinition):
            raise TypeError("actor must be ActorDefinition")
        if value.actor_id in self.actors:
            raise ValueError(f"duplicate actor: {value.actor_id}")
        self.actors[value.actor_id] = value
        return value

    def add_class(self, value):
        if not isinstance(value, ClassDefinition):
            raise TypeError("class must be ClassDefinition")
        if value.class_id in self.classes:
            raise ValueError(f"duplicate class: {value.class_id}")
        self.classes[value.class_id] = value
        return value

    def add_item(self, value):
        from .items import ItemDefinition

        if not isinstance(value, ItemDefinition):
            raise TypeError("item must be ItemDefinition")
        if value.item_id in self.items:
            raise ValueError(f"duplicate item: {value.item_id}")
        self.items[value.item_id] = value
        return value

    def add_equipment(self, value):
        from .items import EquipmentDefinition

        if not isinstance(value, EquipmentDefinition):
            raise TypeError("equipment must be EquipmentDefinition")
        if value.equipment_id in self.equipment:
            raise ValueError(f"duplicate equipment: {value.equipment_id}")
        self.equipment[value.equipment_id] = value
        return value

    def add_attachment(self, value):
        from .items import AttachmentDefinition

        if not isinstance(value, AttachmentDefinition):
            raise TypeError("attachment must be AttachmentDefinition")
        if value.attachment_id in self.attachments:
            raise ValueError(f"duplicate attachment: {value.attachment_id}")
        self.attachments[value.attachment_id] = value
        return value

    def add_enemy(self, value):
        from .enemies import EnemyDefinition

        if not isinstance(value, EnemyDefinition):
            raise TypeError("enemy must be EnemyDefinition")
        if value.enemy_id in self.enemies:
            raise ValueError(f"duplicate enemy: {value.enemy_id}")
        self.enemies[value.enemy_id] = value
        return value

    def add_encounter(self, value):
        from .enemies import EncounterDefinition

        if not isinstance(value, EncounterDefinition):
            raise TypeError("encounter must be EncounterDefinition")
        if value.encounter_id in self.encounters:
            raise ValueError(f"duplicate encounter: {value.encounter_id}")
        self.encounters[value.encounter_id] = value
        return value

    def add_progression_track(self, value):
        from .progression import ProgressionTrackDefinition

        if not isinstance(value, ProgressionTrackDefinition):
            raise TypeError("progression track must be ProgressionTrackDefinition")
        if value.track_id in self.progression_tracks:
            raise ValueError(f"duplicate progression track: {value.track_id}")
        self.progression_tracks[value.track_id] = value
        return value

    def add_passive(self, value):
        from .ability_build import PassiveDefinition

        if not isinstance(value, PassiveDefinition):
            raise TypeError("passive must be PassiveDefinition")
        if value.passive_id in self.passives:
            raise ValueError(f"duplicate passive: {value.passive_id}")
        self.passives[value.passive_id] = value
        return value

    def add_ability_evolution(self, value):
        from .ability_build import AbilityEvolutionRule

        if not isinstance(value, AbilityEvolutionRule):
            raise TypeError("ability evolution must be AbilityEvolutionRule")
        if value.rule_id in self.ability_evolutions:
            raise ValueError(f"duplicate ability evolution: {value.rule_id}")
        self.ability_evolutions[value.rule_id] = value
        return value

    def add_progression_graph(self, value):
        from .progression_graph import ProgressionGraphDefinition

        if not isinstance(value, ProgressionGraphDefinition):
            raise TypeError("progression graph must be ProgressionGraphDefinition")
        if value.graph_id in self.progression_graphs:
            raise ValueError(f"duplicate progression graph: {value.graph_id}")
        self.progression_graphs[value.graph_id] = value
        return value

    def add_equipment_growth(self, value):
        from .equipment_growth import EquipmentGrowthDefinition

        if not isinstance(value, EquipmentGrowthDefinition):
            raise TypeError("equipment growth must be EquipmentGrowthDefinition")
        if value.growth_id in self.equipment_growth:
            raise ValueError(f"duplicate equipment growth: {value.growth_id}")
        self.equipment_growth[value.growth_id] = value
        return value

    def add_battle_resource(self, value):
        from .battle_resources import BattleResourceDefinition

        if not isinstance(value, BattleResourceDefinition):
            raise TypeError("battle resource must be BattleResourceDefinition")
        if value.resource_id in self.battle_resources:
            raise ValueError(f"duplicate battle resource: {value.resource_id}")
        self.battle_resources[value.resource_id] = value
        return value

    def add_interaction_rule(self, value):
        from .interactions import InteractionRule

        if not isinstance(value, InteractionRule):
            raise TypeError("interaction rule must be InteractionRule")
        if value.rule_id in self.interaction_rules:
            raise ValueError(f"duplicate interaction rule: {value.rule_id}")
        self.interaction_rules[value.rule_id] = value
        return value

    def add_outcome_check(self, value):
        from .interactions import OutcomeCheckDefinition

        if not isinstance(value, OutcomeCheckDefinition):
            raise TypeError("outcome check must be OutcomeCheckDefinition")
        if value.check_id in self.outcome_checks:
            raise ValueError(f"duplicate outcome check: {value.check_id}")
        self.outcome_checks[value.check_id] = value
        return value

    def add_battle_state_policy(self, value):
        from .battle_states import BattleStatePolicy

        if not isinstance(value, BattleStatePolicy):
            raise TypeError("battle state policy must be BattleStatePolicy")
        if value.state_id in self.battle_state_policies:
            raise ValueError(f"duplicate battle state policy: {value.state_id}")
        self.battle_state_policies[value.state_id] = value
        return value

    def add_formation(self, value):
        from .targeting import FormationDefinition

        if not isinstance(value, FormationDefinition):
            raise TypeError("formation must be FormationDefinition")
        if value.formation_id in self.formations:
            raise ValueError(f"duplicate formation: {value.formation_id}")
        self.formations[value.formation_id] = value
        return value

    def add_battle_targeting(self, value):
        from .targeting import BattleTargetingDefinition

        if not isinstance(value, BattleTargetingDefinition):
            raise TypeError("battle targeting must be BattleTargetingDefinition")
        if value.ability_id in self.battle_targeting:
            raise ValueError(f"duplicate battle targeting for ability: {value.ability_id}")
        self.battle_targeting[value.ability_id] = value
        return value

    def add_battle_objective(self, value):
        from .battle_lifecycle import BattleObjectiveDefinition

        if not isinstance(value, BattleObjectiveDefinition):
            raise TypeError("battle objective must be BattleObjectiveDefinition")
        if value.objective_id in self.battle_objectives:
            raise ValueError(f"duplicate battle objective: {value.objective_id}")
        self.battle_objectives[value.objective_id] = value
        return value

    def add_escape_rule(self, value):
        from .battle_lifecycle import BattleEscapeRule

        if not isinstance(value, BattleEscapeRule):
            raise TypeError("escape rule must be BattleEscapeRule")
        if value.rule_id in self.escape_rules:
            raise ValueError(f"duplicate escape rule: {value.rule_id}")
        self.escape_rules[value.rule_id] = value
        return value

    def add_battle_scheduler(self, value):
        from .battle_scheduler import BattleSchedulerDefinition

        if not isinstance(value, BattleSchedulerDefinition):
            raise TypeError("battle scheduler must be BattleSchedulerDefinition")
        if value.scheduler_id in self.battle_schedulers:
            raise ValueError(f"duplicate battle scheduler: {value.scheduler_id}")
        self.battle_schedulers[value.scheduler_id] = value
        return value

    def add_action_timing(self, value):
        from .battle_timing import ActionTimingDefinition

        if not isinstance(value, ActionTimingDefinition):
            raise TypeError("action timing must be ActionTimingDefinition")
        if value.ability_id in self.action_timings:
            raise ValueError(f"duplicate action timing for ability: {value.ability_id}")
        self.action_timings[value.ability_id] = value
        return value

    def add_action_sequence(self, value):
        from .action_sequences import ActionSequenceDefinition

        if not isinstance(value, ActionSequenceDefinition):
            raise TypeError("action sequence must be ActionSequenceDefinition")
        if value.sequence_id in self.action_sequences:
            raise ValueError(f"duplicate action sequence: {value.sequence_id}")
        self.action_sequences[value.sequence_id] = value
        return value

    def add_gauge_composition(self, value):
        from .gauge_composition import GaugeCompositionDefinition

        if not isinstance(value, GaugeCompositionDefinition):
            raise TypeError("gauge composition must be GaugeCompositionDefinition")
        if value.composition_id in self.gauge_compositions:
            raise ValueError(f"duplicate gauge composition: {value.composition_id}")
        self.gauge_compositions[value.composition_id] = value
        return value

    def add_reaction(self, value):
        from .reactions import ReactionDefinition

        if not isinstance(value, ReactionDefinition):
            raise TypeError("reaction must be ReactionDefinition")
        if value.reaction_id in self.reactions:
            raise ValueError(f"duplicate reaction: {value.reaction_id}")
        self.reactions[value.reaction_id] = value
        return value

    def add_enemy_ai(self, value):
        from .enemy_ai import EnemyAIDefinition

        if not isinstance(value, EnemyAIDefinition):
            raise TypeError("enemy AI must be EnemyAIDefinition")
        if value.ai_id in self.enemy_ai:
            raise ValueError(f"duplicate enemy AI: {value.ai_id}")
        self.enemy_ai[value.ai_id] = value
        return value

    def add_enemy_behavior_binding(self, value):
        from .enemy_behavior import EnemyBehaviorBinding

        if not isinstance(value, EnemyBehaviorBinding):
            raise TypeError("enemy behavior binding must be EnemyBehaviorBinding")
        if value.enemy_id in self.enemy_behavior_bindings:
            raise ValueError(f"duplicate enemy behavior binding: {value.enemy_id}")
        self.enemy_behavior_bindings[value.enemy_id] = value
        return value

    def add_battle_session_rules(self, value):
        from .battle_session_rules import BattleSessionRules

        if not isinstance(value, BattleSessionRules):
            raise TypeError("battle session rules must be BattleSessionRules")
        if value.rules_id in self.battle_session_rules:
            raise ValueError(f"duplicate battle session rules: {value.rules_id}")
        self.battle_session_rules[value.rules_id] = value
        return value

    def add_shop(self, value):
        from .economy import ShopDefinition

        if not isinstance(value, ShopDefinition):
            raise TypeError("shop must be ShopDefinition")
        if value.shop_id in self.shops:
            raise ValueError(f"duplicate shop: {value.shop_id}")
        self.shops[value.shop_id] = value
        return value

    def add_equipment_set(self, value):
        from .equipment_sets import EquipmentSetDefinition

        if not isinstance(value, EquipmentSetDefinition):
            raise TypeError("equipment set must be EquipmentSetDefinition")
        if value.set_id in self.equipment_sets:
            raise ValueError(f"duplicate equipment set: {value.set_id}")
        self.equipment_sets[value.set_id] = value
        return value

    def _add_keyed(self, store, value, cls, key, label):
        if not isinstance(value, cls):
            raise TypeError(f"{label} must be {cls.__name__}")
        if getattr(value, key) in store:
            raise ValueError(f"duplicate {label}: {getattr(value, key)}")
        store[getattr(value, key)] = value
        return value

    def add_faction(self, value):
        from .world_record import FactionDefinition

        return self._add_keyed(self.factions, value, FactionDefinition, "faction_id", "faction")

    def add_achievement(self, value):
        from .world_record import AchievementDefinition

        return self._add_keyed(self.achievements, value, AchievementDefinition, "achievement_id", "achievement")

    def add_behavior_tree(self, value):
        from .behavior_tree import BehaviorTree

        return self._add_keyed(self.behavior_trees, value, BehaviorTree, "tree_id", "behavior tree")

    def add_drop_table(self, value):
        from .drop_tables import DropTable

        return self._add_keyed(self.drop_tables, value, DropTable, "table_id", "drop table")

    def add_world_interaction(self, value):
        from .world_interactions import WorldInteraction

        return self._add_keyed(self.world_interactions, value, WorldInteraction, "interaction_id", "world interaction")

    def add_capture_rule(self, value):
        from .capture import CaptureRule

        return self._add_keyed(self.capture_rules, value, CaptureRule, "enemy_id", "capture rule")

    def add_quest(self, value):
        from .quests import QuestDefinition

        if not isinstance(value, QuestDefinition):
            raise TypeError("quest must be QuestDefinition")
        if value.quest_id in self.quests:
            raise ValueError(f"duplicate quest: {value.quest_id}")
        self.quests[value.quest_id] = value
        return value

    def add_party_presentation_policy(self, value):
        from .party_setup import PartyPresentationPolicyDefinition

        if not isinstance(value, PartyPresentationPolicyDefinition):
            raise TypeError("party presentation policy must be PartyPresentationPolicyDefinition")
        if value.profile_id in self.party_presentation_policies:
            raise ValueError(f"duplicate party presentation policy: {value.profile_id}")
        self.party_presentation_policies[value.profile_id] = value
        return value

    def add_party_setup(self, value):
        from .party_setup import PartySetupDefinition

        if not isinstance(value, PartySetupDefinition):
            raise TypeError("party setup must be PartySetupDefinition")
        if value.party_id in self.party_setups:
            raise ValueError(f"duplicate party setup: {value.party_id}")
        self.party_setups[value.party_id] = value
        return value

    def add_composition_recipe(self, value):
        from .composition import CompositionRecipeDefinition

        if not isinstance(value, CompositionRecipeDefinition):
            raise TypeError("composition recipe must be CompositionRecipeDefinition")
        if value.recipe_id in self.composition_recipes:
            raise ValueError(f"duplicate composition recipe: {value.recipe_id}")
        self.composition_recipes[value.recipe_id] = value
        return value

    def add_action_transaction(self, value):
        from .battle_transactions import ActionTransactionPolicy

        if not isinstance(value, ActionTransactionPolicy):
            raise TypeError("action transaction must be ActionTransactionPolicy")
        if value.ability_id in self.action_transactions:
            raise ValueError(f"duplicate action transaction for ability: {value.ability_id}")
        self.action_transactions[value.ability_id] = value
        return value

    def reference_errors(self):
        """Every dangling cross-record reference, one message each (Problems panel, EDT-15)."""
        errors = []
        for actor in self.actors.values():
            for assignment in actor.class_assignments:
                if assignment.class_id not in self.classes:
                    errors.append(
                        f"actor {actor.actor_id} class assignment {assignment.assignment_id} "
                        f"references unknown class {assignment.class_id}"
                    )
                for track_id in assignment.progression_track_ids:
                    if track_id not in self.progression_tracks:
                        errors.append(
                            f"actor {actor.actor_id} class assignment {assignment.assignment_id} "
                            f"references unknown progression track {track_id}"
                        )
        for rule in self.ability_evolutions.values():
            if rule.progression_track_id is not None and rule.progression_track_id not in self.progression_tracks:
                errors.append(
                    f"ability evolution {rule.rule_id} references unknown progression track {rule.progression_track_id}"
                )
        for graph in self.progression_graphs.values():
            for node in graph.nodes:
                for reward in node.rewards:
                    for passive_id in reward.unlocked_passives:
                        if passive_id not in self.passives:
                            errors.append(
                                f"progression graph {graph.graph_id} node {node.node_id} "
                                f"references unknown passive {passive_id}"
                            )
        for equipment in self.equipment.values():
            if equipment.growth_id is not None and equipment.growth_id not in self.equipment_growth:
                errors.append(
                    f"equipment {equipment.equipment_id} references unknown equipment growth {equipment.growth_id}"
                )
        for attachment in self.attachments.values():
            if attachment.growth_id is not None and attachment.growth_id not in self.equipment_growth:
                errors.append(
                    f"attachment {attachment.attachment_id} references unknown equipment growth {attachment.growth_id}"
                )
        for growth in self.equipment_growth.values():
            for node in growth.nodes:
                for reward in node.rewards:
                    if (
                        reward.evolution_equipment_id is not None
                        and reward.evolution_equipment_id not in self.equipment
                    ):
                        errors.append(
                            f"equipment growth {growth.growth_id} node {node.node_id} "
                            f"references unknown evolution equipment {reward.evolution_equipment_id}"
                        )
                    for socket_id in reward.unlocked_sockets:
                        owners = [
                            e
                            for e in self.equipment.values()
                            if e.growth_id == growth.growth_id and any(s.socket_id == socket_id for s in e.sockets)
                        ]
                        if not owners:
                            errors.append(
                                f"equipment growth {growth.growth_id} node {node.node_id} "
                                f"unlocks unknown socket {socket_id}"
                            )
        for binding in self.enemy_behavior_bindings.values():
            if binding.enemy_id not in self.enemies:
                errors.append(f"enemy behavior binding references unknown enemy {binding.enemy_id}")
            if binding.ai_id not in self.enemy_ai:
                errors.append(f"enemy behavior binding for {binding.enemy_id} references unknown AI {binding.ai_id}")
        for party in self.party_setups.values():
            for actor_id in party.roster_actor_ids:
                if actor_id not in self.actors:
                    errors.append(f"party setup {party.party_id} references unknown actor {actor_id}")
            if party.formation_id is not None:
                formation = self.formations.get(party.formation_id)
                if formation is None:
                    errors.append(f"party setup {party.party_id} references unknown formation {party.formation_id}")
                else:
                    known_slots = {x.slot_id for x in formation.slots}
                    for placement in party.placements:
                        if placement.slot_id not in known_slots:
                            errors.append(
                                f"party setup {party.party_id} references unknown formation slot {placement.slot_id}"
                            )
        for recipe in self.composition_recipes.values():
            for selection in recipe.selections:
                for item_id in selection.item_ids:
                    if item_id not in self.items:
                        errors.append(f"composition recipe {recipe.recipe_id} references unknown input item {item_id}")
            for item_id in recipe.all_output_item_ids():
                if item_id not in self.items:
                    errors.append(f"composition recipe {recipe.recipe_id} references unknown output item {item_id}")
            for track_id in recipe.experience:
                if track_id not in self.progression_tracks:
                    errors.append(
                        f"composition recipe {recipe.recipe_id} references unknown progression track {track_id}"
                    )
        for equipment_set in self.equipment_sets.values():
            for equipment_id in equipment_set.equipment_ids:
                if equipment_id not in self.equipment:
                    errors.append(f"equipment set {equipment_set.set_id} references unknown equipment {equipment_id}")
        for tree in self.behavior_trees.values():
            for encounter_id in sorted(tree.encounter_ids()):
                if encounter_id not in self.encounters:
                    errors.append(f"behavior tree {tree.tree_id} references unknown encounter {encounter_id}")
        for table in self.drop_tables.values():
            for item_id in sorted(table.item_ids()):
                if item_id not in self.items:
                    errors.append(f"drop table {table.table_id} references unknown item {item_id}")
        for enemy in self.enemies.values():
            if enemy.reward.drop_table_id and enemy.reward.drop_table_id not in self.drop_tables:
                errors.append(
                    f"enemy {enemy.enemy_id} reward references unknown drop table {enemy.reward.drop_table_id}"
                )
        for interaction in self.world_interactions.values():
            where = f"world interaction {interaction.interaction_id}"
            for item_id in {*interaction.cost_items, *interaction.success_items} | (
                {interaction.required_item} if interaction.required_item else set()
            ):
                if item_id not in self.items:
                    errors.append(f"{where} references unknown item {item_id}")
            for faction_id in interaction.reputation:
                if faction_id not in self.factions:
                    errors.append(f"{where} references unknown faction {faction_id}")
        for rule in self.capture_rules.values():
            if rule.enemy_id not in self.enemies:
                errors.append(f"capture rule references unknown enemy {rule.enemy_id}")
            if rule.actor_id not in self.actors:
                errors.append(f"capture rule {rule.enemy_id} references unknown actor {rule.actor_id}")
            if rule.item_id and rule.item_id not in self.items:
                errors.append(f"capture rule {rule.enemy_id} references unknown item {rule.item_id}")
        for achievement in self.achievements.values():
            store = {"defeated": self.enemies, "reputation": self.factions, "quest": self.quests}.get(achievement.kind)
            if store is not None and achievement.target not in store:
                errors.append(
                    f"achievement {achievement.achievement_id} references unknown "
                    f"{achievement.kind} target {achievement.target}"
                )
        for shop in self.shops.values():
            for entry in shop.entries:
                if entry.item_id not in self.items:
                    errors.append(f"shop {shop.shop_id} references unknown item {entry.item_id}")
        for quest in self.quests.values():
            for quest_id in quest.prerequisites + quest.next_quest_ids:
                if quest_id not in self.quests:
                    errors.append(f"quest {quest.quest_id} references unknown quest {quest_id}")
            for objective in quest.objectives:
                if objective.kind == "item" and objective.target not in self.items:
                    errors.append(f"quest {quest.quest_id} references unknown item {objective.target}")
                if objective.kind == "defeat_enemy" and objective.target not in self.enemies:
                    errors.append(f"quest {quest.quest_id} references unknown enemy {objective.target}")
            for entry in quest.reward.loot:
                if entry.item_id not in self.items:
                    errors.append(f"quest {quest.quest_id} reward references unknown item {entry.item_id}")
            for track_id in quest.reward.experience:
                if track_id not in self.progression_tracks:
                    errors.append(f"quest {quest.quest_id} reward references unknown progression track {track_id}")
        for encounter in self.encounters.values():
            for member in encounter.members:
                if member.enemy_id not in self.enemies:
                    errors.append(f"encounter {encounter.encounter_id} references unknown enemy {member.enemy_id}")
        for enemy in self.enemies.values():
            for entry in enemy.reward.loot:
                if entry.item_id not in self.items:
                    errors.append(f"enemy {enemy.enemy_id} reward references unknown item {entry.item_id}")
            for track_id in enemy.reward.experience:
                if track_id not in self.progression_tracks:
                    errors.append(f"enemy {enemy.enemy_id} reward references unknown progression track {track_id}")
        return sorted(errors)

    def validate(self):
        errors = self.reference_errors()
        if errors:
            raise ValueError("invalid RPG database references: " + "; ".join(errors))
        return True

    def build_actor(self, actor_id):
        actor = self.actors[str(actor_id)]
        definitions = {
            assignment.class_id: self.classes[assignment.class_id] for assignment in actor.enabled_class_assignments()
        }
        return RpgActorRuntime(actor, class_definitions=definitions)

    def to_data(self):
        return {
            "schema": "asteria.rpg.database",
            "version": 28,
            "actors": [self.actors[k].to_data() for k in sorted(self.actors)],
            "classes": [self.classes[k].to_data() for k in sorted(self.classes)],
            "items": [self.items[k].to_data() for k in sorted(self.items)],
            "equipment": [self.equipment[k].to_data() for k in sorted(self.equipment)],
            "attachments": [self.attachments[k].to_data() for k in sorted(self.attachments)],
            "enemies": [self.enemies[k].to_data() for k in sorted(self.enemies)],
            "encounters": [self.encounters[k].to_data() for k in sorted(self.encounters)],
            "progression_tracks": [self.progression_tracks[k].to_data() for k in sorted(self.progression_tracks)],
            "passives": [self.passives[k].to_data() for k in sorted(self.passives)],
            "ability_evolutions": [self.ability_evolutions[k].to_data() for k in sorted(self.ability_evolutions)],
            "progression_graphs": [self.progression_graphs[k].to_data() for k in sorted(self.progression_graphs)],
            "equipment_growth": [self.equipment_growth[k].to_data() for k in sorted(self.equipment_growth)],
            "battle_resources": [self.battle_resources[k].to_data() for k in sorted(self.battle_resources)],
            "interaction_rules": [self.interaction_rules[k].to_data() for k in sorted(self.interaction_rules)],
            "outcome_checks": [self.outcome_checks[k].to_data() for k in sorted(self.outcome_checks)],
            "battle_state_policies": [
                self.battle_state_policies[k].to_data() for k in sorted(self.battle_state_policies)
            ],
            "formations": [self.formations[k].to_data() for k in sorted(self.formations)],
            "battle_targeting": [self.battle_targeting[k].to_data() for k in sorted(self.battle_targeting)],
            "battle_objectives": [self.battle_objectives[k].to_data() for k in sorted(self.battle_objectives)],
            "escape_rules": [self.escape_rules[k].to_data() for k in sorted(self.escape_rules)],
            "battle_schedulers": [self.battle_schedulers[k].to_data() for k in sorted(self.battle_schedulers)],
            "action_timings": [self.action_timings[k].to_data() for k in sorted(self.action_timings)],
            "action_sequences": [self.action_sequences[k].to_data() for k in sorted(self.action_sequences)],
            "gauge_compositions": [self.gauge_compositions[k].to_data() for k in sorted(self.gauge_compositions)],
            "reactions": [self.reactions[k].to_data() for k in sorted(self.reactions)],
            "enemy_ai": [self.enemy_ai[k].to_data() for k in sorted(self.enemy_ai)],
            "action_transactions": [self.action_transactions[k].to_data() for k in sorted(self.action_transactions)],
            "composition_recipes": [self.composition_recipes[k].to_data() for k in sorted(self.composition_recipes)],
            "party_setups": [self.party_setups[k].to_data() for k in sorted(self.party_setups)],
            "party_presentation_policies": [
                self.party_presentation_policies[k].to_data() for k in sorted(self.party_presentation_policies)
            ],
            "enemy_behavior_bindings": [
                self.enemy_behavior_bindings[k].to_data() for k in sorted(self.enemy_behavior_bindings)
            ],
            "battle_session_rules": [self.battle_session_rules[k].to_data() for k in sorted(self.battle_session_rules)],
            "shops": [self.shops[k].to_data() for k in sorted(self.shops)],
            "equipment_sets": [self.equipment_sets[k].to_data() for k in sorted(self.equipment_sets)],
            "factions": [self.factions[k].to_data() for k in sorted(self.factions)],
            "achievements": [self.achievements[k].to_data() for k in sorted(self.achievements)],
            "capture_rules": [self.capture_rules[k].to_data() for k in sorted(self.capture_rules)],
            "quests": [self.quests[k].to_data() for k in sorted(self.quests)],
            "world_interactions": [self.world_interactions[k].to_data() for k in sorted(self.world_interactions)],
            "drop_tables": [self.drop_tables[k].to_data() for k in sorted(self.drop_tables)],
            "behavior_trees": [self.behavior_trees[k].to_data() for k in sorted(self.behavior_trees)],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.database" or data.get("version") not in {
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            22,
            23,
            24,
            25,
            26,
            27,
            28,
        }:
            raise ValueError("unsupported RPG database")
        result = cls()
        for x in data["classes"]:
            result.add_class(ClassDefinition.from_data(x))
        for x in data["actors"]:
            result.add_actor(ActorDefinition.from_data(x))
        if data["version"] >= 2:
            from .items import AttachmentDefinition, EquipmentDefinition, ItemDefinition

            for x in data["items"]:
                result.add_item(ItemDefinition.from_data(x))
            for x in data["equipment"]:
                result.add_equipment(EquipmentDefinition.from_data(x))
            for x in data["attachments"]:
                result.add_attachment(AttachmentDefinition.from_data(x))
        if data["version"] >= 3:
            from .enemies import EncounterDefinition, EnemyDefinition

            for x in data["enemies"]:
                result.add_enemy(EnemyDefinition.from_data(x))
            for x in data["encounters"]:
                result.add_encounter(EncounterDefinition.from_data(x))
        if data["version"] >= 4:
            from .progression import ProgressionTrackDefinition

            for x in data["progression_tracks"]:
                result.add_progression_track(ProgressionTrackDefinition.from_data(x))
        if data["version"] >= 6:
            from .ability_build import AbilityEvolutionRule, PassiveDefinition

            for x in data["passives"]:
                result.add_passive(PassiveDefinition.from_data(x))
            for x in data["ability_evolutions"]:
                result.add_ability_evolution(AbilityEvolutionRule.from_data(x))
        if data["version"] >= 7:
            from .progression_graph import ProgressionGraphDefinition

            for x in data["progression_graphs"]:
                result.add_progression_graph(ProgressionGraphDefinition.from_data(x))
        if data["version"] >= 8:
            from .equipment_growth import EquipmentGrowthDefinition

            for x in data["equipment_growth"]:
                result.add_equipment_growth(EquipmentGrowthDefinition.from_data(x))
        if data["version"] >= 9:
            from .battle_resources import BattleResourceDefinition

            for x in data["battle_resources"]:
                result.add_battle_resource(BattleResourceDefinition.from_data(x))
        if data["version"] >= 10:
            from .interactions import InteractionRule, OutcomeCheckDefinition

            for x in data["interaction_rules"]:
                result.add_interaction_rule(InteractionRule.from_data(x))
            for x in data["outcome_checks"]:
                result.add_outcome_check(OutcomeCheckDefinition.from_data(x))
        if data["version"] >= 11:
            from .battle_states import BattleStatePolicy

            for x in data["battle_state_policies"]:
                result.add_battle_state_policy(BattleStatePolicy.from_data(x))
        if data["version"] >= 12:
            from .targeting import BattleTargetingDefinition, FormationDefinition

            for x in data["formations"]:
                result.add_formation(FormationDefinition.from_data(x))
            for x in data["battle_targeting"]:
                result.add_battle_targeting(BattleTargetingDefinition.from_data(x))
        if data["version"] >= 13:
            from .battle_lifecycle import BattleEscapeRule, BattleObjectiveDefinition

            for x in data["battle_objectives"]:
                result.add_battle_objective(BattleObjectiveDefinition.from_data(x))
            for x in data["escape_rules"]:
                result.add_escape_rule(BattleEscapeRule.from_data(x))
        if data["version"] >= 14:
            from .battle_scheduler import BattleSchedulerDefinition

            for x in data["battle_schedulers"]:
                result.add_battle_scheduler(BattleSchedulerDefinition.from_data(x))
        if data["version"] >= 15:
            from .battle_timing import ActionTimingDefinition

            for x in data["action_timings"]:
                result.add_action_timing(ActionTimingDefinition.from_data(x))
        if data["version"] >= 16:
            from .action_sequences import ActionSequenceDefinition

            for x in data.get("action_sequences", ()):
                result.add_action_sequence(ActionSequenceDefinition.from_data(x))
        if data["version"] >= 17:
            from .gauge_composition import GaugeCompositionDefinition

            for x in data.get("gauge_compositions", ()):
                result.add_gauge_composition(GaugeCompositionDefinition.from_data(x))
        if data["version"] >= 18:
            from .reactions import ReactionDefinition

            for x in data.get("reactions", ()):
                result.add_reaction(ReactionDefinition.from_data(x))
        if data["version"] >= 19:
            from .enemy_ai import EnemyAIDefinition

            for x in data.get("enemy_ai", ()):
                result.add_enemy_ai(EnemyAIDefinition.from_data(x))
        if data["version"] >= 20:
            from .battle_transactions import ActionTransactionPolicy

            for x in data.get("action_transactions", ()):
                result.add_action_transaction(ActionTransactionPolicy.from_data(x))
        if data["version"] >= 21:
            from .composition import CompositionRecipeDefinition

            for x in data.get("composition_recipes", ()):
                result.add_composition_recipe(CompositionRecipeDefinition.from_data(x))
        if data["version"] >= 22:
            from .party_setup import PartyPresentationPolicyDefinition, PartySetupDefinition

            for x in data.get("party_setups", ()):
                result.add_party_setup(PartySetupDefinition.from_data(x))
            for x in data.get("party_presentation_policies", ()):
                result.add_party_presentation_policy(PartyPresentationPolicyDefinition.from_data(x))
        if data["version"] >= 23:
            from .enemy_behavior import EnemyBehaviorBinding

            for x in data.get("enemy_behavior_bindings", ()):
                result.add_enemy_behavior_binding(EnemyBehaviorBinding.from_data(x))
        if data["version"] >= 24:
            from .battle_session_rules import BattleSessionRules

            for x in data.get("battle_session_rules", ()):
                result.add_battle_session_rules(BattleSessionRules.from_data(x))
        if data["version"] >= 28:
            from .behavior_tree import BehaviorTree

            for x in data.get("behavior_trees", ()):
                result.add_behavior_tree(BehaviorTree.from_data(x))
        if data["version"] >= 27:
            from .drop_tables import DropTable

            for x in data.get("drop_tables", ()):
                result.add_drop_table(DropTable.from_data(x))
        if data["version"] >= 26:
            from .world_interactions import WorldInteraction

            for x in data.get("world_interactions", ()):
                result.add_world_interaction(WorldInteraction.from_data(x))
        if data["version"] >= 25:
            from .economy import ShopDefinition
            from .quests import QuestDefinition

            for x in data.get("shops", ()):
                result.add_shop(ShopDefinition.from_data(x))
            for x in data.get("quests", ()):
                result.add_quest(QuestDefinition.from_data(x))
            from .equipment_sets import EquipmentSetDefinition

            for x in data.get("equipment_sets", ()):
                result.add_equipment_set(EquipmentSetDefinition.from_data(x))
            from .capture import CaptureRule
            from .world_record import AchievementDefinition, FactionDefinition

            for x in data.get("factions", ()):
                result.add_faction(FactionDefinition.from_data(x))
            for x in data.get("achievements", ()):
                result.add_achievement(AchievementDefinition.from_data(x))
            for x in data.get("capture_rules", ()):
                result.add_capture_rule(CaptureRule.from_data(x))
        return result
