"""Editing the project tree and the selection: scenes, entities and components, rename, move,
cut / copy / paste, delete, the Inspector, undo and redo."""

from __future__ import annotations

from asteria.editor.project.clipboard import (
    build_duplicate_entity_command,
    build_paste_entity_command,
)
from asteria.editor.project.commands import CommandTransaction, SetAttributeCommand
from asteria.editor.project.editing import EditError, build_set_component_field_command
from asteria.editor.project.scenes import (
    SceneEditError,
    build_add_scene_command,
    build_remove_scene_command,
    build_reorder_scene_command,
)
from asteria.editor.project.structure import (
    StructureEditError,
    build_add_component_command,
    build_add_entity_command,
    build_remove_component_command,
    build_remove_entity_command,
    build_rename_command,
)
from asteria.editor.scene.component_picker import build_component_choices
from asteria.editor.scene.hierarchy import build_reorder_entity_command
from asteria.editor.scene.inspector import build_inspector_fields

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtWidgets import QApplication, QInputDialog, QMainWindow, QMessageBox
except ImportError:
    QApplication = None
    QMainWindow = object
    Qt = None


class SceneEditingMixin:
    """Editing the project tree and the selection."""

    def refresh_selection_context(self):
        self.refresh_inspector()
        self._sync_scene_authoring_context()
        self._sync_event_context()
        self.code_workspace.refresh_project_context()
        self._refresh_actions()

    def refresh_inspector(self):
        sel = self.document.selection
        if sel.kind == "none" or sel.value is None:
            if sel.multiple:
                self.inspector.show_properties(
                    f"{len(sel.values)} selected", (("Count", len(sel.values), "int"),)
                )
            else:
                self.inspector.show_message("Nothing selected")
            return
        if sel.multiple:
            self.inspector.show_properties(
                f"{len(sel.values)} {sel.kind.title()}s selected",
                (("Count", len(sel.values), "int"),),
            )
            return
        obj = sel.value
        if sel.kind == "project":
            startup = obj.scene(obj.startup_scene_id)
            self.inspector.show_properties(
                "Project",
                (
                    ("Name", obj.name, "str"),
                    (
                        "Startup Scene",
                        startup.name if startup is not None else "None",
                        "Scene",
                    ),
                ),
            )
        elif sel.kind == "scene":
            self.inspector.show_properties(
                "Scene",
                (
                    ("Name", obj.name, "str"),
                    ("Entities", len(obj.entities()), "int"),
                ),
            )
        elif sel.kind == "entity":
            self.inspector.show_entity(obj)
        elif sel.kind == "component":
            self.inspector.show_component(type(obj).__name__, build_inspector_fields(obj))
        elif sel.kind == "asset":
            self.inspector.show_properties(
                "Asset",
                (
                    ("Kind", obj.kind, "str"),
                    ("Path", obj.source_path, "path"),
                ),
            )
        else:
            self.inspector.show_message(f"Selected: {sel.kind}")

    def _execute_structure(self, command, selection_kind=None, selection_value=None):
        self.document.execute(command)
        if selection_kind is not None:
            self.document.selection.set_single(selection_kind, selection_value)
        self.refresh_all()

    def rename_selected(self):
        sel = self.document.selection
        if sel.kind not in {"project", "scene", "entity"} or sel.value is None or sel.multiple:
            return False
        name, ok = QInputDialog.getText(self, "Rename", "Name:", text=sel.value.name)
        if not ok:
            return False
        try:
            command = build_rename_command(sel.value, name)
        except StructureEditError as exc:
            QMessageBox.warning(self, "Rename", str(exc))
            return False
        if command.new_name == command.old_name:
            return True
        self._execute_structure(command, sel.kind, sel.value)
        return True

    def add_scene(self):
        if self.document.project is None:
            return False
        name, ok = QInputDialog.getText(self, "Add Scene", "Name:", text="Scene")
        if not ok:
            return False
        try:
            command = build_add_scene_command(self.document.project, name)
        except SceneEditError as exc:
            QMessageBox.warning(self, "Add Scene", str(exc))
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
            QMessageBox.warning(self, "Delete Scene", str(exc))
            return False
        self.document.execute(command)
        self.document.selection.set_single("scene", self.document.project.scenes()[0])
        self.refresh_all()
        return True

    def set_startup_scene(self):
        sel = self.document.selection
        project = self.document.project
        if project is None or sel.kind != "scene" or sel.multiple or sel.value is None:
            return False
        scene = sel.value
        if project.startup_scene_id == scene.id:
            return True
        self.document.execute(
            SetAttributeCommand(
                project,
                "startup_scene_id",
                scene.id,
                project.startup_scene_id,
                f"Set Startup Scene {scene.name}",
            )
        )
        self.refresh_all()
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
            QMessageBox.warning(self, "Move", str(exc))
            return False
        self.document.execute(command)
        self.refresh_all()
        return True

    def toggle_selected_entity_enabled(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.multiple or sel.value is None:
            return False
        entity = sel.value
        self.document.execute(
            SetAttributeCommand(
                entity,
                "enabled",
                not entity.enabled,
                entity.enabled,
                f"{'Disable' if entity.enabled else 'Enable'} Entity {entity.name}",
            )
        )
        self.refresh_all()
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
        name, ok = QInputDialog.getText(self, "Add Entity", "Name:", text="Entity")
        if not ok:
            return False
        try:
            command = build_add_entity_command(scene, name)
        except StructureEditError as exc:
            QMessageBox.warning(self, "Add Entity", str(exc))
            return False
        self._execute_structure(command, "entity", command.entity)
        return True

    def add_component(self):
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        choices = [
            c
            for c in build_component_choices(self.document.component_registry, sel.value)
            if c.addable
        ]
        if not choices:
            QMessageBox.information(self, "Add Component", "No addable registered components.")
            return False
        labels = [c.display_name for c in choices]
        label, ok = QInputDialog.getItem(self, "Add Component", "Component:", labels, 0, False)
        if not ok:
            return False
        choice = choices[labels.index(label)]
        try:
            command = build_add_component_command(sel.value, choice.component_type)
        except StructureEditError as exc:
            QMessageBox.warning(self, "Add Component", str(exc))
            return False
        self._execute_structure(command, "component", command.component)
        return True

    def cut_selected(self):
        family = self._focused_record_family()
        if family is not None:
            return family.cut_selected()
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        self.document.clipboard.copy_entity(sel.value)
        return self.delete_selected()

    def copy_selected(self):
        family = self._focused_record_family()
        if family is not None:
            return bool(family.copy_selected())
        sel = self.document.selection
        if sel.kind != "entity" or sel.value is None or sel.multiple:
            return False
        self.document.clipboard.copy_entity(sel.value)
        self._refresh_actions()
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
            self._execute_structure(commands[0], "entity", commands[0].duplicate_entity)
        else:
            tx = CommandTransaction(f"Duplicate {len(commands)} Entities", commands)
            self.document.execute(tx)
            self.document.selection.set_many(
                "entity", tuple(command.duplicate_entity for command in commands)
            )
            self.refresh_all()
        return True

    def paste_entity(self):
        family = self._focused_record_family()
        if family is not None:
            return bool(family.paste())
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
            QMessageBox.warning(self, "Paste", str(exc))
            return False
        self._execute_structure(command, "entity", command.entity)
        return True

    def delete_selected(self):
        family = self._focused_record_family()
        if family is not None:
            return family.delete_selected()
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
                self.refresh_all()
                return True
            if sel.kind == "component" and sel.value is not None and not sel.multiple:
                entity = sel.value.entity
                self._execute_structure(
                    build_remove_component_command(sel.value), "entity", entity
                )
                return True
        except StructureEditError as exc:
            QMessageBox.warning(self, "Delete", str(exc))
        return False

    def edit_selected_component_field(self, field_name, raw_value):
        sel = self.document.selection
        if sel.kind != "component" or sel.value is None or sel.multiple:
            return False, "No single component selected"
        return self.edit_component_field(sel.value, field_name, raw_value)

    def edit_entity(self, entity, *, name=None, enabled=None):
        """Rename or switch on/off an entity from the Inspector (undoable)."""
        from asteria.editor.project.commands import RenameCommand, SetAttributeCommand

        if name is not None and str(name).strip() and name != entity.name:
            self.document.execute(RenameCommand(entity, str(name).strip(), entity.name))
        if enabled is not None and bool(enabled) != bool(entity.enabled):
            self.document.execute(
                SetAttributeCommand(entity, "enabled", bool(enabled), entity.enabled)
            )
        self._refresh_actions()
        self._refresh_title()
        self.viewport.refresh()
        return True

    def edit_passability(self, entity, mode):
        """Make an entity passable, block at its feet or block its whole picture (the
        Inspector's Passability, D88; one undo step); (ok, error)."""
        from asteria.editor.assets.image_tools import project_root
        from asteria.editor.scene.passability import build_passability_command, picture_box

        box = picture_box(self.document.project, project_root(self.document), entity)
        try:
            command = build_passability_command(entity, mode, box)
        except ValueError as exc:
            return False, str(exc)
        if command.commands:
            self.document.execute(command)
        self._refresh_actions()
        self._refresh_title()
        self.viewport.refresh()
        # rebuilt after the combo's signal returns: the page holding it is replaced
        QTimer.singleShot(0, lambda e=entity: self.inspector.show_entity(e))
        return True, None

    def edit_component_field(self, component, field_name, raw_value):
        """Set one field of a component from the Inspector (undoable); (ok, error)."""
        try:
            command = build_set_component_field_command(component, field_name, raw_value)
            if command.new_value == command.old_value:
                return True, None
            self.document.execute(command)
        except EditError as exc:
            return False, str(exc)
        self._refresh_actions()
        self._refresh_title()
        self.viewport.refresh()
        return True, None

    def undo(self):
        if not self.document.undo():
            return False
        self.document.selection.set_single(
            "project" if self.document.project else "none", self.document.project
        )
        self.refresh_all()
        return True

    def redo(self):
        if not self.document.redo():
            return False
        self.document.selection.set_single(
            "project" if self.document.project else "none", self.document.project
        )
        self.refresh_all()
        return True
