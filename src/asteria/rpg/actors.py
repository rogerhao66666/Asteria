from __future__ import annotations

from dataclasses import dataclass, field
from math import isfinite

from asteria.gameplay import ResourcePool, StatBlock, TagSet


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
        object.__setattr__(
            self, "resource_bonuses", _numbers(resource_bonuses or {}, "resource")
        )
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
class ActorDefinition:
    actor_id: str
    display_name: str
    class_id: str | None
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
        base_stats=None,
        base_resources=None,
        tags=(),
        abilities=(),
    ):
        actor_id = _id(actor_id, "actor_id")
        object.__setattr__(self, "actor_id", actor_id)
        object.__setattr__(self, "display_name", str(display_name or actor_id))
        object.__setattr__(
            self, "class_id", None if class_id is None else _id(class_id, "class_id")
        )
        object.__setattr__(self, "base_stats", _numbers(base_stats or {}, "stat"))
        object.__setattr__(self, "base_resources", _resources(base_resources or {}))
        object.__setattr__(
            self, "tags", tuple(sorted({_id(x, "tag").lower() for x in tags}))
        )
        object.__setattr__(
            self,
            "abilities",
            tuple(dict.fromkeys(_id(x, "ability_id") for x in abilities)),
        )

    def to_data(self):
        return {
            "schema": "asteria.rpg.actor",
            "version": 1,
            "actor_id": self.actor_id,
            "display_name": self.display_name,
            "class_id": self.class_id,
            "base_stats": dict(sorted(self.base_stats.items())),
            "base_resources": {
                k: self.base_resources[k] for k in sorted(self.base_resources)
            },
            "tags": list(self.tags),
            "abilities": list(self.abilities),
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.actor" or data.get("version") != 1:
            raise ValueError("unsupported actor definition")
        return cls(
            data["actor_id"],
            data["display_name"],
            class_id=data["class_id"],
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


def build_actor(
    actor: ActorDefinition, class_definition: ClassDefinition | None = None
):
    if actor.class_id is not None and (
        class_definition is None or class_definition.class_id != actor.class_id
    ):
        raise ValueError("actor class definition mismatch")
    stats = StatBlock(actor.base_stats)
    resources = ResourcePool()
    for key, raw in actor.base_resources.items():
        resources.define(
            key, raw["maximum"], minimum=raw["minimum"], current=raw["current"]
        )
    tags = TagSet(actor.tags)
    abilities = list(actor.abilities)
    if class_definition is not None:
        for key, value in class_definition.stat_bonuses.items():
            stats.add(key, value)
        for key, value in class_definition.resource_bonuses.items():
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
        for tag in class_definition.granted_tags:
            tags.add(tag)
        abilities.extend(class_definition.granted_abilities)
    return RpgActorBuild(stats, resources, tags, tuple(dict.fromkeys(abilities)))


@dataclass(frozen=True, slots=True)
class RpgActorSnapshot:
    actor_id: str
    stats: dict
    resources: dict
    tags: dict

    def to_data(self):
        return {
            "schema": "asteria.rpg.actor_snapshot",
            "version": 1,
            "actor_id": self.actor_id,
            "stats": self.stats,
            "resources": self.resources,
            "tags": self.tags,
        }

    @classmethod
    def from_data(cls, data):
        expected = {"schema", "version", "actor_id", "stats", "resources", "tags"}
        if (
            set(data) != expected
            or data["schema"] != "asteria.rpg.actor_snapshot"
            or data["version"] != 1
        ):
            raise ValueError("unsupported actor runtime snapshot")
        return cls(
            _id(data["actor_id"], "actor_id"),
            data["stats"],
            data["resources"],
            data["tags"],
        )


class RpgActorRuntime:
    """Mutable actor state plus derived progression/equipment contributions.

    `stats/resources/tags` are the actor's mutable intrinsic runtime state.
    Equipment and progression are evaluated on demand and never baked into that
    intrinsic state, so unequipping or changing rank cannot leave stale values.
    """

    def __init__(self, actor, class_definition=None):
        self.definition = actor
        self.class_definition = class_definition
        build = build_actor(actor, class_definition)
        self.stats = build.stats
        self.resources = build.resources
        self.tags = build.tags
        self.abilities = build.abilities

    def snapshot(self):
        return RpgActorSnapshot(
            self.definition.actor_id,
            self.stats.to_data(),
            self.resources.to_data(),
            self.tags.to_data(),
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
        return self

    def _progression_contributions(self, progression):
        bonuses = {}
        tags = set()
        abilities = []
        if progression is None:
            return bonuses, tags, abilities
        for track_id in sorted(progression.definitions):
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

    def effective_stats(self, *, progression=None, loadout=None):
        values = StatBlock.from_data(self.stats.to_data())
        bonuses, _, _ = self._progression_contributions(progression)
        for stat, value in bonuses.items():
            values.add(stat, value)
        if loadout is not None:
            values = loadout.modifier_set().evaluate_block(
                values,
                tags=self.effective_tags(progression=progression, loadout=loadout),
            )
        return values

    def effective_tags(self, *, progression=None, loadout=None):
        result = TagSet(self.tags.values())
        _, progression_tags, _ = self._progression_contributions(progression)
        for tag in progression_tags:
            result.add(tag)
        if loadout is not None:
            for tag in loadout.tags():
                result.add(tag)
        return result

    def effective_abilities(self, *, progression=None, loadout=None):
        result = list(self.abilities)
        _, _, progression_abilities = self._progression_contributions(progression)
        result.extend(progression_abilities)
        if loadout is not None:
            result.extend(loadout.abilities())
        return tuple(dict.fromkeys(result))


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

    def validate(self):
        errors = []
        for actor in self.actors.values():
            if actor.class_id is not None and actor.class_id not in self.classes:
                errors.append(
                    f"actor {actor.actor_id} references unknown class {actor.class_id}"
                )
        for encounter in self.encounters.values():
            for member in encounter.members:
                if member.enemy_id not in self.enemies:
                    errors.append(
                        f"encounter {encounter.encounter_id} references unknown enemy {member.enemy_id}"
                    )
        for enemy in self.enemies.values():
            for entry in enemy.reward.loot:
                if entry.item_id not in self.items:
                    errors.append(
                        f"enemy {enemy.enemy_id} reward references unknown item {entry.item_id}"
                    )
            for track_id in enemy.reward.experience:
                if track_id not in self.progression_tracks:
                    errors.append(
                        f"enemy {enemy.enemy_id} reward references unknown progression track {track_id}"
                    )
        if errors:
            raise ValueError(
                "invalid RPG database references: " + "; ".join(sorted(errors))
            )
        return True

    def build_actor(self, actor_id):
        actor = self.actors[str(actor_id)]
        cls = None if actor.class_id is None else self.classes[actor.class_id]
        return RpgActorRuntime(actor, cls)

    def to_data(self):
        return {
            "schema": "asteria.rpg.database",
            "version": 4,
            "actors": [self.actors[k].to_data() for k in sorted(self.actors)],
            "classes": [self.classes[k].to_data() for k in sorted(self.classes)],
            "items": [self.items[k].to_data() for k in sorted(self.items)],
            "equipment": [self.equipment[k].to_data() for k in sorted(self.equipment)],
            "attachments": [
                self.attachments[k].to_data() for k in sorted(self.attachments)
            ],
            "enemies": [self.enemies[k].to_data() for k in sorted(self.enemies)],
            "encounters": [
                self.encounters[k].to_data() for k in sorted(self.encounters)
            ],
            "progression_tracks": [
                self.progression_tracks[k].to_data()
                for k in sorted(self.progression_tracks)
            ],
        }

    @classmethod
    def from_data(cls, data):
        if data.get("schema") != "asteria.rpg.database" or data.get("version") not in {
            1,
            2,
            3,
            4,
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
        return result
