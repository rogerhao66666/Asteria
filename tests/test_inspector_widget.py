import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QCheckBox, QComboBox

from asteria.core import ComponentRegistry, Entity, Scene
from asteria.core.metadata import Field, component_schema
from asteria.core import Component
from asteria.editor.inspector import build_inspector_fields
from asteria.editor.model import EditorDocument
from asteria.editor.widgets import InspectorWidget
from asteria.runtime import SpriteRenderer2D

_app = QApplication.instance() or QApplication([])


@component_schema(
    fields=(
        Field("mode", str, "idle", choices=("idle", "walk", "run")),
    )
)
class _ChoiceComponent(Component):
    def __init__(self):
        super().__init__()
        self.mode = "walk"


def _document_with_component(component):
    registry = ComponentRegistry()
    registry.register(SpriteRenderer2D)
    registry.register(_ChoiceComponent)
    document = EditorDocument(component_registry=registry)
    from asteria.project import Project

    project = Project("P")
    scene = Scene("S")
    entity = scene.add_entity(Entity("E"))
    entity.add_component(component)
    project.add_scene(scene)
    document.set_project(project)
    document.selection.set_single("component", component)
    return document


def test_bool_field_renders_as_a_checkbox_matching_its_value():
    sprite = SpriteRenderer2D()
    sprite.flip_x = True
    document = _document_with_component(sprite)
    inspector = InspectorWidget(document)

    fields = build_inspector_fields(sprite)
    inspector.show_component("SpriteRenderer2D", fields)

    flip_row = next(i for i, f in enumerate(fields) if f.name == "flip_x")
    cell = inspector.table.cellWidget(flip_row, 1)
    checkbox = cell.findChild(QCheckBox)
    assert checkbox is not None
    assert checkbox.isChecked() is True


def test_toggling_the_checkbox_edits_the_component_through_the_window():
    sprite = SpriteRenderer2D()
    sprite.flip_x = False
    document = _document_with_component(sprite)
    inspector = InspectorWidget(document)
    calls = []
    inspector.edit_selected_component_field = lambda name, value: (
        calls.append((name, value)) or (True, None)
    )

    fields = build_inspector_fields(sprite)
    inspector.show_component("SpriteRenderer2D", fields)
    flip_row = next(i for i, f in enumerate(fields) if f.name == "flip_x")
    checkbox = inspector.table.cellWidget(flip_row, 1).findChild(QCheckBox)

    checkbox.setChecked(True)

    assert calls == [("flip_x", True)]


def test_choice_field_renders_as_a_combo_box_with_current_value_selected():
    component = _ChoiceComponent()
    document = _document_with_component(component)
    inspector = InspectorWidget(document)

    fields = build_inspector_fields(component)
    inspector.show_component("_ChoiceComponent", fields)

    mode_row = next(i for i, f in enumerate(fields) if f.name == "mode")
    combo = inspector.table.cellWidget(mode_row, 1)
    assert isinstance(combo, QComboBox)
    assert combo.currentData() == "walk"


def test_switching_from_a_checkbox_row_to_a_plain_value_removes_the_old_widget():
    sprite = SpriteRenderer2D()
    document = _document_with_component(sprite)
    inspector = InspectorWidget(document)
    fields = build_inspector_fields(sprite)
    inspector.show_component("SpriteRenderer2D", fields)

    # A row that held a checkbox widget now gets a plain properties row;
    # the stale checkbox must not linger on top of the new QTableWidgetItem.
    inspector.show_properties("Entity", (("Name", "E", "str"),))

    assert inspector.table.cellWidget(0, 1) is None
