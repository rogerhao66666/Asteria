"""Undoable prefab editing: create, place, change (with propagation), apply and revert."""
from __future__ import annotations

from asteria.core import Transform
from asteria.core.metadata import get_component_schema
from asteria.core.prefab import (
    PrefabDefinition,
    PrefabInstanceComponent,
    instances,
    instantiate,
    prefab_from_entity,
    sync_instance,
)
from asteria.core.serialization import deserialize_component, serialize_component


def _snapshot(entity):
    return [serialize_component(c) for c in entity.components()]


def _restore(entity, snapshot, registry):
    """Put ``entity``'s components back to ``snapshot`` (in place where the type still exists)."""
    wanted = {record["type"]: record for record in snapshot}
    for component in tuple(entity.components()):
        type_name = serialize_component(component)["type"]
        record = wanted.pop(type_name, None)
        if record is None:
            entity.remove_component(type(component))
            continue
        schema = get_component_schema(type(component))
        for name, value in record["fields"].items():
            if schema.fields[name].serialize:
                setattr(component, name, value)
    for record in wanted.values():
        entity.add_component(deserialize_component(record, registry))


class ReplacePrefabsCommand:
    """Set or remove prefab definitions and update every affected instance in the project.

    ``changes`` maps prefab id -> PrefabDefinition (set) or None (remove).
    Instances keep their overrides; variants follow their base.
    """

    def __init__(self, project, registry, changes, label="Edit Prefab"):
        self.project, self.registry, self.changes = project, registry, dict(changes)
        self._label = label
        self._old_library = project.prefabs.to_data()
        self._snapshots = None
        self._applied = False

    @property
    def label(self):
        return self._label

    def execute(self):
        return self.redo()

    def redo(self):
        library = self.project.prefabs
        old = {pid: library.resolve(pid) for pid in library.ids()}
        snapshots = {}
        try:
            for prefab_id, definition in self.changes.items():
                if definition is None:
                    library.remove(prefab_id)
                else:
                    library.set(definition)
            new = {pid: library.resolve(pid) for pid in library.ids()}
            for _scene, entity in instances(self.project.scenes()):
                prefab_id = entity.get(PrefabInstanceComponent).prefab_id
                if prefab_id in old and prefab_id in new and old[prefab_id] != new[prefab_id]:
                    snapshots[entity.id] = (entity, _snapshot(entity))
                    sync_instance(entity, old[prefab_id], new[prefab_id], self.registry)
        except Exception:
            for entity, snapshot in snapshots.values():
                _restore(entity, snapshot, self.registry)
            self._restore_library()
            raise
        self._snapshots = snapshots
        self._applied = True
        return snapshots

    def _restore_library(self):
        from asteria.core.prefab import PrefabLibrary

        restored = PrefabLibrary.from_data(self._old_library)
        self.project.prefabs._prefabs.clear()
        self.project.prefabs._prefabs.update(restored._prefabs)

    def undo(self):
        for entity, snapshot in (self._snapshots or {}).values():
            _restore(entity, snapshot, self.registry)
        self._restore_library()
        self._applied = False


class CreatePrefabFromEntityCommand:
    """Capture an entity as a new prefab and make the entity its first instance."""

    def __init__(self, project, entity, prefab_id, name=None, *, base_prefab_id=""):
        self.project, self.entity = project, entity
        self.definition = prefab_from_entity(entity, prefab_id, name, base_prefab_id=base_prefab_id)
        self._added_marker = None

    @property
    def label(self):
        return f"Create Prefab {self.definition.name}"

    def execute(self):
        return self.redo()

    def redo(self):
        self.project.prefabs.add(self.definition)
        marker = self.entity.try_get(PrefabInstanceComponent)
        if marker is None:
            marker = self._added_marker = self.entity.add_component(PrefabInstanceComponent())
        self._previous_id = marker.prefab_id
        marker.prefab_id = self.definition.prefab_id
        return self.definition

    def undo(self):
        if self._added_marker is not None:
            self.entity.remove_component(PrefabInstanceComponent)
            self._added_marker = None
        else:
            self.entity.get(PrefabInstanceComponent).prefab_id = self._previous_id
        self.project.prefabs.remove(self.definition.prefab_id)


class InstantiatePrefabCommand:
    """Place a new instance of a prefab in a scene."""

    def __init__(self, project, registry, scene, prefab_id, x=0.0, y=0.0, *, name=None):
        self.scene = scene
        self.entity = instantiate(project.prefabs, prefab_id, registry, name=name)
        if not self.entity.has(Transform):
            self.entity.add_component(Transform())
        transform = self.entity.get(Transform)
        transform.x, transform.y = float(x), float(y)

    @property
    def label(self):
        return f"Place Prefab {self.entity.name}"

    def execute(self):
        return self.redo()

    def redo(self):
        self.scene.add_entity(self.entity)
        return self.entity

    def undo(self):
        self.scene.detach_entity(self.entity)


def apply_instance_to_prefab_command(project, registry, entity):
    """Make the instance's current components the prefab's (other instances update)."""
    prefab_id = entity.get(PrefabInstanceComponent).prefab_id
    current = project.prefabs.require(prefab_id)
    captured = prefab_from_entity(entity, prefab_id, current.name, base_prefab_id=current.base_prefab_id)
    definition = PrefabDefinition(prefab_id, current.name, captured.components, current.base_prefab_id,
                                  current.removed_components)
    return ReplacePrefabsCommand(project, registry, {prefab_id: definition}, label=f"Apply to Prefab {current.name}")


class RevertInstanceCommand:
    """Drop all overrides so the instance matches its prefab again (placement kept)."""

    def __init__(self, project, registry, entity):
        self.project, self.registry, self.entity = project, registry, entity
        self._snapshot = None

    @property
    def label(self):
        return f"Revert {self.entity.name} to Prefab"

    def execute(self):
        return self.redo()

    def redo(self):
        prefab_id = self.entity.get(PrefabInstanceComponent).prefab_id
        resolution = self.project.prefabs.resolve(prefab_id)
        self._snapshot = _snapshot(self.entity)
        current = {r["type"]: r["fields"] for r in self._snapshot}
        # Treating the instance's own values as the "old" prefab makes every field an
        # un-overridden one, so the prefab's values win.
        sync_instance(self.entity, current, resolution, self.registry)
        return self.entity

    def undo(self):
        _restore(self.entity, self._snapshot, self.registry)
