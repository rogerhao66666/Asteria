"""UI_PLAN_2 V1: every picture an author can set has a picker with a file chooser in the
editor - never a bare text box for a path. A new picture field added without one fails here.

Three guards: the game-systems forms (each field's kind), the keys that hold pictures in the
bundled projects (the generic record editors make them pickers), and the layout inspector."""

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXT = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp")
# names that suggest a picture; the kinds below are not a path (sizes, styles, groups)
LOOKS_LIKE = re.compile(r"image|icon|portrait|picture|sprite|background|banner|cursor|sheet")
NOT_A_PATH = {"id", "int", "float", "bool", "choice", "group", "table", "optional_int", "amounts"}
# keys that hold pictures but are edited elsewhere, each with its own chooser
ELSEWHERE = {
    "uri": "an imported asset's file (Assets panel ▸ Import)",
    "source_path": "an imported asset's file (Assets panel ▸ Import)",
    "asset_id": "a nine-patch frame's picture (layout inspector ▸ Frame, Choose… / Library…)",
    "backdrop": "a doll place's back picture (layout inspector ▸ Doll places, Choose picture…)",
    "placeholder": "a doll place's empty picture (layout inspector ▸ Doll places, as above)",
}


def _form_fields(fields, path=()):
    for f in fields:
        yield path + (f.key,), f
        yield from _form_fields(f.fields, path + (f.key,))


def test_every_picture_field_of_the_game_systems_forms_is_a_picker():
    from asteria.editor.game_systems_authoring import FORMS
    from asteria.editor.game_systems_widget import _TEXT_SOURCES

    wrong = []
    for kind_id, fields in FORMS.items():
        for path, f in _form_fields(fields):
            if not LOOKS_LIKE.search(f.key) or f.kind in NOT_A_PATH:
                continue
            asset_list = _TEXT_SOURCES.get(f.key, "").startswith("assets:")
            if f.kind != "icon" and not asset_list:
                wrong.append(f"{kind_id}.{'.'.join(path)} ({f.kind})")
    assert wrong == []


def _picture_keys(data, out, path=()):
    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, str) and value.lower().endswith(EXT):
                out.setdefault(key, path + (key,))
            _picture_keys(value, out, path + (key,))
    elif isinstance(data, list):
        for value in data:
            _picture_keys(value, out, path)
    return out


def test_every_key_holding_a_picture_in_the_bundled_projects_gets_a_picker():
    from asteria.editor.image_tools import picture_field

    found = {}
    for path in sorted((REPO / "reference_projects").glob("*/project.asteria.json")):
        _picture_keys(json.loads(path.read_text(encoding="utf-8")), found)
    assert "icon_id" in found and "card_image" in found  # the scan sees real data
    missing = {
        key: "/".join(map(str, where[-4:]))
        for key, where in found.items()
        if key not in ELSEWHERE and not picture_field(key)
    }
    assert missing == {}


@pytest.fixture
def document(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from asteria.editor import EditorDocument
    from asteria.project import Project

    document = EditorDocument()
    project = Project.load_json(
        REPO / "reference_projects" / "full_verification_demo" / "project.asteria.json",
        document.component_registry,
    )
    document.set_project(project, file_path=tmp_path / "project.asteria.json")
    return document


def test_the_record_tree_makes_every_picture_key_a_picker_with_browse(document):
    from asteria.editor.authoring_hub_widget import StructuredRecordEditor
    from asteria.editor.game_systems_widget import _IconPicker
    from asteria.editor.image_tools import IconLibrary

    editor = StructuredRecordEditor()
    editor.icon_library = IconLibrary(document)
    record = {"name": "x", "icon_id": "", "card_image": "a.png", "sprite": "", "portrait": ""}
    editor.set_record(record)
    pickers = {}
    for n in range(editor.topLevelItem(0).childCount()):
        item = editor.topLevelItem(0).child(n)
        widget = editor.itemWidget(item, 1)
        if isinstance(widget, _IconPicker):
            pickers[item.data(0, 0x0100)[-1]] = widget
    assert set(pickers) == {"icon_id", "card_image", "sprite", "portrait"}
    assert all(p.browse.text() == "Browse…" for p in pickers.values())


def test_the_layout_inspector_chooses_every_picture_from_a_file(document):
    from asteria.editor.menu_layout_widget import AssetField, ElementInspector, PatchField

    inspector = ElementInspector(document)
    assert isinstance(inspector.image, AssetField) and inspector.image.kind == "image"
    for name in ("skin", "selection_skin"):
        assert isinstance(getattr(inspector, name), PatchField)
    from PySide6.QtWidgets import QToolButton

    words = {b.text() for b in inspector.image.findChildren(QToolButton)}
    assert {"Choose…", "Library…"} <= words


def test_a_doll_place_picture_is_chosen_not_typed(document):
    from asteria.editor.menu_layout_widget import SlotsField

    field = SlotsField(document)
    field._add()
    picture = REPO / "reference_projects" / "full_verification_demo" / "playable_assets"
    picture = picture / "lucifer" / "ui" / "slot_cell.png"
    field.choose_picture(0, 10, str(picture))
    assert field.places()[0].backdrop.endswith("slot_cell.png")
    assert not Path(field.places()[0].backdrop).is_absolute()  # a path in the project
