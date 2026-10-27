"""Duplicate works for every Game Systems kind: the copy is read back from the stored record's
own data (a translation's mapping, a refine rule's chance list), not through the form adapter."""

from pathlib import Path

from asteria.editor import EditorDocument
from asteria.editor.authoring_hub_widget import _free_id
from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
from asteria.project import Project

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def test_every_kind_duplicates_and_undoes():
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    document = EditorDocument(project)
    controller = GameSystemsAuthoringController(document)
    copied = 0
    for kind in controller.kinds:
        ids = controller.ids(kind.kind_id)
        if not ids or kind.kind_id == "capture_rules":  # keyed by an enemy: copied to another
            continue
        source = ids[0]
        new = _free_id(source, ids)  # rune.* -> rune_copy.*
        controller.duplicate(kind.kind_id, source, new)
        copy = controller.get(kind.kind_id, new)
        original = controller.get(kind.kind_id, source).to_data()
        same = copy.to_data()
        assert same.pop(kind.key) == new and original.pop(kind.key) == source
        assert same == original
        document.undo()
        assert new not in controller.ids(kind.kind_id)
        copied += 1
    assert copied >= 20
