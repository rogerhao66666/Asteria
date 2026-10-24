"""The Translations page of a locale table: every word the game's own screens draw, by key.

The rows are the engine's built-in words (``rpg.built_in_text``: grouped by screen, each with the
English it shows), the project's own names the engine's screens draw (input actions on the
Controls screen, Command Menu Pages labels and skill groups in the battle menu), the project's
data (D60, ``editor/data_translation.py``: every record's name and description, maps,
currencies, who speaks and the dialogue lines that have a key; collapsed until searched), and
the table's own keys (``\\T[key]`` in messages, anything else the project looks up). A
row's Text is what the game shows for that key in this table's locale; an empty Text keeps the
English, so a table never has to list every word. Built-in keys are never locked: in the
default locale's table they rename a word (``Fight`` for Attack).

``set_rows`` / ``values`` take and give the form's rows (``{"key", "text"}``), like the other
table fields of ``game_systems_widget.RecordForm``.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.rpg.built_in_text import GROUPS, engine_translations

from . import data_translation
from .flow_layout import FlowLayout
from .i18n import translate

OWN_GROUP = "This project's own keys"
ACTIONS_GROUP = "Controls: input action names"
LAYERS_GROUP = "Battle: Command Menu Pages names"
SKILL_GROUPS = "Battle: the project's skill groups"
ENTRIES_GROUP = "Pause menu: the project's own entries"
DATA_PREFIXES = ("data.", "dlg.")  # project data rows (D60): names, descriptions, dialogue


def _is_data(key):
    return str(key).startswith(DATA_PREFIXES)


SHOWN = (  # the Show filter: (label, test of a row's (key, english, text, own))
    ("All words", lambda key, english, text, own: True),
    ("Not translated yet", lambda key, english, text, own: not text),
    ("Translated", lambda key, english, text, own: bool(text)),
    ("Engine words", lambda key, english, text, own: not own and not _is_data(key)),
    ("Project data", lambda key, english, text, own: _is_data(key) and not own),
    ("This project's own keys", lambda key, english, text, own: own),
)
GROUP_ICONS = {  # editor icons (icons.py) beside each group of the tree
    "Title screen": "flag",
    "Field": "scene",
    "Dialogue": "dialogue",
    "Pause menu": "list",
    "Game over": "warning",
    "Settings": "settings",
    "Controls": "input",
    ACTIONS_GROUP: "input",
    LAYERS_GROUP: "battle",
    ENTRIES_GROUP: "list",
    SKILL_GROUPS: "skill",
    "Save and load": "save",
    "Status menu": "actor",
    "Quest log": "quest",
    "Shop": "chest",
    "Crafting": "hammer",
    "Achievements and bestiary": "trophy",
    "Message log, music room, credits": "audio",
    "Skill slots": "skill",
    "Pets": "paw",
    "Battle commands": "battle",
    "Battle: why a command cannot be used": "warning",
    "Battle": "battle",
    "Capture": "target",
    "Victory": "banner",
    "Equipment bag (action games)": "armor",
    "Skill tree (action games)": "skill",
    "Action HUD": "gauge",
    "Build menu (testing)": "class",
    "Equipment and enhance": "hammer",
    "Co-op": "multiplayer",
    OWN_GROUP: "project",
    "Data: actors": "actor",
    "Data: classes": "class",
    "Data: skills": "skill",
    "Data: passives": "skill",
    "Data: states": "state",
    "Data: items": "item",
    "Data: equipment": "armor",
    "Data: socketed items": "item",
    "Data: equipment sets": "armor",
    "Data: equipment growth": "hammer",
    "Data: rarities and affixes": "banner",
    "Data: enemies": "enemy",
    "Data: pet species": "paw",
    "Data: quests": "quest",
    "Data: shops": "chest",
    "Data: crafting recipes": "hammer",
    "Data: skill trees": "skill",
    "Data: progression tracks": "gauge",
    "Data: stats": "gauge",
    "Data: factions and achievements": "trophy",
    "Data: world interactions": "target",
    "Data: party setups and drop tables": "list",
    data_translation.MAPS_GROUP: "scene",
    data_translation.CURRENCY_GROUP: "chest",
    data_translation.SLOTS_GROUP: "armor",
    data_translation.SPEAKERS_GROUP: "dialogue",
    data_translation.LINES_GROUP: "dialogue",
}
_KEY = Qt.UserRole  # a row's key; a group row holds its English title instead
_GROUP = Qt.UserRole + 1


class _ShareTree(QTreeWidget):
    """The three columns share the width (Key 30 %, English 33 %, Text the rest), so a narrow
    window never scrolls sideways; a column dragged wider stays so until the next resize."""

    SHARES = (0.30, 0.33)

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        width = self.viewport().width()
        header = self.header()
        header.setStretchLastSection(True)
        for column, share in enumerate(self.SHARES):
            header.setSectionResizeMode(column, QHeaderView.Interactive)
            header.resizeSection(column, max(80, int(width * share)))


def _icon(name, color=None):
    from .icons import icon

    return icon(name, color)


class TranslationTable(QWidget):
    """Search, a Show filter, Fill from the engine's translation, and the grouped rows."""

    changed = Signal()

    def __init__(self, document=None, parent=None):
        super().__init__(parent)
        self.document = document  # its project's input actions are listed too
        self.locale = ""
        self.texts = {}  # key -> text this table gives it (no empty ones)
        self.own = []  # the table's keys that are not built-in, in order
        self._loading = False

        intro = QLabel(
            "Every word the game's own screens draw. Type a row's Text to show it in this "
            "language; an empty Text keeps the English (a space hides the word). {name} marks "
            "a value the game fills in. The table is used when it is the Default Locale "
            "(Message Settings) or the player picks it in Settings ▸ Language."
        )
        intro.setWordWrap(True)
        intro.setObjectName("FieldHint")

        self.search = QLineEdit()
        self.search.setPlaceholderText("Search keys, English or text")
        self.search.setClearButtonEnabled(True)
        self.search.addAction(_icon("search"), QLineEdit.LeadingPosition)
        self.search.textChanged.connect(self._filter)
        self.show_box = QComboBox()
        for label, _test in SHOWN:
            self.show_box.addItem(label, label)
        self.show_box.currentIndexChanged.connect(self._filter)
        self.fill = QPushButton(_icon("apply", "#3fae7a"), "Fill empty rows")
        self.fill.clicked.connect(self.fill_from_engine)
        self.add = QPushButton(_icon("add", "#6a83e8"), "Add key")
        self.add.setToolTip("A key of the project's own (\\T[key] in a message, for one)")
        self.add.clicked.connect(self.add_key)
        self.remove = QPushButton(_icon("delete", "#de5a62"), "Remove key")
        self.remove.setToolTip("Remove the selected project key, or clear a built-in row")
        self.remove.clicked.connect(self.remove_selected)
        self.keys = QPushButton(_icon("dialogue", "#d68a3c"), "Give dialogue lines keys")
        self.keys.clicked.connect(self.give_dialogue_keys)
        self.tree = _ShareTree()
        self.tree.setColumnCount(3)
        self.tree.setHeaderLabels(["Key", "English", "Text"])
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setSelectionMode(QAbstractItemView.SingleSelection)
        # only a row's Text (and a project key's own Key) opens for typing
        self.tree.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tree.itemDoubleClicked.connect(self._open)
        self.tree.itemActivated.connect(lambda item, _column: self._open(item, 2))
        self.tree.setMinimumHeight(360)
        self.tree.itemChanged.connect(self._edited)
        # View ▸ Language puts the headers in the new language: the group rows follow
        self.tree.model().headerDataChanged.connect(lambda *_: self._retitle())

        self.count = QLabel("")
        self.count.setObjectName("FieldHint")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(intro)
        find = QHBoxLayout()
        layout.addLayout(find)
        find.setSpacing(6)
        find.addWidget(self.search, 1)
        find.addWidget(self.show_box)
        buttons = FlowLayout(spacing=6)  # in a narrow window the buttons wrap
        layout.addLayout(buttons)  # added empty, then filled (see ui_fit.layout_widgets)
        for button in (self.fill, self.add, self.remove, self.keys):
            buttons.addWidget(button)
        layout.addWidget(self.tree, 1)
        layout.addWidget(self.count)

    def hasHeightForWidth(self):  # noqa: N802 - Qt API
        return False  # like the other table fields: its plain minimum height

    # -- the rows ---------------------------------------------------------------------------
    def _project_words(self):
        """``[(title, [(key, english)])]``: the project's own names that the engine's screens
        draw - input actions (Controls), Command Menu Pages labels and skill groups (battle)."""
        project = getattr(self.document, "project", None)
        input_map = getattr(project, "input_map", None)
        actions = list(input_map.actions()) if input_map is not None else []
        words = [(ACTIONS_GROUP, [(f"controls.action.{a}", a) for a in [*actions, "reset_all"]])]
        layers, groups = {}, {}
        library = getattr(project, "battle_presentation_library", None)
        try:
            pages = [library.require("interaction", i) for i in library.ids("interaction")]
        except (AttributeError, KeyError, ValueError):
            pages = []
        for profile in pages:
            for layer in getattr(profile, "layers", ()):
                layers.setdefault(f"battle.layer.{layer.layer_id}", layer.label)
        abilities = getattr(getattr(project, "gameplay_library", None), "abilities", None)
        for ability_id in abilities.ids() if abilities is not None else ():
            name = getattr(abilities.get(ability_id), "menu_category", "")
            if name:
                groups.setdefault(f"battle.group.{name}", name)
        entries = getattr(getattr(project, "rpg_database", None), "menu_entries", None) or {}
        if entries:
            rows = [(f"pause.entry.{key}", entry.label) for key, entry in sorted(entries.items())]
            words.insert(0, (ENTRIES_GROUP, rows))
        if layers:
            words.append((LAYERS_GROUP, sorted(layers.items())))
        if groups:
            words.append((SKILL_GROUPS, sorted(groups.items())))
        return words

    def _project(self):
        return getattr(self.document, "project", None)

    def _data(self):
        """The project's data rows (``data_translation.data_groups``), worked out again when
        the rows are set or the document changed (an undo of Give dialogue lines keys...)."""
        stamp = (id(self._project()), getattr(self.document, "revision", None))
        cached = getattr(self, "_data_cache", None)
        if cached is None or cached[0] != stamp:
            cached = self._data_cache = (stamp, data_translation.data_groups(self._project()))
        return cached[1]

    def _known(self):
        known = {key for _, rows in GROUPS for key, _ in rows}
        known.update(key for _, rows in self._project_words() for key, _ in rows)
        known.update(key for _, rows in self._data() for key, _ in rows)
        return known

    def _groups(self):
        """``[(title, [(key, english)], own)]`` in the order the tree shows them."""
        known = self._known()
        own = [k for k in self.own if k not in known]
        groups = [(OWN_GROUP, [(k, "") for k in own], True)] if own else []
        groups += [(title, list(rows), False) for title, rows in GROUPS]
        groups += [(title, rows, False) for title, rows in self._project_words()]
        groups += [(title, rows, False) for title, rows in self._data()]
        return groups

    def set_rows(self, rows, locale=""):
        self.locale = str(locale or "")
        self.texts, self.own = {}, []
        self._data_cache = None
        known = self._known()
        for row in rows or ():
            key, text = str(row.get("key", "")).strip(), str(row.get("text", ""))
            if not key:
                continue
            if text != "":
                self.texts[key] = text
            derived = key.startswith(
                ("controls.action.", "battle.layer.", "battle.group.", "pause.entry.")
            )
            # a data key whose record is gone stays listed (with the project's own keys)
            if key not in known and not derived and key not in self.own:
                self.own.append(key)
        self._build()

    def values(self):
        """The table's rows: every key that has a Text (an empty one would show nothing)."""
        return [{"key": k, "text": v} for k, v in self.texts.items() if v != ""]

    def _build(self):
        self._loading = True
        self.tree.clear()
        bold = QFont()
        bold.setBold(True)
        data_titles = {title for title, _rows in self._data()}
        for title, rows, own in self._groups():
            group = QTreeWidgetItem([translate(title), "", ""])
            group.setData(0, _GROUP, title)
            group.setFlags(Qt.ItemIsEnabled)
            group.setFont(0, bold)
            group.setIcon(0, _icon(GROUP_ICONS.get(title, "list")))
            self.tree.addTopLevelItem(group)
            group.setFirstColumnSpanned(True)
            group.addChildren([self._row(key, english, own) for key, english in rows])
            group.setData(1, _GROUP, title in data_titles)  # data: collapsed until searched
            group.setExpanded(title not in data_titles)
        self._loading = False
        self._filter()

    def _row(self, key, english, own):
        text = self.texts.get(key, "")
        item = QTreeWidgetItem([key, english, text])
        item.setData(0, _KEY, key)
        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsEditable
        item.setFlags(flags)
        item.setToolTip(0, key)  # a narrow column shortens them: the whole of each on hover
        item.setToolTip(1, english)
        item.setForeground(1, QBrush(QColor("#8f96a3")))
        self._mark(item)
        item.setData(2, Qt.UserRole, own)  # a project's own key: its Key can be edited too
        return item

    def _mark(self, item):
        done = bool(item.text(2))
        item.setIcon(0, _icon("apply", "#3fae7a") if done else _icon("dialogue", "#8f96a3"))
        item.setToolTip(2, item.text(2))

    def _retitle(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            title = group.data(0, _GROUP)
            if title:
                group.setText(0, translate(title))

    # -- editing ----------------------------------------------------------------------------
    def _open(self, item, column):
        if item is None or item.parent() is None:
            return
        if column == 0 and not item.data(2, Qt.UserRole):
            column = 2  # a built-in key is fixed: typing goes to its Text
        if column == 1:
            column = 2
        self.tree.editItem(item, column)

    def _edited(self, item, column):
        if self._loading or item.parent() is None:
            return
        key = item.data(0, _KEY)
        own = bool(item.data(2, Qt.UserRole))
        if column == 0:
            new = item.text(0).strip()
            if not own or not new or new == key or new in self.texts or new in self.own:
                self._loading = True  # built-in keys stay; a clash or an empty key is undone
                item.setText(0, key)
                self._loading = False
                return
            self.own[self.own.index(key)] = new
            if key in self.texts:
                self.texts[new] = self.texts.pop(key)
            self._loading = True  # the row's own data changes: no edit of its own
            item.setData(0, _KEY, new)
            item.setToolTip(0, new)
            self._loading = False
        elif column == 2:
            text = item.text(2)
            if text != "":
                self.texts[key] = text
            else:
                self.texts.pop(key, None)
            self._loading = True
            self._mark(item)
            self._loading = False
        else:
            return
        self._count()
        self.changed.emit()

    def fill_from_engine(self):
        """Every empty built-in row gets the engine's own translation for this locale; a
        project name that is a built-in word (a Command Menu Pages label "Skills") gets that
        word's."""
        found = engine_translations(self.locale)
        by_english = {}
        for _title, rows in GROUPS:
            for key, english in rows:
                if key.startswith(("battle.command.", "battle.menu.")) and key in found:
                    by_english.setdefault(english, found[key])
        for _title, rows in self._project_words():
            for key, english in rows:
                if english in by_english:
                    found.setdefault(key, by_english[english])
        added = 0
        for key, text in found.items():
            if key not in self.texts:
                self.texts[key] = text
                added += 1
        if added:
            self._build()
            self.changed.emit()
        return added

    def add_key(self):
        name, number = "new.key", 1
        while name in self.own or name in self.texts:
            number += 1
            name = f"new.key{number}"
        self.own.append(name)
        self._build()
        for item in self._items():
            if item.data(0, _KEY) == name:
                self.tree.setCurrentItem(item)
                self.tree.editItem(item, 0)
        self.changed.emit()
        return name

    def give_dialogue_keys(self):
        """Put a key on every dialogue line, choice and prompt of the project's events that has
        none (one undoable step), so each can be translated here; returns how many programs
        changed."""
        project = self._project()
        execute = getattr(self.document, "execute", None)
        changes = data_translation.keyed_programs(project) if project is not None else []
        if not changes or execute is None:
            return 0
        from .commands import CommandTransaction
        from .event_editing import ReplaceEventProgramCommand

        tx = CommandTransaction("Give Dialogue Lines Keys")
        for program_id, new, old in changes:
            tx.add(ReplaceEventProgramCommand(project.event_programs, program_id, new, old))
        execute(tx)
        self._build()
        return len(changes)

    def remove_selected(self):
        item = self.tree.currentItem()
        if item is None or item.parent() is None:
            return False
        key = item.data(0, _KEY)
        self.texts.pop(key, None)
        if key in self.own:
            self.own.remove(key)
        self._build()
        self.changed.emit()
        return True

    # -- showing ----------------------------------------------------------------------------
    def _items(self):
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            for j in range(group.childCount()):
                yield group.child(j)

    def _filter(self, *_):
        words = self.search.text().strip().casefold()
        test = dict(SHOWN).get(self.show_box.currentData(), SHOWN[0][1])
        for i in range(self.tree.topLevelItemCount()):
            group = self.tree.topLevelItem(i)
            shown = 0
            for j in range(group.childCount()):
                item = group.child(j)
                own = bool(item.data(2, Qt.UserRole))
                cells = (item.text(0), item.text(1), item.text(2))
                visible = test(*cells, own) and (
                    not words or any(words in c.casefold() for c in cells)
                )
                item.setHidden(not visible)
                shown += visible
            group.setHidden(shown == 0)
            if group.data(1, _GROUP):  # project data: open while a search finds rows in it
                group.setExpanded(bool(words) and shown > 0)
        self.fill.setEnabled(bool(engine_translations(self.locale)))
        self.fill.setToolTip(
            "Copy the engine's own translation of its words into the empty rows"
            if self.fill.isEnabled()
            else "The engine has no translation of its own words for this locale"
        )
        project = self._project()
        missing = data_translation.dialogue_without_keys(project) if project is not None else 0
        self.keys.setEnabled(bool(missing) and hasattr(self.document, "execute"))
        self.keys.setToolTip(
            f"{missing} dialogue lines or choices have no key yet: give them keys so they can "
            "be translated here"
            if missing
            else "Every dialogue line and choice already has a key"
        )
        self._count()

    def _count(self):
        built_in = sum(len(rows) for _, rows in GROUPS)
        done = sum(1 for _, rows in GROUPS for key, _ in rows if key in self.texts)
        data = [key for _, rows in self._data() for key, _ in rows]
        data_done = sum(1 for key in data if key in self.texts)
        self.count.setText(
            f"{built_in} engine words · {done} translated · {len(self.own)} project keys · "
            f"{len(data)} data texts · {data_done} translated"
        )


__all__ = ["TranslationTable"]
