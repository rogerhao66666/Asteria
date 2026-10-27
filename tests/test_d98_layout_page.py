"""D98: Presentation ▸ Menu Screens ▸ Layout, laid out again.

The screen is shown as the game draws it: an element's outline shows only while the pointer
is over it or it is chosen (or with Show All Outlines). With nothing chosen the right side
lists the elements to choose from. A screen with a layout of its own reads "(changed)". The
Status screen links to Game Systems ▸ Pause Menu, where its pages' blocks are set.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def _page(monkeypatch, **links):
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.menu_layout_widget import MenuLayoutWorkspace
    from asteria.editor.storage import load_document

    QApplication.instance() or QApplication([])
    document = EditorDocument()
    load_document(document, str(DEMO / "project.asteria.json"))
    page = MenuLayoutWorkspace(document, **links)
    return document, page


def _pen(box):
    pen = box.pen()
    return Qt.NoPen if pen.style() == Qt.NoPen else pen.style()


def test_outlines_show_on_hover_or_choice_or_all(monkeypatch):
    _document, page = _page(monkeypatch)
    try:
        page.screen_id = "pause"
        page.show()
        page.rebuild()
        boxes = page.canvas.boxes
        assert boxes and all(_pen(b) == Qt.NoPen for b in boxes.values())  # as the game draws
        assert page.side.currentWidget() is page.chooser  # nothing chosen: the elements
        assert page.chooser_list.count() > 0
        page.pick("frame")
        assert _pen(boxes["frame"]) == Qt.SolidLine
        assert all(_pen(b) == Qt.NoPen for k, b in boxes.items() if k != "frame")
        assert page.side.currentWidget() is page.inspector
        assert page.element_combo.currentData() == "frame"
        options = boxes["options"]
        options.hovered = True
        options.restyle()
        assert _pen(options) == Qt.DashLine and options.name  # its name on a tab
        options.hovered = False
        page.outlines.setChecked(True)
        assert all(_pen(b) != Qt.NoPen for b in boxes.values())
        page.outlines.setChecked(False)
        assert _pen(options) == Qt.NoPen
        assert isinstance(boxes["frame"].pen(), QPen)
    finally:
        page.close()


def test_a_changed_screen_says_so_and_the_buttons_are_words(monkeypatch):
    _document, page = _page(monkeypatch)
    try:
        page.show()
        page.rebuild()
        texts = [page.screen_list.item(i).text() for i in range(page.screen_list.count())]
        assert any(t.endswith("(changed)") for t in texts)  # the demo's pause and doll
        assert not any("●" in t for t in texts)
        assert page.add_button.text() == "Add Element" and page.add_button.menu() is not None
    finally:
        page.close()


def test_the_status_screen_links_to_the_pause_menu(monkeypatch):
    opened = []
    _document, page = _page(monkeypatch, open_pause_menu=opened.append)
    try:
        page.show()
        page.rebuild()
        assert page.show_screen("status")
        assert page.pages_link.isVisible()
        page.pages_link.click()
        assert opened == ["status"]
        page.show_screen("pause")
        assert not page.pages_link.isVisible()
    finally:
        page.close()


def test_a_pause_menu_page_links_to_its_layout(monkeypatch):
    monkeypatch.setenv("ASTERIA_MUTE", "1")
    from PySide6.QtWidgets import QApplication, QPushButton

    from asteria.editor import EditorDocument
    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    path = DEMO / "project.asteria.json"
    window = AsteriaEditorWindow(Project.load_json(path, EditorDocument().component_registry))
    try:
        window.document.file_path = path.resolve()
        window.open_pause_menu("status")
        pause = window.game_systems_editor.pause
        assert pause.selected == "status"
        link = next(
            b
            for b in pause.scroll.widget().findChildren(QPushButton)
            if b.text() == "Move It on the Screen (Layout)"
        )
        link.click()
        assert window.ui_workspace.currentWidget() is window.menu_layout_editor
        assert window.menu_layout_editor.screen_id == "status"
    finally:
        window.close()
