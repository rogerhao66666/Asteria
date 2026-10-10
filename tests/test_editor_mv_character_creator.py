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


@pytest.mark.mv_reference
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


@pytest.mark.mv_reference
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


@pytest.mark.mv_reference
def test_mv_workspace_family_switch_clears_incompatible_parts_and_palette():
    workspace = _workspace()
    workspace.set_body_family("Male")
    male_hair = next(part for part in workspace.choices("hair_front", gender="Male") if part.source_root == workspace._part(workspace.recipe.parts["body"]).source_root)
    workspace.select("hair_front", male_hair.id)
    workspace.recipe.palette["hair_front"] = "#ffaa00"

    cleared = workspace.set_body_family("Kid")

    assert workspace.recipe.body_family == "Kid"
    assert "hair_front" in cleared
    assert "hair_front" not in workspace.recipe.parts
    assert "hair_front" not in workspace.recipe.palette
    assert workspace._part(workspace.recipe.parts["body"]).gender == "Kid"
    assert all(part.gender == "Kid" for part in workspace.choices("hair_front"))


@pytest.mark.mv_reference
def test_mv_workspace_reloads_saved_recipe_for_editing(tmp_path):
    workspace = _workspace()
    workspace.set_body_family("Female")
    hair = workspace.choices("hair_front")[0]
    workspace.select("hair_front", hair.id)
    bundle = workspace.generate(tmp_path)

    reopened = _workspace()
    reopened.load_bundle(bundle.metadata_path)

    assert reopened.recipe.body_family == "Female"
    assert reopened.recipe.parts == workspace.recipe.parts
    assert reopened.preview_representation("damaged").size == (144, 48)


@pytest.mark.mv_reference
def test_mv_widget_exposes_all_four_full_sheet_previews_and_kid_family():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.character_generator_widget import CharacterGeneratorWidget

    app = QApplication.instance() or QApplication([])
    widget = CharacterGeneratorWidget(_workspace())
    try:
        assert widget.part_grid.objectName() == "CharacterPartGrid"
        assert [widget.preview_tabs.tabText(i) for i in range(widget.preview_tabs.count())] == [
            "Walking", "Face", "Damaged", "Side View"
        ]
        assert [widget.gender_combo.itemText(i) for i in range(widget.gender_combo.count())] == ["Male", "Female", "Kid"]
        assert widget.walking_canvas.minimumWidth() >= 144
        assert widget.walking_canvas.pixmap().size().width() >= 144
        assert widget.damaged_canvas.pixmap().size().height() >= 48
        assert widget.ground_line_visible is True
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.mv_reference
def test_mv_widget_recomposes_hair_and_clothing_without_changing_body():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.character_generator_widget import CharacterGeneratorWidget

    app = QApplication.instance() or QApplication([])
    widget = CharacterGeneratorWidget(_workspace())
    try:
        body_id = widget.workspace.recipe.parts["body"]
        widget.category_combo.setCurrentText("hair_front")
        first, second = widget.workspace.choices("hair_front")[:2]
        widget.workspace.select("hair_front", first.id)
        before = widget.workspace.preview_representation("side_view").tobytes()
        widget.workspace.select("hair_front", second.id)
        widget.refresh_preview()
        after = widget.workspace.preview_representation("side_view").tobytes()
        assert before != after
        assert widget.workspace.recipe.parts["body"] == body_id
        widget.gender_combo.setCurrentText("Kid")
        assert widget.workspace.recipe.body_family == "Kid"
        assert "hair_front" not in widget.workspace.recipe.parts
        assert widget.damaged_canvas.pixmap().height() == 96
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.mv_reference
def test_mv_widget_can_inspect_every_side_view_and_damaged_frame():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication
    from asteria.editor.character_generator_widget import CharacterGeneratorWidget

    app = QApplication.instance() or QApplication([])
    widget = CharacterGeneratorWidget(_workspace())
    try:
        widget.frame_rep_combo.setCurrentText("Side View")
        assert widget.frame_spin.maximum() == 53
        widget.frame_spin.setValue(53)
        assert widget.frame_canvas.pixmap().width() >= 64
        widget.frame_rep_combo.setCurrentText("Damaged")
        assert widget.frame_spin.maximum() == 2
        assert "144×48" in widget.sheet_info.text()
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.mv_reference
def test_mv_widget_loads_saved_recipe_back_into_editable_controls(tmp_path, monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QFileDialog
    from asteria.editor.character_generator_widget import CharacterGeneratorWidget

    saved = _workspace()
    saved.set_body_family("Female")
    hair = saved.choices("hair_front")[0]
    saved.select("hair_front", hair.id)
    bundle = saved.generate(tmp_path)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args, **kwargs: (str(bundle.metadata_path), ""))

    app = QApplication.instance() or QApplication([])
    widget = CharacterGeneratorWidget(_workspace())
    try:
        widget.load_recipe_button.click()
        assert widget.gender_combo.currentText() == "Female"
        assert widget.workspace.recipe.parts["hair_front"] == hair.id
        assert widget.side_view_canvas.pixmap() is not None
    finally:
        widget.close()
        app.processEvents()


@pytest.mark.mv_reference
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
        assert labels == ["Database", "Character Creator", "Game Systems"]
        assert window.character_creator.part_grid.objectName() == "CharacterPartGrid"
        assert not hasattr(window.character_creator, "starter_pack_combo")
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()


def test_editor_shell_generated_bundle_enters_map_placement_mode(monkeypatch):
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
    monkeypatch.setattr(window.character_creator.workspace, "create_character_command", lambda *args, **kwargs: command)
    monkeypatch.setattr(window, "refresh_all", lambda: None)
    window.character_creator.name_edit.setText("Hero")
    try:
        window.character_creator.generated.emit("bundle")
        assert window._pending_character_bundle == "bundle"
        assert window.viewport.character_placement_active
        assert "Click a map cell" in window.character_creator.status.text()
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()


def test_editor_shell_places_pending_generated_bundle_at_clicked_map_cell(monkeypatch):
    pytest.importorskip("PySide6")
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
    from asteria.core import Entity, Scene
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.editor.workspace import WorkspaceMode
    from asteria.project import Project

    class Command:
        label = "Create Character Click Hero"

        def __init__(self):
            self.created = type("Created", (), {
                "entity": Entity("Click Hero"),
                "actor": type("Actor", (), {"display_name": "Click Hero"})(),
            })()
            self.scene = None

        def redo(self): self.scene.add_entity(self.created.entity)
        def undo(self): self.scene.detach_entity(self.created.entity)

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Map"))
    window = AsteriaEditorWindow(project)
    command, captured = Command(), {}

    def build(bundle, actual_project, actual_scene, cell, *, display_name=None):
        command.scene = actual_scene
        captured.update(bundle=bundle, project=actual_project, scene=actual_scene,
                        cell=cell, display_name=display_name)
        return command

    monkeypatch.setattr(window.character_creator.workspace, "create_character_command", build)
    monkeypatch.setattr(window, "refresh_all", lambda: None)
    window.character_creator.name_edit.setText("Click Hero")
    try:
        window.begin_character_placement("bundle")
        assert window.workspace.mode is WorkspaceMode.SCENE
        assert window.viewport.character_placement_active

        window.viewport.resize(480, 360)
        window.viewport.show()
        app.processEvents()
        QTest.mouseClick(window.viewport, Qt.LeftButton, pos=QPoint(4 * 48 + 12, 5 * 48 + 12))

        assert captured == {"bundle": "bundle", "project": project, "scene": scene,
                            "cell": (4, 5), "display_name": "Click Hero"}
        assert window.document.commands.undo_label == "Create Character Click Hero"
        assert not window.viewport.character_placement_active
        assert "Created Click Hero at map cell 4, 5" in window.character_creator.status.text()
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
