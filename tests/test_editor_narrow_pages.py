"""Game Data and Game Systems pages fit a narrow window: fields wrap or stack, the form never
reaches past the right edge (a RecordForm has no sideways scroll bar: what sticks out is cut)."""

import pytest

pytest.importorskip("PySide6")

from pathlib import Path  # noqa: E402

from PySide6.QtWidgets import (  # noqa: E402
    QAbstractScrollArea,
    QApplication,
    QFrame,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from asteria.editor import EditorDocument, i18n  # noqa: E402
from asteria.editor.authoring_hub_widget import AdapterFamilyWidget  # noqa: E402
from asteria.editor.record_form import (  # noqa: E402
    ChipList,
    EntryTable,
    NumberBox,
    Picker,
    RecordForm,
    Section,
    _combo_text_width,
    _ElidedLabel,
)
from asteria.editor.record_vocabulary import Choice  # noqa: E402
from asteria.editor.responsive_form import ResponsiveForm, columns_that_fit  # noqa: E402
from asteria.editor.shell import AsteriaEditorWindow  # noqa: E402
from asteria.editor.theme import apply_asteria_theme  # noqa: E402
from asteria.editor.workspace import WorkspaceMode  # noqa: E402
from asteria.project import Project  # noqa: E402

DEMO = Path(__file__).resolve().parents[1] / "reference_projects" / "full_verification_demo"


@pytest.fixture
def themed_app():
    """The themed app as the editor starts it: the theme's fonts and padding set the widths."""
    app = QApplication.instance() or QApplication([])
    sheet, palette, font = app.styleSheet(), app.palette(), app.font()
    apply_asteria_theme(app)
    i18n.install(app, "en")
    yield app
    i18n.set_language("en")
    app.setStyleSheet(sheet)
    app.setPalette(palette)
    app.setFont(font)


def _settle(app, rounds=4):
    for _ in range(rounds):
        app.processEvents()


def _hosted(widget):
    """``widget`` in a window of its own: a page's layout reads its minimum as a form's would (a
    widget that is itself a window could not shrink below what its own layout holds now)."""
    host = QWidget()
    column = QVBoxLayout(host)
    column.setContentsMargins(0, 0, 0, 0)
    column.addWidget(widget)
    host.show()
    return host


def _inside_inner_view(widget, page):
    """A widget inside a table or list on the page: that view clips and scrolls it itself."""
    parent = widget.parentWidget()
    while parent is not None and parent is not page:
        if isinstance(parent, (QAbstractScrollArea, QLineEdit)):
            return True
        parent = parent.parentWidget()
    return False


def _problems(root):
    """What a person would see wrong on the shown page: a form wider than its area, a widget
    past the right edge, a widget squeezed under its minimum, a label cut."""
    found = []
    for scroll in root.findChildren(QScrollArea):
        page = scroll.widget()
        if page is None or not scroll.isVisible():
            continue
        if scroll.horizontalScrollBar().maximum() > 0:
            found.append(("wider than its area", scroll.horizontalScrollBar().maximum()))
        edge = scroll.viewport().width()
        for child in page.findChildren(QWidget):
            if not child.isVisible() or child.isWindow() or _inside_inner_view(child, page):
                continue
            name = type(child).__name__
            if child.mapTo(page, child.rect().topRight()).x() > edge + 1:
                found.append(("past the edge", name))
            least = child.minimumWidth() or child.minimumSizeHint().width()
            if least > child.width() + 1 and name != "QWidget":
                found.append(("squeezed", name, least, child.width()))
            if isinstance(child, QLabel) and not isinstance(child, _ElidedLabel):
                text = child.text()
                if text and not child.wordWrap() and "<" not in text and "\n" not in text:
                    wanted = child.fontMetrics().horizontalAdvance(text.replace("&", ""))
                    if wanted > child.contentsRect().width() + 1:
                        found.append(("label cut", text[:40]))
    return found


def _settled_problems(app, root):
    """``_problems`` once the page has settled: nested forms take a few rounds to re-flow."""
    return _problems(root) and (_settle(app, 12) or _problems(root))


def test_every_page_fits_a_narrow_window(themed_app):
    project = Project.load_json(DEMO / "project.asteria.json", EditorDocument().component_registry)
    window = AsteriaEditorWindow(project)
    try:
        window.setMinimumSize(0, 0)  # the forms themselves must cope: the window's floor is 1000
        window.show()
        window.workspace.set_mode(WorkspaceMode.RPG)
        family = window.rpg_authoring.findChild(AdapterFamilyWidget)
        systems = window.game_systems_editor
        wrong = {}
        # 700 in both languages, 900 in the first as well: a full page walk is slow
        for language, width in (("en", 900), ("en", 700), ("zh_TW", 700)):
            if i18n.CURRENT["language"] != language:
                i18n.set_language(language)
                window.refresh_all()
            window.resize(width, 900)
            _settle(themed_app)
            assert window.width() == width
            pages = 0
            for host, kinds, browser, area in (
                (window.rpg_authoring, family.category, family.browser, window.rpg_authoring),
                (systems, systems.kind_box, systems.browser, systems),
            ):
                window.rpg_workspace.setCurrentWidget(host)
                for index in range(kinds.count()):
                    kinds.setCurrentIndex(index)
                    _settle(themed_app)
                    if browser.count() and browser.currentRow() < 0:
                        browser.setCurrentRow(0)
                        _settle(themed_app)
                    pages += 1
                    problems = _settled_problems(themed_app, area)
                    if problems:
                        wrong[language, width, kinds.itemText(index)] = problems[:4]
            assert pages > 50  # every page was really walked
        assert wrong == {}
    finally:
        window.close()
        window.deleteLater()


def test_columns_that_fit_counts_each_column_as_wide_as_its_widest_field():
    assert columns_that_fit([100, 100, 100], 320, spacing=10, most=3) == 3
    assert columns_that_fit([100, 100, 100], 319, spacing=10, most=3) == 2
    assert columns_that_fit([100, 100, 100], 50, spacing=10, most=3) == 1
    # the third field falls under the first, so the first column is 300 wide with two columns
    assert columns_that_fit([100, 100, 300], 410, spacing=10, most=2) == 2
    assert columns_that_fit([100, 100, 300], 409, spacing=10, most=2) == 1
    # a whole row (None) starts a new line: the next field is in the first column again
    assert columns_that_fit([100, None, 100], 210, spacing=10, most=2) == 2
    assert columns_that_fit([100, 100, None, 100, 200], 310, spacing=10, most=2) == 2


def test_a_section_wraps_its_columns_and_asks_for_one_column_only(themed_app):
    section = Section("Numbers", columns=3)
    labels = ("First", "Second", "Third", "Fourth")
    for label in labels:
        box = NumberBox(1)
        box.setMinimumWidth(120)
        section.add_row(label, box)
    section.show()
    try:
        section.resize(700, 300)
        _settle(themed_app)
        assert section.shown_columns == 3
        narrow = section.minimumSizeHint().width()
        assert narrow < 2 * 120  # the narrowest it asks for: one column, not all three
        section.resize(320, 300)
        _settle(themed_app)
        assert section.shown_columns == 2
        section.resize(narrow, 300)
        _settle(themed_app)
        assert section.shown_columns == 1
        section.show_more()
        assert len(section.flow_cells) == len(labels)  # every field is still there, in order
        tops = [cell[1].mapTo(section, cell[1].rect().topLeft()) for cell in section.flow_cells]
        assert [p.y() for p in tops] == sorted(p.y() for p in tops)  # one under the other
        section.resize(700, 300)
        _settle(themed_app)
        assert section.shown_columns == 3
    finally:
        section.close()
        section.deleteLater()


def test_an_entry_table_stacks_when_narrow_and_is_a_table_again_when_wide(themed_app):
    form = RecordForm()
    entries = [
        {"stat": "attack", "operation": "add", "value": 3, "note": "strong"},
        {"stat": "guard", "operation": "add", "value": 1, "note": "steady"},
    ]
    table = EntryTable(form, {"modifiers": entries}, "modifiers", entries, list(entries[0]))
    host = _hosted(table)
    try:
        host.resize(1200, 300)
        _settle(themed_app)
        assert table.stacked == 0
        heads = [w for w in table.findChildren(QLabel) if w.objectName() == "FormTableHead"]
        shown = [w.text() for w in heads if w.isVisible()]
        assert len(shown) == len(table.columns) + 1  # the column names and #

        least = table.minimumSizeHint().width()
        assert least < 500  # it never asks for all its columns side by side
        host.resize(least, 500)
        _settle(themed_app)
        assert table.width() == least and table.stacked == 1
        frame = table.findChild(QFrame, "FormCard")
        assert frame.width() <= table.width()
        heads = [w for w in table.findChildren(QLabel) if w.objectName() == "FormTableHead"]
        names = [w.text() for w in heads if w.isVisible()]
        # each entry's fields under their own names; the table's single head line is gone
        assert len(names) == len(entries) * len(table.columns)
        for widget in table.findChildren(QWidget):
            if widget.isVisible() and not isinstance(widget, QFrame):
                assert widget.mapTo(table, widget.rect().topRight()).x() <= table.width() + 1

        host.resize(1200, 300)
        _settle(themed_app)
        assert table.stacked == 0
        assert not [w for w in heads if w.isVisible() and w not in table._heads]
    finally:
        host.close()
        host.deleteLater()


def test_a_deep_table_lets_its_drop_downs_take_the_room_there_is(themed_app):
    form = RecordForm()
    # a stat no list holds: its drop-down shows a long warning, wider than a deep table has
    entries = [{"stat": "unknown_stat", "note": "x"}]
    table = EntryTable(form, {"rules": entries}, "rules", entries, list(entries[0]))
    picker = table._rows[0][1][0]
    assert isinstance(picker, Picker)
    want = table._wants[picker]
    assert want > EntryTable.PICKER_LEAST
    host = _hosted(table)
    try:
        least = table.minimumSizeHint().width()
        assert least < want  # it asks for less than the drop-down's longest choice
        host.resize(least, 500)
        _settle(themed_app, 8)
        assert table.stacked == 1
        assert EntryTable.PICKER_LEAST <= picker.minimumWidth() < want
        frame = table.findChild(QFrame, "FormCard")
        assert frame.width() <= table.width()  # its border counted: nothing squeezed
        assert picker.lineEdit().cursorPosition() == 0  # the words show from their start
        host.resize(1200, 300)
        _settle(themed_app, 8)
        assert picker.minimumWidth() == want  # wide again: the longest choice shows whole
    finally:
        host.close()
        host.deleteLater()


def test_a_long_record_title_takes_two_lines_not_the_width(themed_app):
    form = RecordForm()
    evolution = {  # no name of its own: its title is "source  →  result"
        "evolution_id": "weapon_dance_siphon",
        "source_ability_id": "weapon_dance_with_a_much_longer_name",
        "result_ability_id": "weapon_dance_siphon_with_a_much_longer_name_than_fits",
    }
    form.set_record(evolution, "weapon_dance_siphon")
    titles = [w for w in form.findChildren(QLabel) if w.objectName() == "FormTitle"]
    assert titles and all(t.wordWrap() for t in titles)
    assert all(t.minimumSizeHint().width() <= 120 for t in titles)


def test_small_fields_do_not_pull_the_stacked_columns_apart(themed_app):
    form = RecordForm()
    entries = [{"stat": "attack", "note": "strong", "value": 3, "other": 4}]
    table = EntryTable(form, {"modifiers": entries}, "modifiers", entries, list(entries[0]))
    host = _hosted(table)
    try:
        host.resize(table.minimumSizeHint().width() + 60, 500)
        _settle(themed_app)
        assert table.stacked
        number, cells, _buttons, _opens = table._rows[0]
        left = number.mapTo(table, number.rect().topLeft()).x()
        # the first field starts under the number, at the card's left: no number field's
        # largest width has capped the columns and floated them apart
        assert cells[0].mapTo(table, cells[0].rect().topLeft()).x() == left
    finally:
        host.close()
        host.deleteLater()


def test_a_long_list_keeps_two_halves_only_where_they_fit(themed_app):
    values = [f"tag_{i}" for i in range(12)]
    tags = ChipList(values, [Choice(v, f"Kind: {v}") for v in values], noun="tag")
    assert tags.table.columnCount() == 6  # before it has a width: the two halves
    tags.show()
    try:
        tags.resize(ChipList.TWO_HALVES_FROM + 100, 400)
        _settle(themed_app)
        assert tags.table.columnCount() == 6
        tags.resize(ChipList.TWO_HALVES_FROM - 100, 400)
        _settle(themed_app)
        assert tags.table.columnCount() == 3
        assert tags.table.rowCount() == len(values)
        assert tags.table.height() >= tags.ROW * len(values)  # every row shows
        assert tags.values == values
        assert tags.table.columnWidth(0) < 240  # the drop-down beside it keeps its room
    finally:
        tags.close()
        tags.deleteLater()


def test_a_narrow_tag_list_shows_each_type_whole_and_its_words_on_hover(themed_app):
    values = ["category:skill", "weapon_blow:bow"]
    choices = [
        Choice("category:skill", "Category: Is a skill"),
        Choice("weapon_blow:bow", "Weapon Blow: Bow"),
    ]
    words = "What carrying this tag does, in a sentence"
    tags = ChipList(values, choices, noun="tag", meaning=lambda _value: words)
    host = _hosted(tags)
    try:
        host.resize(330, 300)
        _settle(themed_app)
        kinds = [tags.table.cellWidget(row, 0) for row in range(tags.table.rowCount())]
        need = max(_combo_text_width(box, box.currentText()) for box in kinds)
        assert tags.table.columnWidth(0) >= need  # "Weapon Blow" whole, not a share of width
        said = tags.findChildren(_ElidedLabel)
        assert said and not any(label.isVisible() for label in said)  # no room for words
        contents = [w for w in tags.findChildren(QWidget) if w.objectName() == "FormTagContent"]
        # on hover instead, after the drop-down's whole value
        assert [box.toolTip() for box in contents] == [
            f"{box.currentText()}\n{words}" for box in contents
        ]
        host.resize(1100, 300)
        _settle(themed_app)
        assert all(label.isVisible() for label in said)
    finally:
        host.close()
        host.deleteLater()


def test_long_words_beside_a_tag_end_in_an_ellipsis_and_stay_whole_on_hover(themed_app):
    words = "What carrying this tag does, in a sentence longer than any cell of the table"
    label = _ElidedLabel(words)
    label.setToolTip(words)
    assert label.minimumSizeHint().width() == 0  # the drop-down beside it comes first
    assert label.text() == words and label.toolTip() == words
    label.resize(60, 20)
    label.grab()  # draws without error in its small room


def test_a_form_does_not_squeeze_a_wide_field_into_its_columns(themed_app):
    form = ResponsiveForm(column_width=100, max_columns=3)
    wide = Picker([Choice("a", "A")], "a")
    wide.setMinimumWidth(180)
    form.add_row("Wide", wide)
    form.add_row("Also", NumberBox(1))
    assert form.minimumSizeHint().width() >= 180  # a field wider than a column is the minimum
    host = _hosted(form)
    try:
        host.resize(250, 200)
        _settle(themed_app)
        assert form.columns == 1  # two columns of 100 would hold neither
        assert wide.width() >= 180
        host.resize(400, 200)
        _settle(themed_app)
        assert form.columns > 1  # room for it beside the other: columns again
    finally:
        host.close()
        host.deleteLater()


def test_a_number_box_shows_its_number(themed_app):
    """The theme's border and padding leave a number box's text field its width. PySide6 6.11.3
    and 6.12.0 laid it out 1 px wide (no number to see): pyproject.toml keeps PySide6 below."""
    box = NumberBox(3200, integer=True)
    box.setFixedWidth(84)
    host = _hosted(box)
    try:
        _settle(themed_app)
        field = box.lineEdit()
        assert field.width() >= field.fontMetrics().horizontalAdvance("3200")
        assert field.geometry().left() > 0  # the padding is inside the border
    finally:
        host.close()
        host.deleteLater()
