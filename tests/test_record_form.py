"""The record form: fields get the widget their data asks for, edits apply on their own
(undoable), a bad value is shown and not applied."""

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
pytest.importorskip("PySide6")

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture(scope="module")
def app():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


def _family(category, key):
    from asteria.editor import EditorDocument
    from asteria.editor.authoring_hub_widget import AdapterFamilyWidget
    from asteria.editor.integrated_authoring import IntegratedAuthoringControllers
    from asteria.project import Project

    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    document = EditorDocument(project)
    document.file_path = DEMO / "project.asteria.json"
    controllers = IntegratedAuthoringControllers(document)
    family = AdapterFamilyWidget("Game Data", controllers.rpg_categories(), document=document)
    family.category.setCurrentIndex(family.category.findData(category))
    family.select_ids([key])
    return project, document, family


def test_fields_get_friendly_widgets(app):
    from asteria.editor.record_form import AmountTable, ChipList, NumberBox, Picker

    _project, _document, family = _family("actors", "hero_01")
    form = family.editor
    stats = [t for t in form.findChildren(AmountTable) if "str" in t.values]
    assert stats and stats[0].values["str"] == 21  # the base stats, as a table of numbers
    chips = [c for c in form.findChildren(ChipList) if "trait.cover" in c.values]
    assert chips  # tags as chips
    pickers = [p for p in form.findChildren(Picker) if p.value() == "brave"]
    assert pickers  # the job is picked from the jobs, not typed
    assert form.findChildren(NumberBox)
    assert "Roger" in family.browser.item(family._ids.index("hero_01")).text()  # names listed


def test_an_edit_applies_on_its_own_and_undoes(app):
    from asteria.editor.record_form import AmountTable

    project, document, family = _family("actors", "hero_01")
    (table,) = [t for t in family.editor.findChildren(AmountTable) if "str" in t.values]
    table._set("str", 20)
    family.auto_apply()  # what the timer does a moment after typing stops
    assert project.rpg_database.actors["hero_01"].base_stats["str"] == 20
    document.undo()
    assert project.rpg_database.actors["hero_01"].base_stats["str"] == 21


def test_a_bad_value_is_shown_and_not_applied(app):
    project, _document, family = _family("classes", "brave")
    form = family.editor
    form._data["unlock_level"] = -3  # a job cannot unlock below level 0
    assert not family.auto_apply()
    assert form.error.isVisibleTo(form) and "Not applied" in form.error.text()
    assert project.rpg_database.classes["brave"].unlock_level == 0


def test_a_skill_tree_opens_as_its_graph_without_building_the_form(app):
    """The graph shows first; the form (thousands of fields for a 50-node tree) waits, unbuilt,
    yet holds the record; long lists open one entry at a time; icon pickers fill on demand."""
    from PySide6.QtWidgets import QToolButton

    from asteria.editor.record_form import CardList, NumberBox

    _project, _document, family = _family("graphs", "archmage_tree")
    assert family.detail_stack.currentWidget() is family.graph_view
    form = family.editor
    assert form._unbuilt and not form.findChildren(NumberBox)  # nothing built behind the graph
    assert form.record()["graph_id"] == "archmage_tree"  # the record is there all the same
    family.show()  # the page on screen, still on the graph
    app.processEvents()
    assert form._unbuilt
    family.toggle_skill_tree_view()  # the form shown: built now
    app.processEvents()
    assert not form._unbuilt
    nodes = next(c for c in form.findChildren(CardList) if c.key == "nodes")
    assert nodes.folded and len(nodes.entries) > 8
    arrows = [b for b in nodes.findChildren(QToolButton) if b.text() == "▸"]
    assert len(arrows) == len(nodes.entries)  # every node closed: title lines only
    before = len(nodes.findChildren(NumberBox))
    arrows[0].click()  # opening a node builds its fields
    assert len(nodes.findChildren(NumberBox)) > before
    family.close()


def test_an_icon_picker_fills_its_list_when_opened(app):
    from asteria.editor.game_systems_widget import _IconPicker

    _project, _document, family = _family("items", "ether_leaf")
    (picker,) = family.editor.findChildren(_IconPicker)
    assert picker.combo.count() <= 2  # "(none)" and the item's own icon
    assert picker.text() == "icon.ether_leaf"
    assert not picker.combo.itemIcon(picker.combo.currentIndex()).isNull()  # with its picture
    assert picker.combo.findData("forged:fire") > 0  # a search fills the whole list
    assert picker.text() == "icon.ether_leaf"  # and keeps the choice


def test_help_shows_on_hover_only(app):
    from PySide6.QtWidgets import QLabel

    from asteria.editor.record_vocabulary import CATEGORY_HELP, HELP

    _project, _document, family = _family("abilities", "add_mend")
    form = family.editor
    texts = [label.text() for label in form.findChildren(QLabel)]
    assert HELP["description"] not in texts  # not printed under the field any more
    assert CATEGORY_HELP["abilities"] not in texts  # nor beside the section's title
    (title,) = [lb for lb in form.findChildren(QLabel) if lb.text() == "Description  ⓘ"]
    assert title.toolTip().startswith(HELP["description"])  # on hover instead
    marks = [lb for lb in form.findChildren(QLabel) if lb.objectName() == "FormSectionHelp"]
    assert any(m.toolTip() == CATEGORY_HELP["abilities"] for m in marks)


def test_a_help_tooltip_opens_right_beside_its_mark(app):
    """D95: every ⓘ opens its help in one place - just right of the mark, level with the label,
    see-through - wherever the mouse came in (D93 put it left of the label's words), and the
    help goes when the mouse leaves."""
    from PySide6.QtCore import QEvent, QPoint, Qt
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QLabel

    from asteria.editor.decor import HELP_GAP, HELP_MIN_WIDTH, _mark_span, help_box, install

    install(app)
    _project, _document, family = _family("actors", "hero_01")
    family.resize(1400, 700)  # on the 800-high test screen: a mark scrolled to is on it
    family.move(500, 50)
    family.show()
    (title,) = [lb for lb in family.editor.findChildren(QLabel) if lb.text() == "Base Stats  ⓘ"]
    marks = [lb for lb in family.editor.findChildren(QLabel) if lb.text() == "ⓘ"]
    box = help_box()
    for label in (title, marks[0]):
        family.editor.ensureWidgetVisible(label)  # on the screen (charts push it down)
        app.processEvents()
        for inside in (QPoint(2, 2), QPoint(label.width() - 2, label.height() - 2)):
            event = QHelpEvent(QEvent.ToolTip, inside, label.mapToGlobal(inside))
            assert app.sendEvent(label, event)
            assert box.isVisible() and box.text() == label.toolTip()
            mark = label.mapToGlobal(QPoint(_mark_span(label)[1], 0))  # the ⓘ's right edge
            room = label.screen().availableGeometry().right() - (mark.x() + HELP_GAP)
            if room >= HELP_MIN_WIDTH:
                assert box.x() == mark.x() + HELP_GAP  # just right of the mark
            else:  # the mark is against the screen's edge: just left of it instead
                left = label.mapToGlobal(QPoint(_mark_span(label)[0], 0)).x()
                assert box.geometry().right() < left
            assert box.y() == max(mark.y(), label.screen().availableGeometry().top())  # level
            assert box.testAttribute(Qt.WA_TranslucentBackground)
            app.sendEvent(label, QEvent(QEvent.Leave))
            assert not box.isVisible()
    assert title.toolTip().startswith("Starting numbers")
    family.close()


def test_long_help_wraps_to_the_room_on_the_right(app):
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

    from asteria.editor.decor import HELP_WIDTH, _mark_span, help_box, install
    from asteria.editor.responsive_form import _field_cell

    install(app)
    window = QWidget()
    window.setGeometry(0, 200, 400, 120)  # room on the right, even on a small screen
    cell = _field_cell("Order", QLineEdit(), "Lower comes first. " * 40)  # a Game Systems field
    cell.setParent(window)
    window.show()
    (caption,) = [lb for lb in cell.findChildren(QLabel) if "ⓘ" in lb.text()]
    inside = QPoint(caption.width() - 2, 2)
    assert app.sendEvent(caption, QHelpEvent(QEvent.ToolTip, inside, caption.mapToGlobal(inside)))
    box, mark = help_box(), caption.mapToGlobal(QPoint(_mark_span(caption)[1], 0))
    assert box.x() > mark.x() and box.width() <= HELP_WIDTH
    assert box.wordWrap() and box.height() > 2 * box.fontMetrics().height()  # wrapped lines
    window.close()
    assert not box.isVisible()  # its mark went: so did the help


def test_graph_positions_are_left_to_the_graph_view(app):
    from PySide6.QtWidgets import QLabel

    project, _document, family = _family("graphs", "brave_tree")
    texts = [label.text() for label in family.editor.findChildren(QLabel)]
    assert not any("Positions in the graph view" in t for t in texts)  # dragged, not typed
    family.auto_apply()  # an edit elsewhere keeps the saved positions as they were
    assert project.rpg_database.progression_graphs["brave_tree"] is not None


def test_a_job_shows_its_growth_curves_by_the_games_rules(app):
    """As RPG Maker's Parameter Curves: a chart per stat, from the actor's base stats plus the
    job's bonus and growth per level; an edit redraws them."""
    from asteria.editor.growth_curves import CurveChart, growth_curves

    project, _document, family = _family("classes", "archmage")
    form = family.editor
    curves = form.growth_curves
    database = project.rpg_database
    actor = database.actors[curves.actor.currentData()]
    assert "archmage" in [c.class_id for c in actor.class_assignments]  # its own actors first
    rows = {
        key: values
        for _kind, key, values in growth_curves(
            actor.to_data(), [database.classes["archmage"].to_data()], 99
        )
    }
    growth = database.classes["archmage"].level_growth["int"]
    assert rows["int"][0] == actor.base_stats["int"]
    assert abs(rows["int"][-1] - (actor.base_stats["int"] + growth * 98)) < 1e-6
    charts = curves.findChildren(CurveChart)
    assert len(charts) == len(rows) and charts[0].title == "HP"  # HP, MP first
    form._data["level_growth"]["int"] = 5.0
    curves.redraw()
    int_chart = next(c for c in curves.findChildren(CurveChart) if c.title == "INT")
    assert int_chart.values[-1] == actor.base_stats["int"] + 5.0 * 98


def test_tags_are_a_table_and_resources_one_grid(app):
    from asteria.editor.record_form import ChipList, NumberMatrix

    _project, _document, family = _family("actors", "hero_01")
    form = family.editor
    (tags,) = [c for c in form.findChildren(ChipList) if "trait.cover" in c.values]
    row = tags.values.index("trait.cover")
    assert (tags.table.item(row, 0).text(), tags.table.item(row, 1).text()) == ("Trait", "Cover")
    tags.table.cellWidget(row, 2).click()  # ✕ removes the row
    assert "trait.cover" not in tags.values and tags.table.rowCount() == len(tags.values)
    (matrix,) = form.findChildren(NumberMatrix)
    assert list(matrix.values)[0] == "vitality" and matrix.columns[:2] == ["current", "maximum"]
    matrix._set("vitality", "maximum", 4000.0)
    assert form._data["base_resources"]["vitality"]["maximum"] == 4000.0


def test_plain_entries_are_table_rows_and_numbers_are_compared(app):
    from asteria.editor.growth_curves import StatBar, StatComparison
    from asteria.editor.record_form import CardList, ChipList, EntryTable

    _project, _document, family = _family("equipment", "a_archon_robe")
    form = family.editor
    (changes,) = [t for t in form.findChildren(EntryTable) if t.key == "modifiers"]
    assert changes.columns[:3] == ["stat", "operation", "value"]
    cards = [c for c in form.findChildren(CardList) if c.key == "modifiers"]
    assert cards == [changes]
    before = len(changes.entries)
    changes.duplicate(0)  # the row's buttons edit the list as a card's did
    assert len(form._data["modifiers"]) == before + 1

    _project, _document, family = _family("enemies", "crimson_warlord")
    form = family.editor
    (tags,) = [c for c in form.findChildren(ChipList) if "boss" in c.values]
    assert len(tags.values) > ChipList.SPLIT and tags.table.columnCount() == 6
    assert tags.table.rowCount() == -(-len(tags.values) // 2)  # two halves side by side
    (stats,) = [c for c in form.findChildren(StatComparison) if c.key == "stats"]
    bars = {bar.title: bar for bar in stats.findChildren(StatBar)}
    attack = bars["ATK"]
    assert attack.value == 108 and attack.count > 1
    assert 1 <= attack.rank <= attack.count and attack.top >= attack.value


def test_slots_show_where_they_stand_and_their_tags_in_a_cell(app):
    from asteria.editor.growth_curves import PositionsPreview
    from asteria.editor.record_form import EntryTable, ListCell

    _project, _document, family = _family("formations", "standard_six")
    form = family.editor
    (preview,) = form.findChildren(PositionsPreview)
    assert [name for name, _entry in preview.entries()][:2] == ["Slot 1", "Slot 2"]
    (slots,) = form.findChildren(EntryTable)
    assert "tags" in slots.columns
    cells = slots.findChildren(ListCell)
    assert len(cells) == len(slots.entries) and cells[0].text() == "Front"
