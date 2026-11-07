from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from asteria.core.values import required_id
from asteria.gameplay import ModifierSet, ResourcePool, StatBlock, TagSet
from asteria.rpg.characters.abilities import AbilityGrant, AbilityResolution, ActorAbilityState


def _numbers(values, label):
    result = {}
    for key, value in dict(values).items():
        key = required_id(key, label)
        value = float(value)
        if not isfinite(value):
            raise ValueError(f"{label} values must be finite")
        result[key] = value
    return result


def _resources(values):
    result = {}
    for key, raw in dict(values).items():
        key = required_id(key, "resource")
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

    icon_id: str = ""  # a project icon shown in menus; written only when set
    # stat -> amount gained per actor level above 1 (a warrior's attack rises faster than a
    # scholar's); written only when set
    level_growth: dict[str, float] = field(default_factory=dict)
    # resource -> maximum gained per actor level above 1 (a knight's health climbs faster than a
    # mage's); written only when set
    resource_growth: dict[str, float] = field(default_factory=dict)
    # what a job asks for before it can be taken: the actor's level and jobs it must already
    # have unlocked; written only when set
    unlock_level: int = 0
    unlock_classes: tuple[str, ...] = ()
    description: str = ""  # what the job is, in the author's words (D91); written only when set
    OPTIONAL_DATA = {
        "description": "",
        "icon_id": "",
        "level_growth": {},
        "resource_growth": {},
        "unlock_level": 0,
        "unlock_classes": [],
    }  # shown in the editor while empty

    def __init__(
        self,
        class_id,
        display_name=None,
        *,
        stat_bonuses=None,
        resource_bonuses=None,
        granted_tags=(),
        granted_abilities=(),
        icon_id="",
        level_growth=None,
        unlock_level=0,
        unlock_classes=(),
        resource_growth=None,
        description="",
    ):
        class_id = required_id(class_id, "class_id")
        if int(unlock_level) < 0:
            raise ValueError("unlock_level must be >= 0")
        object.__setattr__(self, "unlock_level", int(unlock_level))
        object.__setattr__(
            self,
            "unlock_classes",
            tuple(dict.fromkeys(required_id(x, "class_id") for x in unlock_classes)),
        )
        object.__setattr__(self, "class_id", class_id)
        object.__setattr__(self, "display_name", str(display_name or class_id))
        object.__setattr__(self, "stat_bonuses", _numbers(stat_bonuses or {}, "stat"))
        object.__setattr__(self, "resource_bonuses", _numbers(resource_bonuses or {}, "resource"))
        object.__setattr__(
            self,
            "granted_tags",
            tuple(sorted({required_id(x, "tag").lower() for x in granted_tags})),
        )
        object.__setattr__(
            self,
            "granted_abilities",
            tuple(dict.fromkeys(required_id(x, "ability_id") for x in granted_abilities)),
        )
        object.__setattr__(self, "icon_id", str(icon_id or "").strip())
        object.__setattr__(self, "level_growth", _numbers(level_growth or {}, "stat"))
        growth = _numbers(resource_growth or {}, "resource")
        object.__setattr__(self, "resource_growth", growth)
        object.__setattr__(self, "description", str(description or ""))

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
            **({"icon_id": self.icon_id} if self.icon_id else {}),
            **(
                {"level_growth": dict(sorted(self.level_growth.items()))}
                if self.level_growth
                else {}
            ),
            **(
                {"resource_growth": dict(sorted(self.resource_growth.items()))}
                if self.resource_growth
                else {}
            ),
            **({"unlock_level": self.unlock_level} if self.unlock_level else {}),
            **({"unlock_classes": list(self.unlock_classes)} if self.unlock_classes else {}),
            **({"description": self.description} if self.description else {}),
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
            icon_id=data.get("icon_id", ""),
            level_growth=data.get("level_growth"),
            unlock_level=data.get("unlock_level", 0),
            unlock_classes=data.get("unlock_classes", ()),
            resource_growth=data.get("resource_growth"),
            description=data.get("description", ""),
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
        class_id = required_id(class_id, "class_id")
        assignment_id = required_id(assignment_id or class_id, "assignment_id")
        role = required_id(role, "class role")
        object.__setattr__(self, "class_id", class_id)
        object.__setattr__(self, "assignment_id", assignment_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "enabled", bool(enabled))
        object.__setattr__(self, "priority", int(priority))
        object.__setattr__(
            self,
            "progression_track_ids",
            tuple(
                dict.fromkeys(
                    required_id(x, "progression track id") for x in progression_track_ids
                )
            ),
        )
        object.__setattr__(
            self,
            "tags",
            tuple(sorted({required_id(x, "tag").lower() for x in tags})),
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
        if (
            set(data) != expected
            or data.get("schema") != "asteria.rpg.class_assignment"
            or data.get("version") != 1
        ):
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
    description: str = ""  # who they are, in the author's words (D91); written only when set
    OPTIONAL_DATA = {"description": ""}  # shown in the editor while empty

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
        description="",
    ):
        actor_id = required_id(actor_id, "actor_id")
        if class_assignments is not None and class_id is not None:
            raise ValueError("use class_id or class_assignments, not both")
        if class_assignments is None:
            assignments = () if class_id is None else (ClassAssignment(class_id, role="primary"),)
        else:
            assignments = tuple(
                x if isinstance(x, ClassAssignment) else ClassAssignment.from_data(x)
                for x in class_assignments
            )
        ids = [x.assignment_id for x in assignments]
        if len(ids) != len(set(ids)):
            raise ValueError("class assignment ids must be unique per actor")
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "display_name", str(display_name or actor_id))
        object.__setattr__(self, "class_assignments", assignments)
        object.__setattr__(self, "base_stats", _numbers(base_stats or {}, "stat"))
        object.__setattr__(self, "base_resources", _resources(base_resources or {}))
        object.__setattr__(
            self, "tags", tuple(sorted({required_id(x, "tag").lower() for x in tags}))
        )
        object.__setattr__(
            self,
            "abilities",
            tuple(dict.fromkeys(required_id(x, "ability_id") for x in abilities)),
        )
        object.__setattr__(self, "description", str(description or ""))

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
            **({"description": self.description} if self.description else {}),
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
            description=data.get("description", ""),
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
            required_id(data["actor_id"], "actor_id"),
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
        self.class_definition = (
            definitions[assignments[0].class_id] if len(assignments) == 1 else None
        )
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
            track_id
            for assignment in self.class_assignments
            for track_id in assignment.progression_track_ids
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

    def level_growth_bonuses(self, level):
        """Per-class growth gained by ``level`` (stat -> total), over the enabled classes."""
        gained = max(0, int(level) - 1)
        bonuses = {}
        if not gained:
            return bonuses
        for assignment in self.class_assignments:
            if not assignment.enabled:
                continue
            definition = self.class_definitions.get(assignment.class_id)
            for stat, rate in (definition.level_growth if definition else {}).items():
                bonuses[stat] = bonuses.get(stat, 0.0) + rate * gained
        return bonuses

    def level_resource_growth(self, level):
        """Per-class resource growth gained by ``level`` (resource -> extra maximum)."""
        gained = max(0, int(level) - 1)
        bonuses = {}
        for assignment in self.class_assignments if gained else ():
            if not assignment.enabled:
                continue
            definition = self.class_definitions.get(assignment.class_id)
            for resource_id, rate in (definition.resource_growth if definition else {}).items():
                bonuses[resource_id] = bonuses.get(resource_id, 0.0) + rate * gained
        return bonuses

    def build_layers(self, progression=None, allocations=None):
        """What progression tracks and allocated graph ranks add: ``(progression, allocation)``
        - ``_progression_contributions`` and ``allocations.contribution()`` (None without
        allocations). Worked out once and handed to the ``_effective_*`` steps of a build."""
        allotted = None if allocations is None else allocations.contribution()
        return self._progression_contributions(progression), allotted

    def effective_stats(
        self, *, progression=None, allocations=None, loadout=None, passives=None, level=1
    ):
        layers = self.build_layers(progression, allocations)
        tags = self._effective_tags(layers, loadout, passives)
        return self._effective_stats(layers, loadout, passives, level, tags)

    def _effective_stats(self, layers, loadout, passives, level, tags):
        (bonuses, _, _), allotted = layers
        values = StatBlock.from_data(self.stats.to_data())
        for stat, value in bonuses.items():
            values.add(stat, value)
        for stat, value in self.level_growth_bonuses(level).items():
            values.add(stat, value)
        if allotted is not None:
            for stat, value in allotted.stat_bonuses.items():
                values.add(stat, value)
        if loadout is not None:
            values = loadout.modifier_set().evaluate_block(values, tags=tags)
        if passives is not None:
            values = self.effective_passive_modifiers(passives).evaluate_block(values, tags=tags)
        return values

    def effective_tags(self, *, progression=None, allocations=None, loadout=None, passives=None):
        return self._effective_tags(self.build_layers(progression, allocations), loadout, passives)

    def _effective_tags(self, layers, loadout, passives):
        (_, progression_tags, _), contribution = layers
        result = TagSet(self.tags.values())
        for tag in progression_tags:
            result.add(tag)
        if contribution is not None:
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

    def effective_capabilities(
        self, *, progression=None, allocations=None, loadout=None, passives=None
    ):
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

    def equipment_eligibility(
        self, loadout, slot_id, item, *, progression=None, allocations=None, passives=None
    ):
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

    def equip_item(
        self, loadout, slot_id, item, *, progression=None, allocations=None, passives=None
    ):
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
        tags=None,
    ):
        layers = self.build_layers(progression, allocations)
        return self._resolve_abilities(
            layers, progression, loadout, passives, evolution_rules, tags
        )

    def _resolve_abilities(self, layers, progression, loadout, passives, evolution_rules, tags):
        """``resolve_abilities`` from ``build_layers``; ``progression`` picks evolutions."""
        (_, _, progression_abilities), allotted = layers
        grants = []

        def add(ability_id, source_kind, source_id):
            grants.append(AbilityGrant(str(ability_id), str(source_kind), str(source_id)))

        for ability_id in self.definition.abilities:
            add(ability_id, "intrinsic", self.definition.actor_id)
        for assignment in self.class_assignments:
            definition = self.class_definitions[assignment.class_id]
            for ability_id in definition.granted_abilities:
                add(ability_id, "class", assignment.assignment_id)
        for ability_id in progression_abilities:
            add(ability_id, "progression", "progression")
        if allotted is not None:
            for ability_id, source_id in allotted.ability_grants:
                add(ability_id, "allocation", source_id)
        for ability_id in self.ability_state.learned_abilities:
            add(ability_id, "learned", self.definition.actor_id)
        if loadout is not None:
            for item in loadout.working():
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

        ordered = list(dict.fromkeys(grant.ability_id for grant in grants))

        rules = tuple(evolution_rules)
        by_source = {}
        for rule in rules:
            if not rule.matches(progression, tags):
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
        self,
        *,
        progression=None,
        allocations=None,
        loadout=None,
        passives=None,
        evolution_rules=(),
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
        passives = dict(passives or {})
        for passive_id in self.ability_state.active_passives:
            passive = passives.get(passive_id)
            if passive is not None:
                for modifier in passive.modifiers:
                    result.add(modifier)
        return result

    def effective_passive_tags(self, passives):
        result = set()
        passives = dict(passives or {})
        for passive_id in self.ability_state.active_passives:
            passive = passives.get(passive_id)
            if passive is not None:
                result.update(passive.tags)
        return tuple(sorted(result))
