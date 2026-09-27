from pathlib import Path

import pytest

from asteria.assets.local_reference import resolve_rpg_maker_mv_root
from asteria.assets.rpg_maker_mv_generator import RPGMakerMVGeneratorCatalog
from asteria.editor.character_generator_workspace import CharacterGeneratorWorkspace


def _workspace():
    repo = Path(__file__).resolve().parents[1]
    catalog = RPGMakerMVGeneratorCatalog.discover(resolve_rpg_maker_mv_root(repo))
    return CharacterGeneratorWorkspace.create_mv(catalog, "editor-hero")


def _complete_accessory(workspace):
    return next(
        part for part in workspace.choices("accessory", search="AccA", gender="Male")
        if part.part_number == 14 and "Modern_Generator/parts" in part.source_root.as_posix()
    )


def test_mv_workspace_filters_selects_and_synchronizes_three_previews():
    workspace = _workspace()
    part = _complete_accessory(workspace)

    workspace.select("accessory", part.id)

    assert workspace.selected_summary() == (("accessory", part.id),)
    assert workspace.representation_available("walking")
    assert workspace.representation_available("face")
    assert workspace.representation_available("side_view")
    assert workspace.preview_representation("walking").size == (144, 192)
    assert workspace.preview_representation("face").size == (144, 144)
    assert workspace.preview_representation("side_view").size == (576, 384)


def test_mv_workspace_reports_unavailable_representation_without_substitution():
    workspace = _workspace()
    body = next(
        part for part in workspace.choices("body", gender="Male")
        if "modern_body" in part.source_root.as_posix()
    )
    workspace.select("body", body.id)

    assert workspace.representation_available("walking")
    assert not workspace.representation_available("face")
    assert workspace.preview_representation("face") is None
    assert workspace.unavailable_reason("face") == "Face unavailable for Body p1"


def test_mv_widget_exposes_part_grid_and_three_representation_tabs():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.character_generator_widget import CharacterGeneratorWidget

    app = QApplication.instance() or QApplication([])
    widget = CharacterGeneratorWidget(_workspace())
    try:
        assert widget.part_grid.objectName() == "CharacterPartGrid"
        assert [widget.preview_tabs.tabText(i) for i in range(widget.preview_tabs.count())] == [
            "Walking", "Face", "Side View"
        ]
        assert widget.walking_canvas.minimumWidth() >= 144
        assert widget.ground_line_visible is True
    finally:
        widget.close()
        app.processEvents()


def test_editor_shell_exposes_mv_character_creator_in_rpg_workspace():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.workspace.set_mode(WorkspaceMode.RPG)
        labels = [window.rpg_workspace.tabText(i) for i in range(window.rpg_workspace.count())]
        assert labels == ["Database", "Character Creator"]
        assert window.character_creator.part_grid.objectName() == "CharacterPartGrid"
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()


def test_editor_shell_generated_bundle_creates_character_in_selected_scene(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.core import Entity, Scene
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    class Command:
        label = "Create Character Hero"

        def __init__(self):
            self.created = type("Created", (), {
                "entity": Entity("Hero"),
                "actor": type("Actor", (), {"display_name": "Hero"})(),
            })()
            self.applied = False
            self.scene = None

        def redo(self):
            self.scene.add_entity(self.created.entity)
            self.applied = True

        def undo(self):
            self.scene.detach_entity(self.created.entity)
            self.applied = False

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    window = AsteriaEditorWindow(project)
    command = Command()
    captured = {}

    def build(bundle, actual_project, actual_scene, cell, *, display_name=None):
        command.scene = actual_scene
        captured.update(bundle=bundle, project=actual_project, scene=actual_scene,
                        cell=cell, display_name=display_name)
        return command

    monkeypatch.setattr(window.character_creator.workspace, "create_character_command", build)
    monkeypatch.setattr(window, "refresh_all", lambda: None)
    window.character_creator.cell_x_spin.setValue(4)
    window.character_creator.cell_y_spin.setValue(5)
    window.character_creator.name_edit.setText("Hero")
    try:
        window.character_creator.generated.emit("bundle")
        assert captured == {"bundle": "bundle", "project": project, "scene": scene,
                            "cell": (4, 5), "display_name": "Hero"}
        assert command.applied
        assert window.document.commands.undo_label == "Create Character Hero"
        assert window.document.selection.value is command.created.entity
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
