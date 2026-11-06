"""Choose an icon (or a portrait) the way a character's picture is chosen
(PicturePickerDialog): the field's own kind of picture only, as a grid with a filter; nothing
picked until the author clicks one (OK waits for it); Browse… for any other picture file and
the project's folder to drop pictures in. None empties the field."""

from __future__ import annotations

import re

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from .record_vocabulary import words


def icon_name(icon_id):
    """A picture's name in words: ``icon.alchemy_salt`` → "Alchemy Salt", ``…/I_Clock.png``
    → "Clock" (the pack's one-letter prefix dropped); the tooltip keeps the whole id."""

    name = icon_id.rsplit("/", 1)[-1].removeprefix("icon.")
    name = name.rsplit(".", 1)[0] if name.lower().endswith(".png") else name
    name = re.sub(r"^[A-Za-z]_(?=[A-Za-z])", "", name)  # I_Clock, S_Fire
    return words(name.replace("-", " "))


class IconPickerDialog(QDialog):
    def __init__(self, library, parent=None, *, current="", title="Choose an Icon"):
        super().__init__(parent)
        self.library = library
        self.chosen = None  # the picture id; "" after None
        self.current = current
        self.setWindowTitle(title)
        # the field's own kind only (an icon field: icons; a portrait: portraits); any other
        # picture comes by Browse…
        self._choices = list(library.choices()) if library is not None else []
        column = QVBoxLayout(self)
        self.filter = QLineEdit(self)
        self.filter.setPlaceholderText("Filter by name…")
        self.filter.setClearButtonEnabled(True)
        self.filter.textChanged.connect(self._fill)
        column.addWidget(self.filter)
        self.listing = QListWidget(self)
        self.listing.setViewMode(QListWidget.IconMode)
        self.listing.setIconSize(QSize(40, 40))
        self.listing.setGridSize(QSize(132, 84))  # "accessory_01" whole
        self.listing.setResizeMode(QListWidget.Adjust)
        self.listing.setMovement(QListWidget.Static)
        self.listing.setUniformItemSizes(True)
        self.listing.setWordWrap(True)
        self.listing.setMinimumSize(680, 380)
        self.listing.itemDoubleClicked.connect(lambda _item: self.accept())
        column.addWidget(self.listing, 1)
        row = QHBoxLayout()
        self.browse_button = QPushButton("Browse…", self)
        self.browse_button.setToolTip("A picture file from anywhere, copied into the project")
        self.browse_button.clicked.connect(self.browse)
        self.folder_button = QPushButton("Open Folder", self)
        folder = getattr(library, "FOLDER", "icons")
        self.folder_button.setToolTip(f"{folder} in the project: pictures put there show up here")
        self.folder_button.clicked.connect(self.open_folder)
        self.none_button = QPushButton("None", self)
        self.none_button.setToolTip("Leave the field without a picture")
        self.none_button.clicked.connect(self.choose_none)
        row.addWidget(self.browse_button)
        row.addWidget(self.folder_button)
        row.addWidget(self.none_button)
        row.addStretch(1)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.ok_button = self.buttons.button(QDialogButtonBox.Ok)
        self.listing.itemSelectionChanged.connect(self._picked)
        row.addWidget(self.buttons)
        column.addLayout(row)
        self._fill()

    def _fill(self, *_):
        self.listing.clear()
        words = self.filter.text().lower().split()
        namer = self.library.name_of if self.library is not None else icon_name
        for icon_id, icon in self._choices:
            name = namer(icon_id)
            if words and not all(w in f"{icon_id} {name}".lower() for w in words):
                continue
            item = QListWidgetItem(icon, name) if icon else QListWidgetItem(name)
            item.setData(Qt.UserRole, icon_id)
            item.setToolTip(icon_id)
            self.listing.addItem(item)
        self.listing.setCurrentRow(-1)  # nothing picked until the author clicks an icon
        self.listing.clearSelection()
        self._picked()

    def picked(self):
        items = self.listing.selectedItems()
        return items[0] if items else None

    def _picked(self):
        self.ok_button.setEnabled(self.picked() is not None)

    def accept(self):
        item = self.picked()
        if item is None:  # OK is off until an icon is picked
            return None
        self.chosen = str(item.data(Qt.UserRole))
        return super().accept()

    def choose_none(self):
        self.chosen = ""
        super().accept()

    def browse(self):
        from PySide6.QtWidgets import QFileDialog

        files = getattr(self.library, "FILE_FILTER", "Images (*.png *.jpg *.jpeg *.webp)")
        path, _ = QFileDialog.getOpenFileName(self, self.windowTitle(), "", files)
        if path and self.library is not None:
            self.chosen = self.library.import_file(path)
            super().accept()

    def open_folder(self):
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QDesktopServices

        from .image_tools import project_root

        folder = project_root(getattr(self.library, "document", None)) / self.library.FOLDER
        folder.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))


def pick_icon(library, parent=None, *, current="", title="Choose an Icon"):
    """The picture chosen (``""`` for None), or None when the dialog was cancelled."""
    dialog = IconPickerDialog(library, parent, current=current, title=title)
    return dialog.chosen if dialog.exec() == QDialog.Accepted else None
