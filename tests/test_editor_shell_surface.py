def test_shell_class_has_core_file_and_play_actions_as_methods():
    from asteria.editor.shell import AsteriaEditorWindow

    for name in (
        "add_scene",
        "delete_scene",
        "add_entity",
        "add_component",
        "delete_selected",
        "save_project",
        "save_project_as",
        "open_project",
        "play_current_scene",
        "stop_play",
        "show_controls",
        "show_about",
    ):
        assert callable(getattr(AsteriaEditorWindow, name, None)), name
    assert callable(getattr(AsteriaEditorWindow, "_poll_runtime_process", None))


def test_project_tree_has_selection_callback_used_during_construction():
    from asteria.editor.widgets import ProjectTreeWidget

    assert callable(getattr(ProjectTreeWidget, "_on_selection_changed", None))


def test_project_tree_refresh_preserves_canonical_selection():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene
    from asteria.editor.model import EditorDocument
    from asteria.editor.widgets import ProjectTreeWidget
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Town"))
    hero = scene.add_entity(Entity("Hero"))
    document = EditorDocument(project)
    document.select_entity(hero)

    widget = ProjectTreeWidget(document)
    widget.refresh()

    assert document.selection.kind == "entity"
    assert document.selection.value is hero
    payload = widget.tree.selectedItems()[0].data(0, Qt.UserRole)
    assert payload == ("entity", hero)
    widget.close()
    app.processEvents()


def test_scene_viewport_arrow_navigation_and_reset():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene, Transform
    from asteria.editor.model import EditorDocument
    from asteria.editor.viewport_widget import SceneViewportWidget
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Town"))
    entity = scene.add_entity(Entity("Camera"))
    transform = entity.add_component(Transform())
    document = EditorDocument(project)
    viewport = SceneViewportWidget(document)

    app.sendEvent(
        viewport,
        QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier),
    )
    assert viewport.camera.pan_x == -24

    document.select_entity(entity)
    app.sendEvent(
        viewport,
        QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier),
    )
    assert transform.x == 1
    assert viewport.camera.pan_x == -24
    assert document.dirty

    viewport.camera.zoom = 2

    viewport.reset_view()
    # No Camera2DComponent exists to frame, so reset_view() falls back to
    # centering every positioned entity at the default 1x zoom, instead of
    # pinning world (0, 0) at the screen's top-left corner. The lone entity
    # sits at world (1, 0) here (after the move above), so it lands at the
    # center of the (unshown, default-sized 640x480) viewport.
    assert (
        viewport.camera.pan_x,
        viewport.camera.pan_y,
        viewport.camera.zoom,
    ) == (319.0, 240.0, 1.0)
    viewport.close()


def test_scene_viewport_frames_active_camera_at_the_center():
    import pytest

    pytest.importorskip("PySide6")
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication

    from asteria.core import Entity, Scene, Transform
    from asteria.editor.model import EditorDocument
    from asteria.editor.viewport_widget import SceneViewportWidget
    from asteria.project import Project
    from asteria.runtime import Camera2DComponent

    app = QApplication.instance() or QApplication([])
    project = Project("Game")
    scene = project.add_scene(Scene("Town"))
    hero = scene.add_entity(Entity("Hero"))
    hero.add_component(Transform(300, 200))
    entity = scene.add_entity(Entity("Camera"))
    entity.add_component(Transform(100, 50))
    spec = entity.add_component(Camera2DComponent())
    spec.width = 480
    spec.height = 270
    spec.follow_entity_id = hero.id
    document = EditorDocument(project)
    viewport = SceneViewportWidget(document)
    viewport.resize(1000, 600)

    assert viewport.frame_game_camera()
    center = viewport.camera.world_to_screen(300, 200)
    assert center == (500, 300)
    camera_marker = next(
        marker for marker in viewport.markers() if marker.entity is entity
    )
    assert (camera_marker.world_x, camera_marker.world_y) == (60, 65)

    document.select_entity(entity)
    app.sendEvent(
        viewport,
        QKeyEvent(QEvent.KeyPress, Qt.Key_Right, Qt.NoModifier),
    )
    assert spec.follow_entity_id == ""
    transform = entity.get(Transform)
    assert (transform.x, transform.y) == (61, 65)
    document.undo()
    assert spec.follow_entity_id == hero.id
    viewport.close()


def test_runtime_monitor_cleans_up_an_exited_preview():
    from asteria.editor.shell import AsteriaEditorWindow

    class Process:
        running = False
        stopped = False

        def stop(self):
            self.stopped = True

    class Session:
        active = True

        def stop(self):
            self.active = False

    class Label:
        def setText(self, text):
            self.text = text

    class Status:
        def showMessage(self, text, timeout):
            self.message = (text, timeout)

    class Window:
        runtime_process = Process()
        play_session = Session()
        console = Label()
        refreshed = False

        def statusBar(self):
            return Status()

        def _refresh_actions(self):
            self.refreshed = True

    window = Window()
    AsteriaEditorWindow._poll_runtime_process(window)
    assert window.runtime_process is None
    assert not window.play_session.active
    assert window.console.text == "Runtime preview closed"
    assert window.refreshed
