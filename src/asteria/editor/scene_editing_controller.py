from .clipboard import build_duplicate_entity_command, build_paste_entity_command
from .commands import CommandTransaction, SetAttributeCommand
from .component_picker import build_component_choices
from .editing import EditError, build_set_component_field_command
from .hierarchy import build_reorder_entity_command
from .scenes import (
    SceneEditError,
    build_add_scene_command,
    build_remove_scene_command,
    build_reorder_scene_command,
)
from .structure import (
    StructureEditError,
    build_add_component_command,
    build_add_entity_command,
    build_remove_component_command,
    build_remove_entity_command,
    build_rename_command,
)
from .tile_edit import (
    AddTileLayerCommand,
    RemoveTileLayerCommand,
    ReorderTileLayerCommand,
    SetTileLayerPropertyCommand,
    TileEditError,
)
from .authoring_context import scene_authoring_source
from .scene_render import resolve_texture_source
from .starter_project import starter_tileset_preview

try:
    from PySide6.QtWidgets import QInputDialog, QMessageBox
except ImportError:
    QInputDialog = None
    QMessageBox = None

from asteria.graphics import TileLayer


class SceneEditingController:
    """Owns tile-layer and scene/entity structure editing behind the Qt shell.

    `window` is the AsteriaEditorWindow: it is the Qt parent for modal dialogs
    and the owner of cross-cutting refresh/action orchestration that this
    controller triggers after an edit.
    """

    def __init__(self, window, document, viewport, tile_palette, tile_layers, animation_widget):
        self.window = window
        self.document = document
        self.viewport = viewport
        self.tile_palette = tile_palette
        self.tile_layers = tile_layers
        self.animation_widget = animation_widget
        self._starter_preview = None

    def _sync_scene_authoring_context(self):
        self.set_tilemap_render_source(scene_authoring_source(self.document))

    def set_animation_clip_set_view(self, clip_set_id, clip_set):
        self.document.asset_views.set_clip_set(clip_set_id, clip_set)
        self.animation_widget.set_clips(tuple(clip_set.clips))
        self.animation_widget.set_status(f"{len(clip_set.clips)} clips available")

    def set_sprite_sheet_view(self, asset_id, sprite_sheet):
        self.document.asset_views.set_sprite_sheet(asset_id, sprite_sheet)
        self.viewport.texture_cache.clear()
        self.viewport.refresh()

    def set_tilemap_render_source(self, source):
        self.viewport.set_render_source(source)
        no_project = source is None and self.document.project is None
        if no_project:
            # The palette shows the editor's built-in tiles even before a
            # project exists, the way a new RPG Maker install already has its
            # default resources; painting still needs a project to hold the map.
            if self._starter_preview is None:
                self._starter_preview = starter_tileset_preview()
            self.tile_palette.set_tileset(*self._starter_preview)
        elif source is None:
            self.tile_palette.set_tileset(None)
        else:
            sheet = source.sprite_sheet
            texture = getattr(sheet, "texture", None)
            self.tile_palette.set_tileset(
                source.tileset,
                sheet,
                resolve_texture_source(self.document, texture.asset_id)
                if texture is not None
                else None,
            )
        layer = self.viewport.tile_tools.active_layer if source is not None else None
        self.tile_palette.set_layer(layer)
        if no_project:
            self.tile_palette.show_hint("Built-in tiles · File → New Project to paint")
        self.tile_layers.set_tilemap(
            source.tilemap if source is not None else None, layer
        )

    def _select_tile_layer(self, layer):
        self.viewport.set_active_tile_layer(layer)
        self.tile_palette.set_layer(layer)

    def _add_tile_layer(self):
        source = self.viewport.render_source
        if source is None:
            return
        names = {l.name for l in source.tilemap.layers}
        index = 1
        name = "Layer"
        while name in names:
            index += 1
            name = f"Layer {index}"
        layer = TileLayer(name, order=len(source.tilemap.layers))
        self.document.execute(AddTileLayerCommand(source.tilemap, layer))
        self.viewport.set_active_tile_layer(layer)
        self.window.refresh_all()

    def _remove_tile_layer(self, layer):
        source = self.viewport.render_source
        if source is None:
            return
        try:
            self.document.execute(RemoveTileLayerCommand(source.tilemap, layer))
        except TileEditError:
            return
        self.viewport.tile_tools.active_layer = source.tilemap.layers[0]
        self.window.refresh_all()

    def _move_tile_layer(self, layer, index):
        source = self.viewport.render_source
        if source is None:
            return
        self.document.execute(ReorderTileLayerCommand(source.tilemap, layer, index))
        self.window.refresh_all()

    def _set_tile_layer_visible(self, layer, value):
        self.document.execute(
            SetTileLayerPropertyCommand(layer, "visible", bool(value))
        )
        self.window.refresh_all()

    def _set_tile_layer_collision(self, layer, value):
        self.document.execute(
            SetTileLayerPropertyCommand(layer, "collision_enabled", bool(value))
        )
        self.window.refresh_all()

    def _execute_structure(self, command, selection_kind=None, selection_value=None):
        self.document.execute(command)
        if selection_kind is not None:
            self.document.selection.set_single(selection_kind, selection_value)
        self.window.refresh_all()

    def rename_selected(self):
        sel = self.document.selection
        if (
            sel.kind not in {"project", "scene", "entity"}
            or sel.value is None
            or sel.multiple
        ):
            return False
        name, ok = QInputDialog.getText(
            self.window, "Rename", "Name:", text=sel.value.name
        )
        if not ok:
            return False
        try:
            command = build_rename_command(sel.value, name)
        except StructureEditError as exc:
            QMessageBox.warning(self.window, "Rename", str(exc))
            return False
        if command.new_name == command.old_name:
            return True
        self._execute_structure(command, sel.kind, sel.value)
        return True

    def add_scene(self):
        if self.document.project is None:
            return False
        name, ok = QInputDialog.getText(self.window, "Add Scene", "Name:", text="Scene")
        if not ok:
            return False
        try:
            command = build_add_scene_command(self.document.project, name)
        except SceneEditError as exc:
            QMessageBox.warning(self.window, "Add Scene", str(exc))
            return False
        self._execute_structure(command, "scene", command.scene)
        return True

    def delete_scene(self):
        sel = self.document.selection
        if (
            sel.kind != "scene"
            or sel.value is None
            or sel.multiple
            or self.document.project is None
        ):
            return False
        try:
            command = build_remove_scene_command(self.document.project, sel.value)
        except SceneEditError as exc:
            QMessageBox.warning(self.window, "Delete Scene", str(exc))
            return False
        self.document.execute(command)
        self.document.selection.set_single("scene", self.document.project.scenes()[0])
        self.window.refresh_all()
        return True

    def set_startup_scene(self):
        sel = self.document.selection
        project = self.document.project
        if project is None or sel.kind != "scene" or sel.multiple or sel.value is None:
            return False
        scene = sel.value
        if project.startup_scene_id == scene.id:
            return True
        self.document.execute(SetAttributeCommand(
            project, "startup_scene_id", scene.id, project.startup_scene_id,
            f"Set Startup Scene {scene.name}",
        ))
        self.window.refresh_all()
        return True

    def move_selected(self, delta):
        sel = self.document.selection
        if sel.multiple or sel.value is None:
            return False
        try:
            if sel.kind == "scene":
                project = self.document.project
                old = project.scene_index(sel.value)
                new = max(0, min(old + int(delta), len(project.scenes()) - 1))
                if new == old:
                    return True
                command = build_reorder_scene_command(project, sel.value, new)
            elif sel.kind == "entity":
                scene = sel.value.scene
                old = scene.entity_index(sel.value)
                new = max(0, min(old + int(delta), len(scene.entities()) - 1))
                if new == old:
                    return True
                command = build_reorder_entity_command(sel.value, new)
            else:
                return False
        except (SceneEditError, ValueError) as exc:
            QMessageBox.warning(self.window, "Move", str(exc))
            return False
        self.document.execute(command)
        self.window.refresh_all()
        return True

    def toggle_selected_entity_enabled(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.multiple or sel.value is None:
            return False
        entity = sel.value
        self.document.execute(SetAttributeCommand(
            entity, "enabled", not entity.enabled, entity.enabled,
            f"{'Disable' if entity.enabled else 'Enable'} Entity {entity.name}",
        ))
        self.window.refresh_all()
        return True

    def add_entity(self):
        sel = self.document.selection
        scene = (
            sel.value
            if sel.kind == "scene"
            else getattr(sel.value, "scene", None)
            if sel.kind == "entity"
            else None
        )
        if scene is None or sel.multiple:
            return False
        name, ok = QInputDialog.getText(self.window, "Add Entity", "Name:", text="Entity")
        if not ok:
            return False
        try:
            command = build_add_entity_command(scene, name)
        except StructureEditError as exc:
            QMessageBox.warning(self.window, "Add Entity", str(exc))
            return False
        self._execute_structure(command, "entity", command.entity)
        return True

    def add_component(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        choices = [
            c
            for c in build_component_choices(
                self.document.component_registry, sel.value
            )
            if c.addable
        ]
        if not choices:
            QMessageBox.information(
                self.window, "Add Component", "No addable registered components."
            )
            return False
        labels = [c.display_name for c in choices]
        label, ok = QInputDialog.getItem(
            self.window, "Add Component", "Component:", labels, 0, False
        )
        if not ok:
            return False
        choice = choices[labels.index(label)]
        try:
            command = build_add_component_command(sel.value, choice.component_type)
        except StructureEditError as exc:
            QMessageBox.warning(self.window, "Add Component", str(exc))
            return False
        self._execute_structure(command, "component", command.component)
        return True

    def copy_selected(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        self.document.clipboard.copy_entity(sel.value)
        self.window._refresh_actions()
        return True

    def duplicate_selected(self):
        sel = self.document.selection
        if sel.kind != "entity" or not sel.values:
            return False
        commands = [
            build_duplicate_entity_command(value, self.document.component_registry)
            for value in sel.values
        ]
        if len(commands) == 1:
            self._execute_structure(
                commands[0], "entity", commands[0].duplicate_entity
            )
        else:
            tx = CommandTransaction(f"Duplicate {len(commands)} Entities", commands)
            self.document.execute(tx)
            self.document.selection.set_many(
                "entity", tuple(command.duplicate_entity for command in commands)
            )
            self.window.refresh_all()
        return True

    def paste_entity(self):
        sel = self.document.selection
        scene = (
            sel.value
            if sel.kind == "scene"
            else getattr(sel.value, "scene", None)
            if sel.kind == "entity"
            else None
        )
        if scene is None or sel.multiple:
            return False
        try:
            command = build_paste_entity_command(
                scene, self.document.clipboard, self.document.component_registry
            )
        except ValueError as exc:
            QMessageBox.warning(self.window, "Paste", str(exc))
            return False
        self._execute_structure(command, "entity", command.entity)
        return True

    def delete_selected(self):
        sel = self.document.selection
        try:
            if sel.kind == "entity" and sel.values:
                entities = tuple(sel.values)
                scenes = {id(entity.scene): entity.scene for entity in entities}
                commands = [build_remove_entity_command(entity) for entity in entities]
                if len(commands) == 1:
                    self.document.execute(commands[0])
                else:
                    self.document.execute(
                        CommandTransaction(f"Delete {len(commands)} Entities", commands)
                    )
                if len(scenes) == 1:
                    self.document.selection.set_single("scene", next(iter(scenes.values())))
                else:
                    self.document.selection.set_single("project", self.document.project)
                self.window.refresh_all()
                return True
            if sel.kind == "component" and sel.value is not None and not sel.multiple:
                entity = sel.value.entity
                self._execute_structure(
                    build_remove_component_command(sel.value), "entity", entity
                )
                return True
        except StructureEditError as exc:
            QMessageBox.warning(self.window, "Delete", str(exc))
        return False

    def edit_selected_component_field(self, field_name, raw_value):
        sel = self.document.selection
        if sel.kind != "component" or sel.value is None or sel.multiple:
            return False, "No single component selected"
        try:
            command = build_set_component_field_command(
                sel.value, field_name, raw_value
            )
            if command.new_value == command.old_value:
                return True, None
            self.document.execute(command)
        except EditError as exc:
            return False, str(exc)
        self.window._refresh_actions()
        self.window._refresh_title()
        self.viewport.refresh()
        return True, None

    def undo(self):
        if not self.document.undo():
            return False
        self.document.selection.set_single(
            "project" if self.document.project else "none", self.document.project
        )
        self.window.refresh_all()
        return True

    def redo(self):
        if not self.document.redo():
            return False
        self.document.selection.set_single(
            "project" if self.document.project else "none", self.document.project
        )
        self.window.refresh_all()
        return True
