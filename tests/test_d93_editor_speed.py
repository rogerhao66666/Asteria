"""D93: opening Game Systems ▸ Tags names its hundred records without working out each one's
usage card (every card walks the whole project: four seconds before)."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


def test_the_tag_list_is_named_without_the_usage_cards(monkeypatch):
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument, tag_usage
    from asteria.editor.game_systems_authoring import GameSystemsAuthoringController
    from asteria.editor.game_systems_widget import GameSystemsEditorWidget
    from asteria.project import Project

    QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    controller = GameSystemsAuthoringController(EditorDocument(project))
    widget = GameSystemsEditorWidget(controller)
    calls = []
    original = tag_usage.tag_usage
    monkeypatch.setattr(tag_usage, "tag_usage", lambda p, t: calls.append(t) or original(p, t))
    widget.set_kind("tag_definitions")
    assert widget.browser.count() > 100
    assert len(calls) <= 1  # the shown record's card at most, not one a row
    assert controller.form_data("tag_definitions", "special", info=False)["usage"] == ""
