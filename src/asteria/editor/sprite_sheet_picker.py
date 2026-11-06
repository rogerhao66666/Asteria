"""Sprite sheet fields and pictures: a fighter's battlefield picture as a list of the
project's sheets with their first frame; the framed picture box at the top of a record, which
a double-click changes; and the dialog that picks a picture by kind, from the project, from
its picture folders or from a file (picture_import brings a file in)."""

from __future__ import annotations

from pathlib import PurePosixPath

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .dialogue_command_dialog import _PortraitPicker
from .image_tools import SpriteSheetLibrary
from .picture_categories import CATEGORIES, OTHER, sheets_by_category
from .record_pictures import forget_pictures, framed, sprite_sheet_pixmap


class BattleCharacterLibrary(SpriteSheetLibrary):
    """The battle sheets that are characters (heroes and monsters), not effects."""

    def choices(self):
        choices = super().choices()
        kinds = sheets_by_category(self.document, tuple(sheet for sheet, _icon in choices))
        wanted = set(kinds.get("characters", ()))
        return tuple(choice for choice in choices if choice[0] in wanted)


class SpriteSheetPicker(_PortraitPicker):
    """A fighter's battlefield picture: a double-click opens the picture dialog (the battle
    characters, the project's folder, a file from anywhere)."""

    def __init__(self, document, parent=None):
        super().__init__(BattleCharacterLibrary(document), parent)
        self.preview.setToolTip("Double-click to choose the battlefield picture")
        self._shown()

    def choose(self):
        chosen = pick_sprite_sheet(self.library.document, self, battle=True)
        if chosen:
            self._fill()
            self.setText(chosen)

    def _show_name(self):
        self.name.setText(sheet_label(self.library.document, self.text()) or "None")
        self.name.setToolTip(self.text())

    def _shown(self, *_):
        document = getattr(self.library, "document", None)
        pixmap = sprite_sheet_pixmap(document, self.text()) if document is not None else None
        side = self.PREVIEW - 8
        if pixmap is None or pixmap.isNull():
            self.preview.setPixmap(None)
        else:  # without its empty margin, sharp pixels: as the record's own picture
            self.preview.setPixmap(framed(pixmap, side))
        self._show_name()
        self.changed.emit()


class WalkingSheetLibrary(SpriteSheetLibrary):
    """Every sprite sheet the editor has loaded for the project (the map's walking sheets
    among them), listed by the name of its file, with its first frame."""

    CACHE = "_walking_sheet_choices_cache"

    def choices(self):
        """The list, built again when the sheets the editor has loaded change."""
        views = getattr(self.document, "asset_views", None)
        stamp = tuple(views.sprite_sheet_ids()) if views is not None else ()
        holder = self.document if self.document is not None else self
        cached = getattr(holder, self.CACHE, None)
        if cached is not None and cached[0] == stamp:
            return cached[1]
        choices = self._build()
        setattr(holder, self.CACHE, (stamp, choices))
        return choices

    def _build(self):
        document = self.document
        views = getattr(document, "asset_views", None)
        if views is None:
            return ()
        choices = []
        for asset_id in views.sprite_sheet_ids():
            pixmap = sprite_sheet_pixmap(document, asset_id)
            icon = None
            if pixmap is not None and not pixmap.isNull():
                icon = QIcon(framed(pixmap, 48))
            choices.append((asset_id, icon))
        return tuple(choices)


def sheet_label(document, asset_id):
    """A sprite sheet's name for a list: its asset's name or file, not its id."""
    project = getattr(document, "project", None)
    record = project.assets.get(asset_id) if project is not None and asset_id else None
    if record is not None:
        name = getattr(record, "name", "") or ""
        source = getattr(record, "source_path", "") or ""
        name = name.removesuffix(" Sheet")  # every one is a sheet: the name says whose
        return name or source.rsplit("/", 1)[-1].rsplit(".", 1)[0] or asset_id
    fighter = str(asset_id).removeprefix("battle.combatant.")  # a battle sheet: its fighter
    return fighter.replace("_", " ").title() if fighter != asset_id else fighter


class PictureBox(QLabel):
    """A record's picture in a framed square; a double-click asks to change it."""

    doubleClicked = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("FormPortrait")
        self.setFixedSize(64, 64)
        self.setAlignment(Qt.AlignCenter)

    def setPixmap(self, pixmap):  # noqa: N802 - Qt API
        if pixmap is None or pixmap.isNull():
            super().setPixmap(QPixmap())
            # an empty frame says "None"; a small one beside its name (which says it) stays bare
            self.setText("None" if self.width() >= 56 else "")
        else:
            self.setText("")
            super().setPixmap(pixmap)

    def mouseDoubleClickEvent(self, event):  # noqa: N802 - Qt API
        self.doubleClicked.emit()
        event.accept()


class PicturePickerDialog(QDialog):
    """The project's pictures of one kind at a time (Characters first: heroes and monsters
    alike), as a grid of first frames; the pictures waiting in the project's folders for
    that kind; a picture file from anywhere (Browse…); and the folder to drop pictures in."""

    def __init__(
        self,
        document,
        parent=None,
        *,
        battle=False,
        category_id="characters",
        sheet_ids=None,
        fighter=None,
    ):
        from PySide6.QtWidgets import QHBoxLayout, QPushButton, QTabBar

        super().__init__(parent)
        self.document = document
        self.battle = bool(battle)
        self.chosen = None
        self.setWindowTitle("Choose a Picture")
        library = SpriteSheetLibrary(document) if battle else WalkingSheetLibrary(document)
        self._choices = dict(library.choices())
        # a fighter's picture (battle, no list of its own): every character the map shows
        # too, one picked made a battle sprite; a page's own list stays as it is
        self.fighter = bool(battle and sheet_ids is None) if fighter is None else fighter
        if self.fighter:
            self._choices = _with_map_sheets(document, self._choices)
        if sheet_ids is not None:  # only these (a page's own list), each with its picture
            wanted = set(sheet_ids)
            self._choices = {k: v for k, v in self._choices.items() if k in wanted}
        self._grouped = sheets_by_category(document, tuple(self._choices))
        column = QVBoxLayout(self)
        self.tabs = QTabBar(self)
        self.tabs.setDrawBase(False)
        self._tab_ids = []
        # a picture for a character shows characters only (heroes and monsters alike), never
        # map tiles or objects; ``category_id=None`` lists every kind, a tab each
        for kind in (*CATEGORIES, OTHER):
            count = len(self._grouped.get(kind.category_id, ()))
            if kind.category_id == category_id or (category_id is None and count):
                self.tabs.addTab(f"{kind.label} ({count})")
                self._tab_ids.append(kind.category_id)
        if category_id is None:
            self.tabs.addTab(f"All ({len(self._choices)})")
            self._tab_ids.append(None)
        self.tabs.setToolTip("Pictures sorted by kind; monsters are characters too")
        self.tabs.setVisible(self.tabs.count() > 1)  # one kind: no tabs to choose between
        column.addWidget(self.tabs)
        self.listing = QListWidget(self)
        self.listing.setViewMode(QListWidget.IconMode)
        self.listing.setIconSize(QSize(48, 48))
        self.listing.setGridSize(QSize(112, 88))
        self.listing.setResizeMode(QListWidget.Adjust)
        self.listing.setMovement(QListWidget.Static)
        self.listing.setUniformItemSizes(True)
        self.listing.setWordWrap(True)
        self.listing.setMinimumSize(560, 360)
        self.listing.itemDoubleClicked.connect(lambda _item: self.accept())
        column.addWidget(self.listing, 1)
        row = QHBoxLayout()
        self.browse_button = QPushButton("Browse…", self)
        self.browse_button.setToolTip(
            "A picture file from anywhere, copied into the project's characters folder"
            + ("" if battle else " (a 3x4 walking sheet: down, left, right, up)")
        )
        self.browse_button.clicked.connect(self.browse)
        self.folder_button = QPushButton("Open Pictures Folder", self)
        self.folder_button.setToolTip(
            "playable_assets/characters in the project: pictures put there show up here"
        )
        self.folder_button.clicked.connect(self.open_folder)
        row.addWidget(self.browse_button)
        row.addWidget(self.folder_button)
        row.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.ok_button.setEnabled(False)  # nothing picked yet: OK waits for a picture
        self.listing.itemSelectionChanged.connect(self._picked)
        row.addWidget(self.buttons)
        column.addLayout(row)
        self.tabs.currentChanged.connect(self._fill)
        start = self._tab_ids.index(category_id) if category_id in self._tab_ids else 0
        self.tabs.setCurrentIndex(start)
        self._fill()

    def category_id(self):
        return self._tab_ids[self.tabs.currentIndex()] if self._tab_ids else None

    def _fill(self, *_):
        from .picture_import import folder_pictures

        self.listing.clear()
        kind = self.category_id()
        ids = list(self._choices) if kind is None else self._grouped.get(kind, [])
        for sheet_id in ids:
            icon = self._choices.get(sheet_id)
            item = QListWidgetItem(icon or QIcon(), sheet_label(self.document, sheet_id))
            item.setData(Qt.UserRole, ("sheet", sheet_id))
            item.setToolTip(sheet_id)
            self.listing.addItem(item)
        for relative in folder_pictures(self.document, kind or "characters"):
            item = QListWidgetItem(
                self._file_icon(relative), PurePosixPath(relative).stem + "\n(new)"
            )
            item.setData(Qt.UserRole, ("file", relative))
            item.setToolTip(f"{relative}: in the project's folder, not used yet")
            self.listing.addItem(item)
        self.listing.setCurrentRow(-1)  # nothing picked until the author clicks a picture
        self.listing.clearSelection()
        self._picked()

    def picked(self):
        items = self.listing.selectedItems()
        return items[0] if items else None

    def _picked(self):
        self.ok_button.setEnabled(self.picked() is not None)

    def _file_icon(self, relative):
        from .picture_import import WALK_COLUMNS, WALK_ROWS, _project_dir

        pixmap = QPixmap(str(_project_dir(self.document) / relative))
        if pixmap.isNull():
            return QIcon()
        w, h = pixmap.width(), pixmap.height()
        if not self.battle and w % WALK_COLUMNS == 0 and h % WALK_ROWS == 0:
            fw, fh = w // WALK_COLUMNS, h // WALK_ROWS
            pixmap = pixmap.copy(fw, 0, fw, fh)  # standing, facing down
        return QIcon(framed(pixmap, 48))

    def accept(self):
        item = self.picked()
        if item is None:  # OK is off until a picture is picked
            return None
        kind, value = item.data(Qt.UserRole)
        chosen = value if kind == "sheet" else self._import(value)
        if chosen and kind == "sheet" and self.fighter:
            chosen = self._battle_sheet(value)
        if chosen:
            self.chosen = chosen
            super().accept()

    def _battle_sheet(self, sheet_id):
        """A map sheet picked for the battlefield, as a battle sprite (picture_import)."""
        from PySide6.QtWidgets import QMessageBox

        from .picture_import import PictureImportError, battle_sheet_for

        try:
            chosen = battle_sheet_for(self.document, sheet_id)
        except (PictureImportError, OSError) as exc:
            QMessageBox.warning(self, "Picture", str(exc))
            return None
        if chosen != sheet_id:
            resolve_pictures(self.document, self.parent())
        return chosen

    def browse(self):
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(self, "Picture", "", "Images (*.png)")
        if path:
            chosen = self._import(path)
            if chosen:
                self.chosen = chosen
                super().accept()

    def _import(self, path):
        """``path`` made a picture of the project; its sheet id, or None (said why)."""
        from PySide6.QtWidgets import QMessageBox

        from .picture_import import (
            PictureImportError,
            import_battle_picture,
            import_walking_picture,
        )

        try:
            if self.battle:
                chosen = import_battle_picture(self.document, path)
            else:
                chosen = import_walking_picture(self.document, path)
        except (PictureImportError, OSError) as exc:
            QMessageBox.warning(self, "Picture", str(exc))
            return None
        resolve_pictures(self.document, self.parent())
        return chosen

    def open_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices
        from PySide6.QtWidgets import QMessageBox

        from .picture_import import CHARACTER_FOLDER, PictureImportError, _project_dir

        try:
            folder = _project_dir(self.document) / CHARACTER_FOLDER
        except PictureImportError as exc:
            QMessageBox.information(self, "Picture", str(exc))
            return
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def _with_map_sheets(document, battle_choices):
    """The battle sprites and every sheet the map has loaded, without a picture twice (a
    battle sprite made from a map sheet stands for it)."""
    project = getattr(document, "project", None)
    views = getattr(document, "asset_views", None)
    if project is None or views is None:
        return dict(battle_choices)
    known = {a.asset_id: a for a in project.assets.snapshot()}
    drawn = {known[k].source.uri for k in battle_choices if k in known}
    merged = dict(battle_choices)
    for sheet_id, icon in WalkingSheetLibrary(document).choices():
        try:
            texture = project.assets.get(str(views.sprite_sheet(sheet_id).texture.asset_id))
        except Exception:  # noqa: BLE001 - a sheet that cannot be read is left out
            continue
        if texture is not None and str(texture.source_path) not in drawn:
            merged[sheet_id] = icon
    return merged


class SheetPickerBox(QWidget):
    """A sprite sheet field of a page (Character Composition, Battle Effects): the sheet's
    first frame in a framed square and its name; a double-click opens the picture dialog with
    that field's kind only (``category_id``) - any other picture comes by Browse… there."""

    changed = Signal()

    def __init__(self, document, category_id, parent=None, *, title="Choose a Picture"):
        from PySide6.QtWidgets import QHBoxLayout

        super().__init__(parent)
        self.document = document
        self.category_id = category_id
        self.title = title
        self._value = ""
        self.sheet_ids = None  # the sheets the page offers (None: every sheet of the kind)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.preview = PictureBox()
        self.preview.setFixedSize(44, 44)
        self.preview.setToolTip("Double-click to choose a picture")
        self.preview.doubleClicked.connect(self.choose)
        self.name = QLabel()
        row.addWidget(self.preview, 0, Qt.AlignVCenter)
        row.addWidget(self.name, 1)
        self._shown()

    def set_choices(self, sheet_ids):
        self.sheet_ids = tuple(sheet_ids)

    def choose(self):
        dialog = PicturePickerDialog(
            self.document,
            self,
            battle=True,
            category_id=self.category_id,
            sheet_ids=None if self.sheet_ids is None else self.sheet_ids,
            fighter=False,  # worn things and layers are drawn as they are
        )
        dialog.setWindowTitle(self.title)
        if dialog.exec() == QDialog.Accepted and dialog.chosen:
            self.set_value(dialog.chosen)

    def value(self):
        return self._value

    currentData = value  # noqa: N815 - read as the combo box it replaces
    currentText = value  # noqa: N815

    def set_value(self, sheet_id):
        sheet_id = str(sheet_id or "")
        changed = sheet_id != self._value
        self._value = sheet_id
        self._shown()
        if changed:
            self.changed.emit()

    def _shown(self):
        pixmap = sprite_sheet_pixmap(self.document, self._value) if self._value else None
        side = self.preview.width() - 6
        if pixmap is None or pixmap.isNull():
            self.preview.setPixmap(None)
        else:
            self.preview.setPixmap(framed(pixmap, side))
        self.name.setText(sheet_label(self.document, self._value) if self._value else "None")
        self.name.setToolTip(self._value)


def resolve_pictures(document, widget=None):
    """The editor's sprite sheets loaded again after a picture came in: through the main
    window when there is one (its map view drops its textures too), else the document's."""
    window = widget.window() if widget is not None else None
    if window is not None and hasattr(window, "_resolve_project_resources"):
        window._resolve_project_resources()
    else:
        from .resource_resolver import resolve_project_resources

        resolve_project_resources(document)

    forget_pictures()


def pick_sprite_sheet(document, parent=None, *, battle=False):
    """A dialog of the project's pictures, sorted by kind and starting at Characters: the
    battle sheets (``battle``) or the map's; the chosen sheet's id, or None."""
    dialog = PicturePickerDialog(document, parent, battle=battle)
    if dialog.exec() != QDialog.Accepted:
        return None
    return dialog.chosen
