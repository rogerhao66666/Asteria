"""D108: Game Systems ▸ Stats and Properties show their Usage card as a summary and rows -
what, how many, the range, a button opening the page and one showing every record - and each
record shown opens its own page."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture(scope="module")
def widget():
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    from asteria.editor import EditorDocument
    from asteria.editor.rpg.game_systems_authoring import GameSystemsAuthoringController
    from asteria.editor.rpg.game_systems_widget import GameSystemsEditorWidget
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    QApplication.instance() or QApplication([])
    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    widget = GameSystemsEditorWidget(GameSystemsAuthoringController(EditorDocument(project)))
    yield widget
    widget.deleteLater()  # gone before the next test: a language switch walks every widget
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _panel(widget, kind, key):
    from asteria.editor.rpg.usage_panel import UsagePanel

    widget.set_kind(kind)
    assert widget.show_record(kind, key)
    (panel,) = widget.findChildren(UsagePanel)
    return panel


def _buttons(panel, name):
    from PySide6.QtWidgets import QToolButton

    return [b for b in panel.findChildren(QToolButton) if b.objectName() == name]


def test_a_stat_card_has_rows_with_counts_ranges_and_buttons(widget):
    from PySide6.QtWidgets import QLabel

    panel = _panel(widget, "stat_definitions", "str")
    shown = [label.text() for label in panel.findChildren(QLabel)]
    assert any(x.startswith("Strength comes from the starting value, level ups") for x in shown)
    row = next(x for x in shown if x.startswith("Starting value of each actor"))
    assert "5 actors · 12 – 32" in row  # dimmed after the sentence: wraps when narrow
    assert len(_buttons(panel, "UsageOpen")) >= 8
    assert not _buttons(panel, "UsageRecord")  # the records are made when first shown


def test_records_show_on_demand_and_open_their_page(widget):
    panel = _panel(widget, "stat_definitions", "str")
    opened = []
    panel.opened.connect(opened.append)
    _buttons(panel, "UsageMore")[0].setChecked(True)
    records = _buttons(panel, "UsageRecord")
    assert [b.text() for b in records][:2] == ["Roger 32", "Mira 12"]
    records[1].click()
    assert opened == [("record", "rpg", "actors", "hero_02")]
    _buttons(panel, "UsageOpen")[0].click()
    assert opened[-1] == ("record", "rpg", "actors", "hero_01")


def test_a_property_card_reads_as_sentences(widget):
    from PySide6.QtWidgets import QLabel

    panel = _panel(widget, "tag_definitions", "consumable")
    shown = [label.text() for label in panel.findChildren(QLabel)]
    assert "Carried by 16 records · read by 1 record" in shown
    assert any(x.startswith("Items: has it") and "16 records" in x for x in shown)
    assert any(x.startswith("Menu pages: its tab or category holds what has it") for x in shown)
    opened = []
    panel.opened.connect(opened.append)
    _buttons(panel, "UsageOpen")[-1].click()
    assert opened == [("game_system", "menu_pages", "items")]


def test_the_usage_is_not_saved_with_the_record(widget):
    panel = _panel(widget, "stat_definitions", "speed")
    assert panel.usage.sections
    assert "usage" not in widget.form.data()


def test_a_group_has_a_row_per_member_that_opens_its_records(widget):
    from PySide6.QtWidgets import QLabel

    panel = _panel(widget, "tag_definitions", "capability.weapon.*")
    shown = [label.text() for label in panel.findChildren(QLabel)]
    assert "Can Wield is a group of 10 properties" in shown
    axe = next(x for x in shown if x.startswith("Axe · carried by: Brave"))
    assert "read by: Hand Axe" in axe
    opened = []
    panel.opened.connect(opened.append)
    _buttons(panel, "UsageMore")[0].setChecked(True)
    records = _buttons(panel, "UsageRecord")
    assert records[0].text() == "Brave (Classes)"
    records[0].click()
    assert opened == [("record", "rpg", "classes", "brave")]


def test_a_shown_card_is_replaced_again_and_again(widget):
    """A card shown on a visible window, then others: a run in the editor raised
    AttributeError where ``set_usage`` asked a layout item for its widget a second time (None
    once the widget had left the card); it asks once now."""
    from PySide6.QtWidgets import QApplication

    widget.show()
    try:
        for key in ("str", "speed", "vitality", "str"):
            panel = _panel(widget, "stat_definitions", key)
            QApplication.processEvents()
        assert panel.usage.summary[0].startswith("Strength comes from")
    finally:
        widget.hide()
