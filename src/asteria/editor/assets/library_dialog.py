"""File > Import from Asset Library...: browse the engine's art packs (with thumbnails and each
pack's licence) and copy pictures into the project as assets, in one undo step."""

from __future__ import annotations

from dataclasses import dataclass, field

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from asteria.assets.library import (
    import_into_project,
    library_packs,
    pack_images,
    pack_license,
)

THUMB = 72


@dataclass(slots=True)
class ImportLibraryAssetsCommand:
    """Register pictures copied from the library; undo forgets the records."""

    project: object
    project_dir: object
    picks: tuple  # ((pack, relative), ...)
    records: list = field(default_factory=list)

    @property
    def label(self):
        return f"Import {len(self.picks)} Library Asset(s)"

    def redo(self):
        known = {r.id for r in self.project.assets.records()}
        if self.records:  # redo after an undo: put the same records back
            for record in self.records:
                if record.id not in known:
                    self.project.assets.add(record)
            return
        for pack, relative in self.picks:
            record = import_into_project(self.project, self.project_dir, pack, relative)
            if record.id not in known:
                self.records.append(record)

    def undo(self):
        for record in self.records:
            self.project.assets.remove_record(record.id)


def _thumbnail(path):
    image = QImage(str(path))
    if image.isNull():
        return QIcon()
    scale = max(1, min(THUMB // max(1, image.width()), THUMB // max(1, image.height())))
    pixmap = QPixmap.fromImage(image).scaled(
        image.width() * scale, image.height() * scale, Qt.KeepAspectRatio, Qt.FastTransformation
    )
    return QIcon(pixmap)


class AssetLibraryDialog(QDialog):
    """Packs on the left, their pictures on the right; Import copies the selected ones."""

    def __init__(self, parent=None, *, root=None):
        super().__init__(parent)
        self.setWindowTitle("Asset Library")
        self.resize(980, 640)
        self.packs = library_packs(root)
        self.pack_list = QListWidget()
        self.pack_list.setMaximumWidth(300)
        for pack in self.packs:
            self.pack_list.addItem(QListWidgetItem(pack.name))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filter pictures...")
        self.pictures = QListWidget()
        self.pictures.setViewMode(QListWidget.IconMode)
        self.pictures.setIconSize(QSize(THUMB, THUMB))
        self.pictures.setGridSize(QSize(THUMB + 70, THUMB + 40))
        self.pictures.setResizeMode(QListWidget.Adjust)
        self.pictures.setWordWrap(True)
        self.pictures.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.license = QLabel()
        self.license.setWordWrap(True)
        self.license.setObjectName("AssetLibraryLicense")
        buttons = QDialogButtonBox()
        self.import_button = buttons.addButton("Import Selected", QDialogButtonBox.AcceptRole)
        buttons.addButton(QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        right = QVBoxLayout()
        right.addWidget(self.filter)
        right.addWidget(self.pictures, 1)
        right.addWidget(self.license)
        body = QHBoxLayout()
        body.addWidget(self.pack_list)
        body.addLayout(right, 1)
        layout = QVBoxLayout(self)
        if not self.packs:
            layout.addWidget(QLabel("The asset library is empty (asset_library/ next to src/)."))
        layout.addLayout(body, 1)
        layout.addWidget(buttons)
        self.pack_list.currentRowChanged.connect(self._show_pack)
        self.filter.textChanged.connect(lambda _text: self._show_pack(self.pack_list.currentRow()))
        if self.packs:
            self.pack_list.setCurrentRow(0)

    @property
    def pack(self):
        row = self.pack_list.currentRow()
        return self.packs[row] if 0 <= row < len(self.packs) else None

    def _show_pack(self, row):
        self.pictures.clear()
        if not 0 <= row < len(self.packs):
            return
        pack = self.packs[row]
        wanted = self.filter.text().strip().lower()
        for relative in pack_images(pack):
            if wanted and wanted not in relative.lower():
                continue
            item = QListWidgetItem(_thumbnail(pack.path / relative), relative.rsplit("/", 1)[-1])
            item.setToolTip(relative)
            item.setData(Qt.UserRole, relative)
            self.pictures.addItem(item)
        self.license.setText(
            f"{pack.name}  ·  {len(pack_images(pack))} pictures  ·  licence: "
            f"{pack_license(pack)}  ·  {pack.pack_id}"
        )

    def select(self, relatives):
        """Select pictures by relative path (tests and scripts)."""
        wanted = set(relatives)
        for index in range(self.pictures.count()):
            item = self.pictures.item(index)
            item.setSelected(item.data(Qt.UserRole) in wanted)

    def picks(self):
        pack = self.pack
        if pack is None:
            return ()
        return tuple((pack, item.data(Qt.UserRole)) for item in self.pictures.selectedItems())
