from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .commands import CommandStack


@dataclass(slots=True)
class EditorSelection:
    kind: str = "none"
    value: Any = None
    values: tuple = ()

    @property
    def multiple(self):
        return len(self.values) > 1

    def set_single(self, kind, value):
        self.kind = kind
        self.value = value
        self.values = () if value is None else (value,)

    def set_many(self, kind, values):
        values = tuple(values)
        self.kind = kind if values else "none"
        self.values = values
        self.value = values[0] if len(values) == 1 else None


class EditorDocument:
    def __init__(
        self, project=None, *, component_registry=None, clipboard=None, file_path=None
    ):
        from asteria.core import ComponentRegistry, PersistentComponent, Transform
        from asteria.gameplay import GameplayAttributesComponent
        from asteria.runtime import (
            ActorLinkComponent,
            Animator2DComponent,
            Camera2DComponent,
            Interaction2DComponent,
            SpriteRenderer2D,
            TileMap2DComponent,
        )

        from .asset_views import EditorAssetViews
        from .clipboard import EditorClipboard

        if component_registry is None:
            component_registry = ComponentRegistry()
            component_registry.register(Transform)
            component_registry.register(SpriteRenderer2D)
            component_registry.register(Camera2DComponent)
            component_registry.register(Interaction2DComponent)
            component_registry.register(Animator2DComponent)
            component_registry.register(TileMap2DComponent)
            component_registry.register(GameplayAttributesComponent)
            component_registry.register(ActorLinkComponent)
            component_registry.register(PersistentComponent)
        self.project = project
        self.selection = EditorSelection()
        self.component_registry = component_registry
        self.clipboard = clipboard or EditorClipboard()
        self.asset_views = EditorAssetViews()
        self.commands = CommandStack()
        self.saved_state_id = self.commands.current_state_id
        self.file_path = Path(file_path) if file_path is not None else None

    @property
    def revision(self):
        # Compatibility/read-only diagnostic. Dirty logic does not depend on it.
        return self.commands.current_state_id

    @property
    def saved_revision(self):
        return self.saved_state_id

    @property
    def dirty(self):
        return self.commands.current_state_id != self.saved_state_id

    def mark_saved(self):
        self.saved_state_id = self.commands.current_state_id

    def execute(self, command):
        self.commands.execute(command)

    def undo(self):
        return self.commands.undo()

    def redo(self):
        return self.commands.redo()

    def set_project(self, project, *, file_path=None):
        self.project = project
        self.selection = EditorSelection()
        self.commands.clear()
        self.file_path = Path(file_path) if file_path is not None else None
        self.mark_saved()

    def select_project(self):
        self.selection.set_single("project", self.project)

    def select_scene(self, scene):
        self.selection.set_single("scene", scene)

    def select_entity(self, entity):
        self.selection.set_single("entity", entity)

    def select_component(self, component):
        self.selection.set_single("component", component)

    def select_many(self, kind, values):
        self.selection.set_many(kind, values)
