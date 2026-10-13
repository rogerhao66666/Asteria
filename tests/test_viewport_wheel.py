"""Scene view: a mouse wheel zooms around the cursor, a trackpad keeps scrolling the view."""

import pytest

pytest.importorskip("PySide6")


def _wheel(widget, *, pixel=(0, 0), angle=(0, 120), phase=None, at=(300.0, 200.0)):
    from PySide6.QtCore import QPoint, QPointF, Qt
    from PySide6.QtGui import QWheelEvent

    return QWheelEvent(
        QPointF(*at),
        QPointF(*at),
        QPoint(*pixel),
        QPoint(*angle),
        Qt.NoButton,
        Qt.NoModifier,
        phase if phase is not None else Qt.NoScrollPhase,
        False,
    )


@pytest.fixture
def view():
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.viewport_widget import SceneViewportWidget
    from asteria.project import Project

    app = QApplication.instance() or QApplication([])
    document = EditorDocument()
    document.set_project(Project("Wheel"))
    widget = SceneViewportWidget(document)
    widget.resize(800, 600)
    yield widget
    widget.close()
    app.processEvents()


def test_a_mouse_wheel_zooms_around_the_cursor_and_does_not_pan(view):
    camera = view.camera
    at = (300.0, 200.0)
    world_before = camera.screen_to_world(*at)
    zoom = camera.zoom
    view.wheelEvent(_wheel(view, angle=(0, 120), at=at))
    assert camera.zoom == pytest.approx(zoom * view.WHEEL_ZOOM_STEP)
    after = camera.screen_to_world(*at)
    assert after == pytest.approx(world_before)  # the point under the cursor stays put
    view.wheelEvent(_wheel(view, angle=(0, -240), at=at))
    assert camera.zoom == pytest.approx(zoom / view.WHEEL_ZOOM_STEP)


def test_a_trackpad_scroll_still_pans(view):
    from PySide6.QtCore import Qt

    camera = view.camera
    zoom, pan = camera.zoom, (camera.pan_x, camera.pan_y)
    view.wheelEvent(_wheel(view, pixel=(0, 30), angle=(0, 30), phase=Qt.ScrollUpdate))
    assert camera.zoom == zoom
    assert (camera.pan_x, camera.pan_y) == (pan[0], pan[1] + 30)
