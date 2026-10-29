"""A scene opens with its characters in the middle of the view; Reset View does the same."""

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

ROOT = Path(__file__).resolve().parents[1] / "reference_projects" / "party_rpg_demo"


def _centre_of_entities(viewport):
    from asteria.core import Transform, world_position

    scene = viewport.current_scene()
    points = [world_position(e) for e in scene.entities() if e.try_get(Transform) is not None]
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return viewport.camera.world_to_screen(cx, cy)


def test_opening_a_project_centres_its_entities_and_reset_view_does_too():
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    window = AsteriaEditorWindow()
    try:
        window.resize(1400, 900)
        window.show()
        project = Project.load_json(
            ROOT / "project.asteria.json", window.document.component_registry
        )
        from asteria.runtime.components2d import Camera2DComponent

        for scene in project.scenes():  # a scene with no game camera frames its entities
            for entity in list(scene.entities()):
                if entity.try_get(Camera2DComponent) is not None:
                    scene.remove_entity(entity)
        window.set_project(project)
        for _ in range(30):
            app.processEvents()
        viewport = window.viewport
        x, y = _centre_of_entities(viewport)
        assert abs(x - viewport.width() / 2) <= 2 and abs(y - viewport.height() / 2) <= 2
        # the view follows a window resize while nobody has panned
        window.resize(1100, 700)
        for _ in range(30):
            app.processEvents()
        x, y = _centre_of_entities(viewport)
        assert abs(x - viewport.width() / 2) <= 2 and abs(y - viewport.height() / 2) <= 2
        # after the user pans, Reset View brings it back to the middle
        viewport.pan_view(300, -120)
        x, y = _centre_of_entities(viewport)
        assert abs(x - viewport.width() / 2) > 50
        viewport.reset_view()
        x, y = _centre_of_entities(viewport)
        assert abs(x - viewport.width() / 2) <= 2 and abs(y - viewport.height() / 2) <= 2
        # a panned view is left alone by a resize
        viewport.pan_view(200, 0)
        before = (viewport.camera.pan_x, viewport.camera.pan_y)
        window.resize(1200, 760)
        for _ in range(30):
            app.processEvents()
        assert (viewport.camera.pan_x, viewport.camera.pan_y) == before
    finally:
        window.document.mark_saved()
        window.close()
        app.processEvents()
