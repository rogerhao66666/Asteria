"""Game Systems ▸ Pause Menu (D97): the whole pause menu in one place.

The sidebar lists every entry of the menu as the game lists it: a tick shows it, a drag moves
it, and New Page / New Event Entry add one. The page beside it shows the chosen entry: what a
built-in entry opens, a menu page's name, icon and blocks (Status and Items are pages too), an
event entry's name, icon, event program and switches.

The records behind it are what the game reads: the one Pause Menu record (``menu_rules``: the
order and the hidden entries, made when the order is first changed), ``menu_pages`` and
``menu_entries``. Their ids are made from the names; the list's tooltip names them.
"""

from __future__ import annotations

import re

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QHBoxLayout, QInputDialog, QLabel, QPushButton, QVBoxLayout, QWidget

from asteria.rpg.extras import MenuEntry
from asteria.rpg.menu_pages import (
    BUILT_IN_PAGES,
    MENU_ENTRY,
    PAGE_ENTRY,
    PAUSE_OPENS,
    MenuBlock,
    MenuPage,
    default_pages,
)
from asteria.rpg.menu_rules import MenuRules, menu_rules

from .game_systems_authoring import FORMS, GameSystemsAuthoringError, _with_defaults
from .i18n import translate
from .ui_fit import swap_scroll_page

RULES_ID = "pause"  # the Pause Menu record made when a project has none
# what the page leaves out of a record's form: ids are made from names, the order is the list's
HIDDEN = {"menu_pages": ("page_id",), "menu_entries": ("entry_id", "order")}
_ERRORS = (GameSystemsAuthoringError, ValueError, TypeError, KeyError)


def _new_id(name, taken, fallback):
    """``Bag of Holding`` -> ``bag_of_holding`` (``page``, ``page2``... for a name without
    letters, a Chinese one)."""
    base = re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_") or fallback
    key, number = base, 2
    while key in taken:
        key, number = f"{base}{number}", number + 1
    return key


class PauseMenuEditor(QWidget):
    """The pause menu: ``side`` (the list, in the Game Systems sidebar) and the chosen entry's
    page, shown in ``scroll``. ``changed`` - a record changed; ``report(text, ok)`` - a line
    for the page's status."""

    changed = Signal()
    report = Signal(str, bool)

    def __init__(self, controller, scroll, parent=None):
        super().__init__(parent)
        from .game_systems_widget import _PauseOrder

        self.controller = controller
        self.scroll = scroll
        self.side = QWidget()
        layout = QVBoxLayout(self.side)
        layout.setContentsMargins(0, 0, 0, 0)
        self.order = _PauseOrder((), compact=True)
        self.order.edited.connect(self._save_order)
        self.order.list.currentItemChanged.connect(self._selected)
        layout.addWidget(self.order, 1)
        self.new_page_button = QPushButton("New Page")
        self.new_entry_button = QPushButton("New Event Entry")
        self.new_page_button.setToolTip(translate("A screen of the menu built from blocks."))
        self.new_entry_button.setToolTip(translate("An entry that runs an event program."))
        self.new_page_button.clicked.connect(self._new_page_clicked)
        self.new_entry_button.clicked.connect(self._new_entry_clicked)
        layout.addWidget(self.new_page_button)
        layout.addWidget(self.new_entry_button)
        self.form = None
        self.open_layout = None  # screen_id -> opens Menu Screens ▸ Layout (the shell's)
        self._editing = None  # (kind, key) the form edits
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self.apply)

    # -- the list -----------------------------------------------------------------------------
    @property
    def database(self):
        return self.controller.database

    @property
    def selected(self):
        item = self.order.list.currentItem()
        return None if item is None else item.data(Qt.UserRole)

    def refresh(self, select=None):
        """Fill the list from the project and show ``select`` (else the entry shown before,
        else the first)."""
        self.flush()
        current = select or self.selected
        rules = menu_rules(self.database)
        self.order.list.blockSignals(True)
        self.order.set_choices(self.controller.references("pause_entries"))
        if rules is not None:
            self.order.set_value(rules.pause_entries, rules.pause_hidden)
        else:
            self.order.set_value((), ())
        self.order.list.blockSignals(False)
        ids = [item.data(Qt.UserRole) for item in self.order._entries()]
        self.order.list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._selected()

    def _save_order(self):
        order, hidden = self.order.order(), self.order.hidden()
        rules = menu_rules(self.database)
        try:
            if rules is None:
                made = MenuRules(RULES_ID, "Pause menu", pause_entries=order, pause_hidden=hidden)
                self.controller.create("menu_rules", made)
            else:
                data = self.controller.form_data("menu_rules", rules.rules_id, info=False)
                data.update(pause_entries=order, pause_hidden=hidden)
                self.controller.edit("menu_rules", rules.rules_id, data)
        except _ERRORS as exc:
            self.report.emit(translate("⚠  Not applied: ") + str(exc), False)
            return
        self.report.emit("", True)
        self.changed.emit()
        self._selected()  # the page says shown or hidden

    # -- the chosen entry ---------------------------------------------------------------------
    def _record(self, entry):
        """``(kind, key)`` of the record behind ``entry``, or None for a built-in entry that
        opens a screen of its own."""
        if entry in BUILT_IN_PAGES:
            return "menu_pages", entry
        if entry.startswith(PAGE_ENTRY):
            return "menu_pages", entry[len(PAGE_ENTRY) :]
        if entry.startswith(MENU_ENTRY):
            return "menu_entries", entry[len(MENU_ENTRY) :]
        return None

    def _data(self, kind, key):
        if key in self.controller.store(kind):
            return self.controller.form_data(kind, key)
        page = default_pages(menu_rules(self.database))[key]  # the engine's own page
        return _with_defaults(FORMS[kind], page.to_data())

    def _selected(self, *_args):
        self.flush()
        entry = self.selected
        self.form, self._editing = None, None
        if entry is None:
            return
        choices = {c[0]: c for c in self.controller.references("pause_entries")}
        _id, name, why_not = choices[entry]
        record = self._record(entry)
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(10)
        title = QLabel(name)
        title.setObjectName("PauseEntryTitle")
        layout.addWidget(title)
        if entry in BUILT_IN_PAGES:
            kind_words = "Built-in entry · a menu page you can change"
        elif record is None:
            kind_words = "Built-in entry"
        elif record[0] == "menu_pages":
            kind_words = "Menu page"
        else:
            kind_words = "Event entry"
        kind_label = QLabel(translate(kind_words))
        kind_label.setObjectName("PauseEntryKind")
        layout.addWidget(kind_label)
        lines = []
        if entry in PAUSE_OPENS:
            lines.append(translate(PAUSE_OPENS[entry]))
        if why_not:
            not_yet = translate("Not in this game yet: shown once {0}.")
            lines.append(not_yet.format(translate(why_not)))
        if entry in self.order.hidden():
            lines.append(translate("Hidden: tick it in the list to show it."))
        if lines:
            about = QLabel("\n".join(lines))
            about.setWordWrap(True)
            about.setObjectName("PauseEntryAbout")
            layout.addWidget(about)
        if record is not None:
            self._form(layout, *record)
        buttons = QHBoxLayout()
        if record is not None and record[0] == "menu_pages" and self.open_layout is not None:
            # the page's blocks are here; where its frame, tabs and rows sit is the Layout's
            layout_link = QPushButton("Move It on the Screen (Layout)")
            layout_link.setToolTip(
                translate("Presentation ▸ Menu Screens ▸ Layout ▸ Status pages: the frame,")
                + " "
                + translate("tabs and rows the blocks are drawn in.")
            )
            layout_link.clicked.connect(lambda: self.open_layout("status"))
            buttons.addWidget(layout_link)
        if record is not None and record[1] in self.controller.store(record[0]):
            if entry in BUILT_IN_PAGES:
                reset = QPushButton("Back to the Engine's Page")
                reset.setToolTip(translate("Drop the changes: the page the engine draws."))
                reset.clicked.connect(lambda: self.delete_record(*record))
                buttons.addWidget(reset)
            else:
                words = "Delete Page" if record[0] == "menu_pages" else "Delete Entry"
                delete = QPushButton(words)
                delete.clicked.connect(lambda: self.delete_record(*record))
                buttons.addWidget(delete)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        layout.addStretch(1)
        swap_scroll_page(self.scroll, page)

    def _form(self, layout, kind, key):
        from .game_systems_widget import RecordForm

        fields = tuple(f for f in FORMS[kind] if f.key not in HIDDEN[kind])
        form = RecordForm(
            fields,
            self.controller.references,
            icons=self.controller.icon_library,
            document=self.controller.document,
        )
        form.set_data(self._data(kind, key))
        form.changed.connect(self._timer.start)
        layout.addWidget(form)
        self.form, self._editing = form, (kind, key)

    def apply(self):
        """Apply the form to its record (a built-in page's first change makes its record)."""
        self._timer.stop()
        if self.form is None or self._editing is None:
            return False
        kind, key = self._editing
        try:
            data = self.form.data()
            if key in self.controller.store(kind):
                self.controller.edit(kind, key, data)
            else:
                self.controller.create(kind, data)
        except _ERRORS as exc:
            self.report.emit(translate("⚠  Not applied: ") + str(exc), False)
            return False
        self.report.emit("", True)
        self.changed.emit()
        if kind == "menu_entries" or key not in BUILT_IN_PAGES:  # a new name in the list
            entry = (MENU_ENTRY if kind == "menu_entries" else PAGE_ENTRY) + key
            name = dict((c[0], c[1]) for c in self.controller.references("pause_entries"))
            for item in self.order._entries():
                if item.data(Qt.UserRole) == entry:
                    self.order.list.blockSignals(True)
                    item.setText(name[entry])
                    self.order.list.blockSignals(False)
        return True

    def flush(self):
        if self._timer.isActive():
            self.apply()

    # -- add and remove -------------------------------------------------------------------------
    def delete_record(self, kind, key):
        self._timer.stop()
        self.form, self._editing = None, None
        try:
            self.controller.delete(kind, key)
        except _ERRORS as exc:
            self.report.emit(str(exc), False)
            return False
        self.changed.emit()
        self.refresh()
        if menu_rules(self.database) is not None:
            self._save_order()  # the order without it
        return True

    def new_page(self, name):
        """A new menu page named ``name`` (one Item List block to start from)."""
        key = _new_id(name, self.controller.store("menu_pages"), "page")
        page = MenuPage(key, name, blocks=(MenuBlock("item_list"),))
        return self._create("menu_pages", page, PAGE_ENTRY + key)

    def new_entry(self, name):
        """A new event entry named ``name`` running the first event program."""
        programs = sorted(self.controller.project.event_programs.ids())
        if not programs:
            self.report.emit(translate("Make an event program first: the entry runs one."), False)
            return False
        key = _new_id(name, self.controller.store("menu_entries"), "entry")
        return self._create("menu_entries", MenuEntry(key, name, programs[0]), MENU_ENTRY + key)

    def _create(self, kind, record, entry):
        try:
            self.controller.create(kind, record)
        except _ERRORS as exc:
            self.report.emit(str(exc), False)
            return False
        self.changed.emit()
        self.refresh(entry)
        return True

    def _ask_name(self, title, prompt):
        name, ok = QInputDialog.getText(self, translate(title), translate(prompt))
        return name.strip() if ok and name.strip() else None

    def _new_page_clicked(self):
        name = self._ask_name("New Page", "The page's name (players see it in the pause menu):")
        if name:
            self.new_page(name)

    def _new_entry_clicked(self):
        name = self._ask_name(
            "New Event Entry", "The entry's name (players see it in the pause menu):"
        )
        if name:
            self.new_entry(name)
