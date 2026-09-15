"""One Unit family over the separate Actor and Enemy record stores.

Authoring a party member and authoring a monster is the same job — a name, a
sprite, stats, resources, tags and abilities — so the editor presents one
"Units" list with a `kind` field instead of two near-identical categories. The
canonical database is untouched: actors still live in `db.actors` and enemies
in `db.enemies`, and flipping `kind` moves the record from one to the other.

Unit ids are therefore unique across both stores; creating one that already
exists on either side is refused, the same way each store refuses a duplicate.
"""
from __future__ import annotations

from asteria.rpg import ActorDefinition, EnemyDefinition

ACTOR = "actor"
ENEMY = "enemy"
KIND_FIELD = "kind"


class UnitAuthoringError(RuntimeError):
    pass


def _resource_maximums(resources):
    """Enemy resources are plain numbers; actor resources are min/max/current."""
    result = {}
    for key, value in dict(resources or {}).items():
        result[key] = float(value["maximum"]) if isinstance(value, dict) else float(value)
    return result


def to_actor_data(data):
    if "actor_id" in data and KIND_FIELD not in data:
        return dict(data)
    return {
        "schema": "asteria.rpg.actor",
        "version": 2,
        "actor_id": data.get("actor_id") or data.get("enemy_id") or "",
        "display_name": data.get("display_name") or "",
        "class_assignments": list(data.get("class_assignments") or ()),
        "base_stats": dict(data.get("base_stats") or data.get("stats") or {}),
        "base_resources": dict(
            data.get("base_resources") or _resource_maximums(data.get("resources"))
        ),
        "tags": list(data.get("tags") or ()),
        "abilities": list(data.get("abilities") or ()),
    }


def to_enemy_data(data):
    return {
        "schema": "asteria.rpg.enemy",
        "version": 1,
        "enemy_id": data.get("enemy_id") or data.get("actor_id") or "",
        "display_name": data.get("display_name") or "",
        "stats": dict(data.get("stats") or data.get("base_stats") or {}),
        "resources": _resource_maximums(
            data.get("resources") or data.get("base_resources")
        ),
        "tags": list(data.get("tags") or ()),
        "abilities": list(data.get("abilities") or ()),
        "reward": data.get("reward") or {"currencies": {}, "experience": {}, "loot": []},
    }


def encode_unit(value):
    """Canonical record -> editor data, with `kind` first so it reads as a field."""
    data = value.to_data()
    kind = ACTOR if isinstance(value, ActorDefinition) else ENEMY
    return {KIND_FIELD: kind, **data}


def decode_unit(data):
    data = dict(data)
    kind = str(data.pop(KIND_FIELD, "") or "").strip().lower()
    if kind not in (ACTOR, ENEMY):
        kind = ENEMY if "enemy_id" in data else ACTOR
    if kind == ENEMY:
        return EnemyDefinition.from_data(to_enemy_data(data))
    return ActorDefinition.from_data(to_actor_data(data))


class UnitAdapterFunctions:
    """ids/get/edit/delete/create over both stores, resolved by id."""

    def __init__(self, database, actor_class, enemy):
        self.database = database
        self.actor_class = actor_class
        self.enemy = enemy

    def kind_of(self, key):
        key = str(key)
        if key in self.database.actors:
            return ACTOR
        if key in self.database.enemies:
            return ENEMY
        return None

    def ids(self):
        return tuple(sorted(set(self.database.actors) | set(self.database.enemies)))

    def get(self, key):
        kind = self.kind_of(key)
        if kind == ACTOR:
            return self.database.actors[str(key)]
        if kind == ENEMY:
            return self.database.enemies[str(key)]
        raise UnitAuthoringError(f"unknown unit: {key}")

    def create(self, key):
        key = str(key).strip()
        if self.kind_of(key) is not None:
            raise UnitAuthoringError(f"duplicate unit: {key}")
        return self.actor_class.create_actor(key)

    def delete(self, key):
        kind = self.kind_of(key)
        if kind == ACTOR:
            return self.actor_class.delete_actor(key)
        if kind == ENEMY:
            return self.enemy.delete_enemy(key)
        raise UnitAuthoringError(f"unknown unit: {key}")

    def duplicate(self, key, new_key):
        kind = self.kind_of(key)
        if kind == ACTOR:
            return self.actor_class.duplicate_actor(key, new_key)
        source = self.get(key)
        data = source.to_data()
        data["enemy_id"] = str(new_key)
        return self.enemy.create_enemy(EnemyDefinition.from_data(data))

    def edit(self, key, value):
        """Write the record back, moving stores when the kind was changed."""
        key = str(key)
        current = self.kind_of(key)
        target = ACTOR if isinstance(value, ActorDefinition) else ENEMY
        if current == target:
            return self._edit_in_place(target, key, value)
        if current is not None:
            self.delete(key)
        if target == ACTOR:
            return self.actor_class.create_actor(
                key, value.display_name, class_assignments=value.class_assignments,
                base_stats=value.base_stats, base_resources=value.base_resources,
                tags=value.tags, abilities=value.abilities,
            )
        return self.enemy.create_enemy(value)

    def _edit_in_place(self, kind, key, value):
        if kind == ACTOR:
            return self.actor_class.edit_actor(
                key, display_name=value.display_name,
                class_assignments=value.class_assignments,
                base_stats=value.base_stats, base_resources=value.base_resources,
                tags=value.tags, abilities=value.abilities,
            )
        return self.enemy.edit_enemy(key, value)
