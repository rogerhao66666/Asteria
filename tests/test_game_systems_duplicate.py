"""Duplicate works for every Game Systems kind: the copy is read back from the stored record's
own data (a translation's mapping, a refine rule's chance list), not through the form adapter."""

from pathlib import Path

from asteria.editor import EditorDocument
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
        controller.duplicate(kind.kind_id, source, f"{source}_copy")
        copy = controller.get(kind.kind_id, f"{source}_copy")
        original = controller.get(kind.kind_id, source).to_data()
        same = copy.to_data()
        assert same.pop(kind.key) == f"{source}_copy" and original.pop(kind.key) == source
        assert same == original
        document.undo()
        assert f"{source}_copy" not in controller.ids(kind.kind_id)
        copied += 1
    assert copied >= 20
