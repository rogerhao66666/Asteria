"""Search everything (⌘K / Ctrl+K): every page of the editor, every record of the database,
battle and presentation (actors, items, skills, combatant sprites…), every game system record,
every scene and every entity on it - typed words in any order, names or ids. Choosing a result
opens its page with it selected, as a problem's jump does (``navigate_to_problem``)."""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QVBoxLayout

from .i18n import translate
from .workspace import WorkspaceMode

MAX_SHOWN = 200


@dataclass(frozen=True, slots=True)
class SearchEntry:
    title: str
    detail: str  # where it is: "Game Data ▸ Actors · hero_01"
    target: tuple = ()  # a problem target (navigate_to_problem), or
    page: tuple = ()  # (workspace mode, tab widget, page widget) of an editor page

    def words(self):
        return f"{self.title} {self.detail}".lower()


def _name(record, record_id):
    for field in ("display_name", "name", "title"):
        value = getattr(record, field, None)
        if isinstance(value, str) and value.strip():
            return value
    return str(record_id)


def _records(window, family, label, builder):
    entries = []
    try:
        adapters = builder()
    except Exception:  # noqa: BLE001 - a family that cannot be read is left out
        return entries
    for adapter in adapters:
        try:
            ids = adapter.ids()
        except Exception:  # noqa: BLE001
            continue
        for record_id in ids:
            try:
                title = _name(adapter.get(record_id), record_id)
            except Exception:  # noqa: BLE001
                title = str(record_id)
            entries.append(
                SearchEntry(
                    title,
                    f"{label} ▸ {adapter.label} · {record_id}",
                    ("record", family, adapter.category_id, record_id),
                )
            )
    return entries


def _pages(window):
    entries = []
    for mode, tabs in (
        (WorkspaceMode.RPG, getattr(window, "rpg_workspace", None)),
        (WorkspaceMode.UI, getattr(window, "ui_workspace", None)),
    ):
        if tabs is None:
            continue
        workspace = "Database" if mode == WorkspaceMode.RPG else "Presentation"
        for index in range(tabs.count()):
            name = tabs.tabText(index).replace("&", "")
            entries.append(SearchEntry(name, f"Page · {workspace}", (), (mode, tabs, index)))
    for mode, name in (
        (WorkspaceMode.SCENE, "Scene"),
        (WorkspaceMode.BATTLE, "Battle"),
        (WorkspaceMode.EVENT, "Events"),
        (WorkspaceMode.CODE, "Code"),
        (WorkspaceMode.MULTIPLAYER, "Multiplayer"),
    ):
        entries.append(SearchEntry(name, "Workspace", (), (mode, None, None)))
    return entries


def search_entries(window):
    """Everything the editor can open, as SearchEntry rows (built when the search opens)."""
    document = window.document
    project = document.project
    entries = _pages(window)
    if project is None:
        return entries
    controllers = window.authoring_controllers
    for family, label, builder in (
        ("rpg", "Game Data", controllers.rpg_categories),
        ("battle", "Battle Rules", controllers.battle_categories),
        ("presentation", "Battle Presentation", controllers.presentation_categories),
    ):
        entries.extend(_records(window, family, label, builder))
    systems = window.game_systems_editor.controller
    for kind in systems.kinds:
        try:
            ids = systems.ids(kind.kind_id)
        except Exception:  # noqa: BLE001
            continue
        for record_id in ids:
            try:
                title = _name(systems.get(kind.kind_id, record_id), record_id)
            except Exception:  # noqa: BLE001
                title = str(record_id)
            entries.append(
                SearchEntry(
                    title,
                    f"Game Systems ▸ {kind.label} · {record_id}",
                    ("game_system", kind.kind_id, record_id),
                )
            )
    for scene in project.scenes():
        entries.append(SearchEntry(scene.name, "Scene", ("scene", scene.id)))
        for entity in scene.entities():
            entries.append(
                SearchEntry(entity.name, f"Entity · {scene.name}", ("entity", scene.id, entity.id))
            )
    return entries


def shown_detail(detail):
    """``detail`` in the editor's language, part by part ("Game Data ▸ Actors · hero_01")."""

    return " ▸ ".join(
        " · ".join(translate(part) for part in side.split(" · ")) for side in detail.split(" ▸ ")
    )


def matches(entries, text):
    """The entries holding every typed word (names first: a word at the start of the title
    ranks highest), at most MAX_SHOWN."""
    words = text.lower().split()
    if not words:
        return list(entries[:MAX_SHOWN])
    found = [entry for entry in entries if all(word in entry.words() for word in words)]

    def rank(entry):
        title = entry.title.lower()
        return (
            0 if title.startswith(words[0]) else 1 if words[0] in title else 2,
            len(title),
        )

    return sorted(found, key=rank)[:MAX_SHOWN]


def open_entry(window, entry):
    """Open ``entry``'s page (and select it); True when it opened."""
    if entry.target:
        from types import SimpleNamespace

        return bool(window.navigate_to_problem(SimpleNamespace(target=entry.target)))
    mode, tabs, index = entry.page
    window.workspace.set_mode(mode)
    if tabs is not None:
        tabs.setCurrentIndex(index)
    return True


class GlobalSearchDialog(QDialog):
    """A search box over everything; Return or a double-click opens the chosen row."""

    def __init__(self, window):
        super().__init__(window)
        self.window_ = window
        self.setObjectName("GlobalSearch")
        self.setWindowTitle("Search Everything")
        self.setModal(True)
        self.resize(640, 460)
        self.entries = search_entries(window)
        column = QVBoxLayout(self)
        self.field = QLineEdit(self)
        self.field.setObjectName("GlobalSearchField")
        self.field.setPlaceholderText("Search pages, records, scenes and entities…")
        self.field.setClearButtonEnabled(True)
        self.field.textChanged.connect(self._fill)
        self.field.returnPressed.connect(self.open_current)
        column.addWidget(self.field)
        self.results = QListWidget(self)
        self.results.setObjectName("GlobalSearchResults")
        self.results.setUniformItemSizes(True)
        self.results.itemActivated.connect(lambda _item: self.open_current())
        column.addWidget(self.results, 1)
        self.count = QLabel(self)
        self.count.setObjectName("MutedLabel")
        column.addWidget(self.count)
        self.field.installEventFilter(self)
        self._fill()

    def eventFilter(self, watched, event):  # noqa: N802 - Qt API
        from PySide6.QtCore import QEvent

        if watched is self.field and event.type() == QEvent.KeyPress:
            step = {Qt.Key_Down: 1, Qt.Key_Up: -1}.get(event.key())
            if step and self.results.count():  # the arrows move in the list from the box
                row = max(0, min(self.results.count() - 1, self.results.currentRow() + step))
                self.results.setCurrentRow(row)
                return True
        return super().eventFilter(watched, event)

    def _fill(self, *_):
        self.results.clear()
        shown = matches(self.entries, self.field.text())
        for entry in shown:
            item = QListWidgetItem(f"{entry.title}\n{shown_detail(entry.detail)}")
            item.setData(Qt.UserRole, entry)
            item.setSizeHint(QSize(0, 40))
            self.results.addItem(item)
        if self.results.count():
            self.results.setCurrentRow(0)
        self.count.setText(f"{len(shown)} shown · {len(self.entries)} in the project")

    def open_current(self):
        item = self.results.currentItem()
        if item is None:
            return False
        entry = item.data(Qt.UserRole)
        self.accept()
        return open_entry(self.window_, entry)
