"""The asset library: CC0 packs beside the engine, imported picture by picture into a project."""

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from asteria.assets.library import (  # noqa: E402
    default_library_root,
    import_into_project,
    library_packs,
    pack_images,
)


def _pack(name_part):
    return next(p for p in library_packs() if name_part in p.pack_id)


def test_the_library_holds_the_cc0_pixel_packs():
    packs = library_packs()
    assert default_library_root().name == "asset_library"
    assert len(packs) >= 30
    equipment = _pack("Lucifer_Equipment")
    assert equipment.name == "Lucifer Equipment Pixel Art"
    assert "Equipment/Weapons/Png/Mythic Battleaxe.png" in pack_images(equipment)
    for pack in packs:  # only packs whose readme grants CC0 may live in the repo
        text = pack.license_text.lower()
        assert "cc0" in text or "creative commons zero" in text, pack.pack_id


def test_importing_copies_into_the_project_once(tmp_path):
    from asteria.editor import EditorDocument
    from asteria.project import Project

    project = Project("P")
    pack = _pack("Lucifer_Equipment")
    relative = "Equipment/Weapons/Png/Rare Greatsword.png"
    record = import_into_project(project, tmp_path, pack, relative)
    assert (tmp_path / record.source_path).is_file()
    assert record.source_path.startswith("playable_assets/library/")
    assert record.metadata["license"] == "CC0 1.0"
    assert import_into_project(project, tmp_path, pack, relative) is record  # once
    assert EditorDocument  # the editor module imports


def test_the_editor_imports_through_the_dialog_and_undoes(tmp_path):
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    from asteria.editor.shell import AsteriaEditorWindow
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    project = Project("P")
    window = AsteriaEditorWindow(project)
    window.document.file_path = tmp_path / "project.asteria.json"

    def choose(dialog):
        dialog.pack_list.setCurrentRow(
            next(i for i, p in enumerate(dialog.packs) if "Lucifer_Equipment" in p.pack_id)
        )
        dialog.select(["Equipment/Weapons/Png/Mythic Battleaxe.png"])
        return True

    (record,) = window.import_from_asset_library(dialog_hook=choose)
    assert record in project.assets.records()
    window.document.commands.undo()
    assert record not in project.assets.records()
    window.document.commands.redo()
    assert record in project.assets.records()
    window.document.mark_saved()  # closing would ask to save the import
    window.close()
