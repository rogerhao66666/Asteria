"""Events ▸ Common & Battle Events: the two boxes' headings sit inside their frames (the boxes
have no frame title, so no title band), and each table's last column reaches the edge after
every refresh (sizing to contents used to undo the stretch)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture(scope="module")
def page():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication, QGroupBox

    from asteria.editor import EditorDocument
    from asteria.editor.events.flow_widget import EventFlowWidget
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    app = QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    widget = EventFlowWidget(EditorDocument(project))
    widget.resize(1400, 800)
    widget.show()
    app.processEvents()
    yield widget, widget.findChildren(QGroupBox), app
    widget.close()


def test_the_boxes_have_no_title_band(page):
    _widget, boxes, _app = page
    assert len(boxes) == 2
    assert all(box.property("untitled") is True and not box.title() for box in boxes)


def test_the_last_column_reaches_the_edge_after_every_refresh(page):
    widget, _boxes, app = page
    for _ in range(3):
        widget.refresh()
        app.processEvents()
        for table in (widget.common, widget.battle):
            assert table.horizontalHeader().length() >= table.viewport().width()
