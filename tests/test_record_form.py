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
    from asteria.editor.records.hub import AdapterFamilyWidget
    from asteria.editor.rpg.integrated_authoring import IntegratedAuthoringControllers
    from asteria.project import Project
    from asteria.runtime.component_registry import default_component_registry

    project = Project.load_json(DEMO / "project.asteria.json", default_component_registry())
    document = EditorDocument(project)
    document.file_path = DEMO / "project.asteria.json"
    controllers = IntegratedAuthoringControllers(document)
    family = AdapterFamilyWidget("Game Data", controllers.rpg_categories(), document=document)
    family.category.setCurrentIndex(family.category.findData(category))
    family.select_ids([key])
    return project, document, family


def test_fields_get_friendly_widgets(app):
    from asteria.editor.records.form_chips import ChipList
    from asteria.editor.records.form_controls import NumberBox, Picker
    from asteria.editor.records.form_tables import AmountTable

    _project, _document, family = _family("actors", "hero_01")
    form = family.editor
    stats = [t for t in form.findChildren(AmountTable) if "str" in t.values]
    assert stats and stats[0].values["str"] == 32  # the base stats, as a table of numbers
    chips = [c for c in form.findChildren(ChipList) if "trait.ring_bearer" in c.values]
    assert chips  # tags as chips
    pickers = [p for p in form.findChildren(Picker) if p.value() == "brave"]
    assert pickers  # the job is picked from the jobs, not typed
    assert form.findChildren(NumberBox)
    assert "Roger" in family.browser.item(family._ids.index("hero_01")).text()  # names listed


def test_an_edit_applies_on_its_own_and_undoes(app):
    from asteria.editor.records.form_tables import AmountTable

    project, document, family = _family("actors", "hero_01")
    (table,) = [t for t in family.editor.findChildren(AmountTable) if "str" in t.values]
    table._set("str", 20)
    family.auto_apply()  # what the timer does a moment after typing stops
    assert project.rpg_database.actors["hero_01"].base_stats["str"] == 20
    document.undo()
    assert project.rpg_database.actors["hero_01"].base_stats["str"] == 32


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

    from asteria.editor.records.form_controls import NumberBox
    from asteria.editor.records.form_parts import CardList

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
    from asteria.editor.rpg.game_systems_widget import _IconPicker

    _project, _document, family = _family("items", "ether_leaf")
    (picker,) = family.editor.findChildren(_IconPicker)
    assert picker.combo.count() <= 2  # "(none)" and the item's own icon
    assert picker.text() == "icon.ether_leaf"
    assert not picker.combo.itemIcon(picker.combo.currentIndex()).isNull()  # with its picture
    assert picker.combo.findData("forged:fire") > 0  # a search fills the whole list
    assert picker.text() == "icon.ether_leaf"  # and keeps the choice


def test_help_shows_on_hover_only(app):
    from PySide6.QtWidgets import QLabel

    from asteria.editor.records.vocabulary import CATEGORY_HELP, HELP

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

    from asteria.editor.ui.decor import HELP_GAP, HELP_MIN_WIDTH, _mark_span, help_box, install

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


def test_help_says_only_the_help_not_the_data_key(app):
    from PySide6.QtWidgets import QLabel

    _project, _document, family = _family("actors", "hero_01")
    tips = [lb.toolTip() for lb in family.findChildren(QLabel) if "ⓘ" in lb.text()]
    assert not [tip for tip in tips if "data:" in tip or "\n\n" in tip]
    bare = [lb for lb in family.findChildren(QLabel) if lb.objectName() == "FormFieldLabel"]
    assert bare and not [lb.text() for lb in bare if lb.toolTip() and "ⓘ" not in lb.text()]
    family.close()


def test_a_card_of_lists_is_called_after_what_is_in_it(app):
    from PySide6.QtWidgets import QToolButton

    from asteria.editor.records.form_parts import Section
    from asteria.editor.records.form_shapes import lists_title

    assert lists_title(["Properties"]) == "Properties"
    assert lists_title(["Properties", "Abilities"]) == "Properties and Abilities"
    assert lists_title(["Skills", "Properties", "Blocked Slots"]) == "Lists"
    _project, _document, family = _family("actors", "hero_01")
    titles = [section.toggle.text() for section in family.findChildren(Section)]
    assert "Properties and Abilities" in titles
    adds = [b.text() for b in family.findChildren(QToolButton) if b.objectName() == "FormAddChip"]
    assert "+ Add property" in adds
    family.close()


def test_short_help_after_long_help_gets_a_short_box(app):
    from PySide6.QtWidgets import QLabel

    from asteria.editor.ui.decor import help_box, install, show_help_tip

    install(app)
    label = QLabel("Basics ⓘ")
    label.show()
    label.setToolTip("Short.")
    show_help_tip(label)
    short = help_box().height()
    label.setToolTip("Long help that has to wrap onto further lines of the box. " * 8)
    show_help_tip(label)
    assert help_box().height() > short
    label.setToolTip("Short.")
    show_help_tip(label)
    assert help_box().height() == short
    label.close()


def test_long_help_wraps_to_the_room_on_the_right(app):
    from PySide6.QtCore import QEvent, QPoint
    from PySide6.QtGui import QHelpEvent
    from PySide6.QtWidgets import QLabel, QLineEdit, QWidget

    from asteria.editor.ui.decor import HELP_WIDTH, _mark_span, help_box, install
    from asteria.editor.ui.responsive_form import _field_cell

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
    """As RPG Maker's Parameter Curves: a chart per stat the job raises, its own share level
    by level (whoever takes it); an edit redraws them. An actor's page has none (its jobs
    change in play)."""
    from asteria.editor.rpg.growth_curves import CurveChart, GrowthCurves

    project, _document, family = _family("classes", "archmage")
    form = family.editor
    curves = form.growth_curves
    database = project.rpg_database
    job = database.classes["archmage"]
    charts = {chart.title: chart for chart in curves.findChildren(CurveChart)}
    assert charts["INT"].values[0] == job.stat_bonuses.get("int", 0.0)
    gained = charts["INT"].values[-1] - charts["INT"].values[0]
    assert abs(gained - job.level_growth["int"] * 98) < 1e-6
    mana = charts["MP"].values[-1] - charts["MP"].values[0]  # from the job's own MP bonus
    assert abs(mana - job.resource_growth["technique"] * 98) < 1e-6
    # HP, MP first; then only the stats set to Grow with Level (not ATK, a formula's)
    titles = list(charts)
    grown = [s for s in job.level_growth if "classes" in database.stat_definitions[s].set_on]
    assert titles[:2] == ["HP", "MP"] and len(titles) == 2 + len(grown)
    assert "ATK" not in titles and "VIT" in titles
    form._data["level_growth"]["int"] = 5.0
    curves.redraw()
    int_chart = next(c for c in curves.findChildren(CurveChart) if c.title == "INT")
    assert int_chart.values[-1] == int_chart.values[0] + 5.0 * 98
    _project, _document, family = _family("actors", "hero_01")
    assert not family.editor.findChildren(GrowthCurves)


def test_tags_are_a_table_and_resources_one_grid(app):
    from asteria.editor.records.form_chips import ChipList
    from asteria.editor.records.form_tables import NumberMatrix

    _project, _document, family = _family("actors", "hero_04")
    form = family.editor
    (tags,) = [c for c in form.findChildren(ChipList) if "trait.follow_up" in c.values]
    row = tags.values.index("trait.follow_up")
    shown = (tags.table.item(row, 0).text(), tags.table.item(row, 1).text())
    assert shown == ("Trait", "Follow Up")
    tags.table.cellWidget(row, 2).click()  # ✕ removes the row
    assert "trait.follow_up" not in tags.values and tags.table.rowCount() == len(tags.values)
    (matrix,) = form.findChildren(NumberMatrix)
    assert matrix.columns == ["maximum", "current", "minimum"]


def test_hp_and_mp_are_stats_and_resources_are_the_special_ones(app):
    from asteria.editor.records.form_tables import AmountTable, NumberMatrix
    from asteria.editor.rpg.growth_curves import StatBar, StatComparison

    _project, _document, family = _family("actors", "hero_01")
    form = family.editor
    (table,) = [t for t in form.findChildren(AmountTable) if "str" in t.values]
    (special,) = form.findChildren(NumberMatrix)
    assert table.values["vitality"] == 3200 and table.values["str"] == 32
    assert list(table._labels)[:2] == ["vitality", "technique"]
    assert not special.values and "shield" in special.labels
    assert "shield" not in table._labels  # a mechanic of its own: not among the stats

    table._set("vitality", 4000.0)  # the engine's own places, a full resource stays full
    pool = form._data["base_resources"]["vitality"]
    assert pool["maximum"] == 4000.0 and pool["current"] == 4000.0 and pool["minimum"] == 0.0
    assert "vitality" not in form._data["base_stats"]
    table._set("str", 30.0)
    assert form._data["base_stats"]["str"] == 30.0 and "str" not in form._data["base_resources"]

    # one table for a mechanic's amounts; a full one stays full, one that isn't keeps its start
    special.values["shield"] = special.new_row("shield")
    special.edited.emit()
    assert form._data["base_resources"]["shield"]["maximum"] == 1.0  # its rule's maximum
    special._set("shield", "maximum", 9.0)
    assert form._data["base_resources"]["shield"]["current"] == 9.0
    special._set("shield", "current", 2.0)
    special._set("shield", "maximum", 12.0)
    assert form._data["base_resources"]["shield"] == {
        "current": 2.0,
        "maximum": 12.0,
        "minimum": 0.0,
    }
    table._set("str", 31.0)  # another table's edit leaves it alone
    assert form._data["base_resources"]["shield"]["current"] == 2.0 and "shield" in special.values
    assert "shield" not in table.values
    special._remove("shield")
    assert "shield" not in form._data["base_resources"]

    # HP added there gets its own start, and is the same number as among the stats
    special.values["technique"] = special.new_row("technique")
    special.edited.emit()
    special._set("technique", "current", 50.0)
    special._set("technique", "maximum", 500.0)
    assert table.values["technique"] == 500.0
    table._set("technique", 600.0)
    assert special.values["technique"]["maximum"] == 600.0
    pool = form._data["base_resources"]["technique"]
    assert pool["maximum"] == 600.0 and pool["current"] == 50.0
    special._remove("technique")  # taken off: full again, and still among the stats
    pool = form._data["base_resources"]["technique"]
    assert pool["current"] == 600.0 == pool["maximum"] and table.values["technique"] == 600.0
    table._remove("technique")
    assert "technique" not in form._data["base_resources"]
    (compared,) = [c for c in form.findChildren(StatComparison) if c.key == "base_stats"]
    assert compared._numbers(form._data)["vitality"] == 4000.0

    _project, _document, family = _family("enemies", "vaelor")
    form = family.editor
    (table,) = [t for t in form.findChildren(AmountTable) if "speed" in t.values]
    (special,) = [t for t in form.findChildren(AmountTable) if t.noun == "resource"]
    assert table.values["vitality"] == 36000 and set(special.values) == {"shield"}
    before = dict(form._data["resources"])
    table._set("vitality", 100.0)
    special._set("shield", 3.0)
    assert form._data["resources"] == {**before, "vitality": 100.0, "shield": 3.0}
    assert "vitality" not in form._data["stats"]
    (stats,) = [c for c in form.findChildren(StatComparison) if c.key == "stats"]
    hp = next(b for b in stats.findChildren(StatBar) if b.value == 36000 or b.value == 100)
    assert hp is not None

    _project, _document, family = _family("classes", "brave")
    form = family.editor
    (table,) = [t for t in form.findChildren(AmountTable) if "str" in t.values]
    assert "vitality" in table.values
    table._set("vitality", 77.0)
    assert form._data["resource_growth"]["vitality"] == 77.0
    assert "vitality" not in form._data["level_growth"]
    held = dict(form._data["resource_bonuses"])
    assert held and not any(t.noun == "resource" and held.keys() & t.values.keys()
                            for t in form.findChildren(AmountTable))  # fmt: skip
    bonuses = form._paired[("stat_bonuses", "resource_bonuses")].stats
    assert held.keys() <= bonuses.values.keys()
    key = next(iter(held))
    bonuses._set(key, 5.0)
    assert form._data["resource_bonuses"][key] == 5.0 and key not in form._data["stat_bonuses"]


def test_each_side_is_compared_with_its_own_side_only(app):
    from asteria.editor.rpg.growth_curves import StatBar, StatComparison

    project, _document, family = _family("enemies", "vaelor")
    enemies = project.rpg_database.enemies
    speeds = [e.stats["speed"] for e in enemies.values() if "speed" in e.stats]
    (stats,) = [c for c in family.editor.findChildren(StatComparison) if c.key == "stats"]
    bar = next(b for b in stats.findChildren(StatBar) if b.title == "SPD")
    assert bar.average == pytest.approx(sum(speeds) / len(speeds))

    project, _document, family = _family("actors", "hero_01")
    actors = project.rpg_database.actors
    strengths = [a.base_stats["str"] for a in actors.values() if "str" in a.base_stats]
    (stats,) = [c for c in family.editor.findChildren(StatComparison) if c.key == "base_stats"]
    bar = next(b for b in stats.findChildren(StatBar) if b.title == "STR")
    assert bar.average == pytest.approx(sum(strengths) / len(strengths))


def test_plain_entries_are_table_rows_and_numbers_are_compared(app):
    from PySide6.QtWidgets import QToolButton

    from asteria.editor.records.form_chips import ChipList
    from asteria.editor.records.form_parts import CardList, EntryTable
    from asteria.editor.rpg.growth_curves import StatBar, StatComparison

    _project, _document, family = _family("equipment", "a_archon_robe")
    form = family.editor
    (changes,) = [t for t in form.findChildren(EntryTable) if t.key == "modifiers"]
    assert changes.columns[:3] == ["stat", "operation", "value"]
    cards = [c for c in form.findChildren(CardList) if c.key == "modifiers"]
    assert cards == [changes]
    marks = {b.text() for b in changes.findChildren(QToolButton) if "⋯" in b.text()}
    assert marks == {"⋯"}  # the button for the rest says nothing more, no count
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
    assert attack.value == 108 and attack.top >= attack.value


def test_slots_show_where_they_stand_and_their_tags_in_a_cell(app):
    from asteria.editor.records.form_parts import EntryTable, ListCell
    from asteria.editor.rpg.growth_curves import PositionsPreview

    _project, _document, family = _family("formations", "standard_six")
    form = family.editor
    (preview,) = form.findChildren(PositionsPreview)
    assert [name for name, _entry in preview.entries()][:2] == ["Slot 1", "Slot 2"]
    (slots,) = form.findChildren(EntryTable)
    assert "tags" in slots.columns
    cells = slots.findChildren(ListCell)
    assert len(cells) == len(slots.entries) and cells[0].text() == "Front Row"  # its name


def test_stats_grow_with_level_by_a_switch_and_jobs_read_plainly(app):
    from asteria.editor.records.form_controls import Picker
    from asteria.editor.records.form_parts import EntryTable
    from asteria.editor.rpg.game_systems_authoring import GameSystemsAuthoringController

    _project, document, family = _family("actors", "hero_01")
    systems = GameSystemsAuthoringController(document)
    data = systems.form_data("stat_definitions", "vit", info=False)
    assert data["grows_with_level"] is True and "set_on" not in data
    assert data["base_stats"] == {"actors": True, "enemies": False}  # a tick per record
    data["grows_with_level"] = False  # Game Systems ▸ Stats: VIT no longer grows
    systems.edit("stat_definitions", "vit", data)
    assert "classes" not in document.project.rpg_database.stat_definitions["vit"].set_on
    data["grows_with_level"] = True
    systems.edit("stat_definitions", "vit", data)
    assert document.project.rpg_database.stat_definitions["vit"].set_on == ("actors", "classes")
    data["base_stats"] = {"actors": True, "enemies": True}
    systems.edit("stat_definitions", "vit", data)
    stat = document.project.rpg_database.stat_definitions["vit"]
    assert stat.set_on == ("actors", "classes", "enemies")

    (jobs,) = [t for t in family.editor.findChildren(EntryTable) if t.key == "class_assignments"]
    assert jobs.columns == ["class_id", "role"]
    roles = [p for p in jobs.findChildren(Picker) if p.value() in ("primary", "secondary")]
    assert roles and roles[0].currentText() == "Main job"  # in words, no ⚠


def test_a_tag_is_picked_by_its_type_then_from_a_list(app):
    from PySide6.QtWidgets import QComboBox

    from asteria.editor.records.form_chips import ChipList

    _project, _document, family = _family("actors", "hero_04")
    (tags,) = [c for c in family.editor.findChildren(ChipList) if "trait.follow_up" in c.values]
    row = tags.values.index("trait.follow_up")

    def pick(at):  # the content drop-down, beside what the tag does when that is known
        cell = tags.table.cellWidget(at, 1)
        return cell if isinstance(cell, QComboBox) else cell.findChild(QComboBox)

    kind = tags.table.cellWidget(row, 0)
    content = pick(row)
    assert isinstance(kind, QComboBox) and kind.currentText() == "Trait"
    assert content.currentData() == "trait.follow_up"
    other = next(i for i in range(content.count()) if content.itemData(i) != "trait.follow_up")
    picked = content.itemData(other)
    content.setCurrentIndex(other)
    content.activated.emit(other)  # another trait, picked from the list
    assert picked in tags.values and "trait.follow_up" not in tags.values
    before = list(tags.values)
    tags._add()  # "+ Add tag": a new row, nothing added until a tag is picked
    assert tags.values == before and tags.table.rowCount() == len(before) + 1
    new_content = pick(len(before))
    cancel = tags.table.cellWidget(len(before), 2)
    assert cancel.text() == "✕"  # a row not picked yet can be removed too
    assert new_content.currentText() == "Choose…" and new_content.count() > 1
    new_content.setCurrentIndex(1)
    new_content.activated.emit(1)
    assert len(tags.values) == len(before) + 1
    tags._add()
    tags.table.cellWidget(len(tags.values), 2).click()
    assert not tags._pending and tags.table.rowCount() == len(tags.values)


def test_a_tag_row_says_what_the_tag_does(app):
    from PySide6.QtWidgets import QLabel

    from asteria.editor.records.form_chips import ChipList
    from asteria.editor.records.vocabulary import tag_label, tag_meaning

    assert tag_label("capability.weapon.book") == "Weapon: Book"  # type, then content
    assert tag_meaning("capability.weapon.book") == "Can equip Book weapons"
    _project, _document, family = _family("classes", "archmage")
    (tags,) = [c for c in family.editor.findChildren(ChipList) if c.noun == "tag"]
    said = [w.text() for w in tags.findChildren(QLabel) if w.objectName() == "FormTagEffect"]
    assert "Can equip Book weapons" in said


def test_an_enemy_ai_rule_picks_its_action_and_names_itself(app):
    from PySide6.QtWidgets import QToolButton

    from asteria.editor.records.form_controls import Picker
    from asteria.editor.records.form_parts import CardList
    from asteria.editor.records.form_shapes import entry_title

    _project, _document, family = _family("ai", "goblin_beast_ai")
    form = family.editor
    (rules,) = [c for c in form.findChildren(CardList) if c.key == "rules"]
    first = rules.entries[0]
    assert first["payload"]["ability_id"] == "beast_maul"
    assert entry_title(first, "rule") == "Beast Maul"  # the skill, not the rule's id
    kinds = [p for p in rules.findChildren(Picker) if p.value() == "ability"]
    assert kinds and kinds[0].currentText() == "Skill"  # an action in words, picked
    other = rules.entries[1]["payload"]["ability_id"]
    rules._ai_target(0, "ability_id", other)  # the same skill as rule 2: its id follows
    (rules,) = [c for c in form.findChildren(CardList) if c.key == "rules"]
    assert rules.entries[0]["rule_id"] == other
    rules._ai_target(1, "ability_id", "beast_maul")
    rules._ai_target(1, "ability_id", other)  # a second rule of that skill: a free id
    (rules,) = [c for c in form.findChildren(CardList) if c.key == "rules"]
    assert rules.entries[1]["rule_id"] == f"{other}_2"
    assert form._data["rules"][0]["payload"] == {"ability_id": other}
    rules._ai_kind(0, "hook")  # custom code instead: the hook replaces the skill
    assert form._data["rules"][0]["payload"] == {"hook": ""}
    folds = [b.text() for b in form.findChildren(QToolButton) if b.objectName() == "FormCardMore"]
    assert folds and not any(ch.isdigit() for text in folds for ch in text)  # "More", no count


def test_an_enemy_ai_condition_is_picked_in_words_with_defaults(app):
    from asteria.editor.records.form_controls import Picker
    from asteria.editor.records.form_parts import CardList
    from asteria.editor.records.form_shapes import entry_title

    _project, _document, family = _family("ai", "crimson_ai")
    form = family.editor
    rules = form._data["rules"]
    assert entry_title(rules[0]["conditions"][0], "condition") == "Round is 1"
    (cards,) = [c for c in form.findChildren(CardList) if c.key == "rules"]
    cards._opened().add((id(cards.entries), 0))  # the first rule's card, open
    form.restructure()
    (conditions,) = [c for c in form.findChildren(CardList) if c.entries is rules[0]["conditions"]]
    words = {p.currentText() for p in conditions.findChildren(Picker)}
    assert {"Round", "is"} <= words  # what is checked and how it compares, in words
    conditions._ai_condition_kind(0, "resource_ratio")  # another check: works as it is
    condition = conditions.entries[0]
    assert condition["params"] == {"resource_id": "vitality", "op": "<=", "value": 0.5}
    assert entry_title(condition, "condition", {"vitality": "HP"}) == "HP % is at most 50 %"


def test_boss_phases_read_plainly_and_pick_their_rules_by_name(app):
    from asteria.editor.records.form_chips import ChipList
    from asteria.editor.records.form_parts import CardList
    from asteria.editor.records.form_shapes import ai_context

    _project, _document, family = _family("ai", "crimson_ai")
    form = family.editor
    data = form._data
    (cards,) = [c for c in form.findChildren(CardList) if c.key == "phases"]
    last = data["phases"][2]
    assert ai_context(data, last, cards.names) == "starts when HP % is at most 30 %"
    assert ai_context(data, data["phases"][0], cards.names) == "at the start"
    assert ai_context(data, data["rules"][0], cards.names) == "Opening  ·  Round is 1"
    cards._opened().add((id(cards.entries), 0))
    form.restructure()
    (cards,) = [c for c in form.findChildren(CardList) if c.key == "phases"]
    first = data["phases"][0]["decision_rule_ids"]
    (used,) = [c for c in cards.findChildren(ChipList) if c.noun == "rule" and c.values == first]
    assert used.heads == ("Rule", "When")
    assert used.cells(data["rules"][0]["rule_id"]) == ("1. Iron Stance", "Round is 1")
    cards._phase_rename(0, "First Clash")  # a rename reaches every place that names it
    assert data["phases"][0]["phase_id"] == "first_clash"
    assert data["initial_phase_id"] == "first_clash"


def test_an_effect_step_picks_its_kind_in_words(app):
    from PySide6.QtCore import QCoreApplication

    from asteria.editor.records.form_controls import Picker

    _project, _document, family = _family("abilities", "add_bite")
    form = family.editor
    kinds = [p for p in form.findChildren(Picker) if p.value() == "resource_delta"]
    assert kinds and kinds[0].currentText() == "Change a Resource"  # not "resource_delta"
    step = form._data["effects"][0]["effect"]["operations"][0]
    kinds[0].setCurrentIndex(kinds[0].findData("tag_add"))
    kinds[0].picked.emit()
    assert step["kind"] == "tag_add" and step["value"] is None  # a tag step has no amount
    QCoreApplication.processEvents()
    targets = [p for p in form.findChildren(Picker) if p.value() == step["target"]]
    assert targets  # the tag is picked too
    assert family.auto_apply()  # what it became decodes


def test_ids_are_picked_by_name_or_made_and_folded(app):
    from PySide6.QtWidgets import QLineEdit

    from asteria.editor.records.form_controls import Picker
    from asteria.editor.records.form_shapes import own_id

    _project, _document, family = _family("parties", "main_party")
    form = family.editor
    formation = [p for p in form.findChildren(Picker) if p.value() == "standard_six"]
    assert formation and formation[0].currentText() != "standard_six"  # a formation by name
    slots = [p for p in form.findChildren(Picker) if p.value() == "slot_1"]
    assert slots and slots[0].currentText() == "Slot 1"  # where a member stands, in words
    typed = [e.text() for e in form.findChildren(QLineEdit) if e.isVisibleTo(form)]
    assert "slot_1" not in typed
    assert own_id("slots", "slot_id") and own_id("nodes", "node_id")
    assert not own_id("slots", "actor_id")
    assert family.heading.text() == family.category.currentText()  # no "· 1 record"


def test_record_lists_show_names_and_icons_read_as_words(app):
    from asteria.editor.records.form_chips import ChipList
    from asteria.editor.records.icon_picker import icon_name
    from asteria.editor.records.vocabulary import Choice

    assert icon_name("icon.alchemy_salt") == "Alchemy Salt"
    assert icon_name("asset_library/x/I_Clock.png") == "Clock"
    from PySide6.QtGui import QIcon, QPixmap

    pixmap = QPixmap(8, 8)
    pixmap.fill()
    chips = ChipList(
        ["fire"],
        [Choice("fire", "Fire Bolt", icon="fire")],
        noun="skill",
        icons=lambda _name: QIcon(pixmap),
    )
    assert chips.table.isColumnHidden(1)  # the name only; the id is in the tooltip
    assert chips.table.item(0, 0).toolTip().endswith("fire")
    box = chips.table.cellWidget(0, 0)
    assert not box.itemIcon(box.currentIndex()).isNull()  # the drop-down shows the icon
    assert chips.table.item(0, 0).icon().isNull()  # and no second one is drawn beneath


def test_a_needed_node_and_a_beat_cue_are_picked_in_words(app):
    from asteria.editor.records.form import RecordForm
    from asteria.editor.records.form_controls import Picker
    from asteria.editor.records.form_shapes import node_pair

    assert node_pair("prerequisites", ["awaken", 1])
    assert not node_pair("tags", ["awaken", 1]) and not node_pair("prerequisites", ["a"])
    _project, _document, family = _family("growth", "sunbrand_growth")
    named = [p.currentText() for p in family.editor.findChildren(Picker) if p.value() == "awaken"]
    assert "Awaken" in named  # the node another needs, by its name
    assert RecordForm._STAND_INS["@target"] == "The Target"  # "@target" in words


def test_list_nouns_are_made_singular_by_their_endings():
    """D107: "+ Add switch" (not "switche") and "+ Add term" for a label ending in a sign."""
    from asteria.editor.records.form_shapes import entry_noun, singular

    pairs = {"switches": "switch", "affixes": "affix", "boxes": "box", "statuses": "status",
             "phases": "phase", "entries": "entry", "classes": "class", "caches": "cache",
             "abilities": "ability", "stats": "stat", "what it does": "entry"}  # fmt: skip
    assert {w: singular(w) for w in pairs} == pairs
    assert entry_noun("gene_terms") == "term"
