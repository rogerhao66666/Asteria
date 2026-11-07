from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class Command(Protocol):
    @property
    def label(self) -> str: ...
    def redo(self) -> None: ...
    def undo(self) -> None: ...


class CommandStack:
    """Undo/redo stack whose history positions have unique identities.

    A simple integer revision is insufficient: execute A -> save -> undo ->
    execute B can produce the same numeric revision while representing a
    different document state. Each branch therefore receives a fresh state ID.
    """

    def __init__(self):
        self._undo = []
        self._redo = []
        self._current_state_id = 0
        self._next_state_id = 1

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    @property
    def undo_label(self):
        return self._undo[-1][0].label if self._undo else None

    @property
    def redo_label(self):
        return self._redo[-1][0].label if self._redo else None

    @property
    def current_state_id(self):
        return self._current_state_id

    def execute(self, command: Command):
        before = self._current_state_id
        command.redo()
        after = self._next_state_id
        self._next_state_id += 1
        self._undo.append((command, before, after))
        self._redo.clear()
        self._current_state_id = after

    def record_applied(self, command: Command):
        """Record a command whose redo effects are already applied."""
        before = self._current_state_id
        after = self._next_state_id
        self._next_state_id += 1
        self._undo.append((command, before, after))
        self._redo.clear()
        self._current_state_id = after

    def undo(self):
        if not self._undo:
            return False
        command, before, after = self._undo.pop()
        command.undo()
        self._redo.append((command, before, after))
        self._current_state_id = before
        return True

    def redo(self):
        if not self._redo:
            return False
        command, before, after = self._redo.pop()
        command.redo()
        self._undo.append((command, before, after))
        self._current_state_id = after
        return True

    def clear(self):
        self._undo.clear()
        self._redo.clear()
        self._current_state_id = 0
        self._next_state_id = 1


@dataclass(slots=True)
class SetAttributeCommand:
    target: object
    attribute: str
    new_value: object
    old_value: object
    description: str | None = None

    @property
    def label(self):
        return self.description or f"Set {self.attribute}"

    def redo(self):
        setattr(self.target, self.attribute, self.new_value)

    def undo(self):
        setattr(self.target, self.attribute, self.old_value)


@dataclass(slots=True)
class SetSkeletonCommand:
    target: object
    new_skeleton: object
    old_skeleton: object
    description: str = "Edit skeleton"

    @property
    def label(self):
        return self.description

    def redo(self):
        self.target.set_skeleton(self.new_skeleton)

    def undo(self):
        self.target.set_skeleton(self.old_skeleton)


@dataclass(slots=True)
class RenameCommand:
    target: object
    new_name: str
    old_name: str

    @property
    def label(self):
        return f"Rename {self.old_name}"

    def redo(self):
        self.target.name = self.new_name

    def undo(self):
        self.target.name = self.old_name


@dataclass(slots=True)
class AddEntityCommand:
    scene: object
    entity: object

    @property
    def label(self):
        return f"Add Entity {self.entity.name}"

    def redo(self):
        self.entity._destroy_requested = False
        self.scene.add_entity(self.entity)

    def undo(self):
        self.scene.detach_entity(self.entity)


@dataclass(slots=True)
class RemoveEntityCommand:
    scene: object
    entity: object

    @property
    def label(self):
        return f"Remove Entity {self.entity.name}"

    def redo(self):
        self.scene.detach_entity(self.entity)

    def undo(self):
        self.entity._destroy_requested = False
        self.scene.add_entity(self.entity)


@dataclass(slots=True)
class AddComponentCommand:
    entity: object
    component: object

    @property
    def label(self):
        return f"Add {type(self.component).__name__}"

    def redo(self):
        self.entity.add_component(self.component)

    def undo(self):
        self.entity.detach_component(type(self.component))


@dataclass(slots=True)
class RemoveComponentCommand:
    entity: object
    component: object

    @property
    def label(self):
        return f"Remove {type(self.component).__name__}"

    def redo(self):
        detached = self.entity.detach_component(type(self.component))
        if detached is not self.component:
            raise RuntimeError("component identity changed during remove")

    def undo(self):
        self.entity.add_component(self.component)


class CommandTransaction:
    def __init__(self, label, commands=()):
        self._label = str(label)
        self.commands = list(commands)

    @property
    def label(self):
        return self._label

    def add(self, command):
        self.commands.append(command)
        return command

    def redo(self):
        completed = []
        try:
            for command in self.commands:
                command.redo()
                completed.append(command)
        except Exception:
            for command in reversed(completed):
                command.undo()
            raise

    def undo(self):
        for command in reversed(self.commands):
            command.undo()


@dataclass(slots=True)
class DuplicateEntityCommand:
    scene: object
    source_entity: object
    duplicate_entity: object

    @property
    def label(self):
        return f"Duplicate Entity {self.source_entity.name}"

    def redo(self):
        self.duplicate_entity._destroy_requested = False
        self.scene.add_entity(self.duplicate_entity)

    def undo(self):
        self.scene.detach_entity(self.duplicate_entity)


@dataclass(slots=True)
class ReorderEntityCommand:
    scene: object
    entity: object
    new_index: int
    old_index: int

    @property
    def label(self):
        return f"Reorder Entity {self.entity.name}"

    def redo(self):
        self.scene.move_entity(self.entity, self.new_index)

    def undo(self):
        self.scene.move_entity(self.entity, self.old_index)


@dataclass(slots=True)
class MoveEntityToSceneCommand:
    source_scene: object
    target_scene: object
    entity: object
    target_index: int | None = None
    source_index: int | None = None

    @property
    def label(self):
        return f"Move Entity {self.entity.name}"

    def redo(self):
        if self.source_index is None:
            self.source_index = self.source_scene.entity_index(self.entity)
        self.source_scene.detach_entity(self.entity)
        self.target_scene.add_entity(self.entity)
        if self.target_index is not None:
            self.target_scene.move_entity(self.entity, self.target_index)

    def undo(self):
        self.target_scene.detach_entity(self.entity)
        self.source_scene.add_entity(self.entity)
        if self.source_index is not None:
            self.source_scene.move_entity(self.entity, self.source_index)


@dataclass(slots=True)
class AddSceneCommand:
    project: object
    scene: object

    @property
    def label(self):
        return f"Add Scene {self.scene.name}"

    def redo(self):
        self.project.add_scene(self.scene)

    def undo(self):
        self.project.detach_scene(self.scene)


@dataclass(slots=True)
class RemoveSceneCommand:
    project: object
    scene: object
    old_index: int | None = None
    old_startup_scene_id: str | None = None

    @property
    def label(self):
        return f"Remove Scene {self.scene.name}"

    def redo(self):
        if self.old_index is None:
            self.old_index = self.project.scene_index(self.scene)
            self.old_startup_scene_id = self.project.startup_scene_id
        self.project.detach_scene(self.scene)

    def undo(self):
        self.project.add_scene(self.scene)
        self.project.move_scene(self.scene, self.old_index)
        self.project.startup_scene_id = self.old_startup_scene_id


@dataclass(slots=True)
class ReorderSceneCommand:
    project: object
    scene: object
    new_index: int
    old_index: int

    @property
    def label(self):
        return f"Reorder Scene {self.scene.name}"

    def redo(self):
        self.project.move_scene(self.scene, self.new_index)

    def undo(self):
        self.project.move_scene(self.scene, self.old_index)
