try:
    from PySide6.QtCore import QRect, QSize, Qt, Signal
    from PySide6.QtGui import QIcon, QPixmap
    from PySide6.QtWidgets import (
        QGridLayout,
        QLabel,
        QListWidget,
        QListWidgetItem,
        QSizePolicy,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Signal = None
    Qt = None

from .qt_texture_renderer import QtTextureCache
from .tile_palette import build_tile_palette

_TILE_THUMBNAIL_SIZE = 32


class TilePaletteWidget(QWidget):
    if Signal is not None:
        tileSelected = Signal(int)
        modeChanged = Signal(str)

    def __init__(self, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._tileset = None
        self._texture_cache = QtTextureCache()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Wrapped into a grid rather than one row: five labelled buttons do not
        # fit across the left dock's width, and a single row truncates them to
        # unreadable stubs ("S...t").
        tools = QGridLayout()
        tools.setSpacing(4)
        self.select_button = QToolButton()
        self.select_button.setText("Select")
        self.select_button.setToolTip("Select and inspect tiles without painting")
        self.paint_button = QToolButton()
        self.paint_button.setText("Paint")
        self.paint_button.setToolTip("Paint the selected tile (drag to draw)")
        self.erase_button = QToolButton()
        self.erase_button.setText("Erase")
        self.erase_button.setToolTip("Erase tiles back to empty")
        self.fill_button = QToolButton()
        self.fill_button.setText("Fill")
        self.fill_button.setToolTip("Flood-fill a connected area with the selected tile")
        self.rect_button = QToolButton()
        self.rect_button.setText("Rect")
        self.rect_button.setToolTip("Drag a rectangle filled with the selected tile")
        for index, button in enumerate((
            self.select_button,
            self.paint_button,
            self.erase_button,
            self.fill_button,
            self.rect_button,
        )):
            button.setCheckable(True)
            button.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            tools.addWidget(button, index // 3, index % 3)
        self.select_button.setChecked(True)
        layout.addLayout(tools)

        self.layer_label = QLabel("Layer: —")
        self.layer_label.setObjectName("MutedLabel")
        layout.addWidget(self.layer_label)

        self.list = QListWidget()
        self.list.setObjectName("TilePaletteList")
        self.list.setIconSize(QSize(_TILE_THUMBNAIL_SIZE, _TILE_THUMBNAIL_SIZE))
        self.list.setResizeMode(QListWidget.Adjust)
        self.list.setMovement(QListWidget.Static)
        self.list.setSpacing(2)
        layout.addWidget(self.list, 1)

        self.select_button.clicked.connect(lambda: self._set_mode("select"))
        self.paint_button.clicked.connect(lambda: self._set_mode("paint"))
        self.erase_button.clicked.connect(lambda: self._set_mode("erase"))
        self.fill_button.clicked.connect(lambda: self._set_mode("fill"))
        self.rect_button.clicked.connect(lambda: self._set_mode("rectangle"))
        self.list.currentRowChanged.connect(self._row_changed)

    def _set_mode(self, mode):
        mapping = {
            "select": self.select_button,
            "paint": self.paint_button,
            "erase": self.erase_button,
            "fill": self.fill_button,
            "rectangle": self.rect_button,
        }
        for name, button in mapping.items():
            button.setChecked(name == mode)
        self.modeChanged.emit(mode)

    def _row_changed(self, row):
        if self._tileset is None or row < 0:
            return
        items = build_tile_palette(self._tileset)
        if row < len(items):
            self.tileSelected.emit(items[row].tile_id)

    def set_tileset(self, tileset, sprite_sheet=None, texture_path=None):
        self._tileset = tileset
        self.list.clear()
        if tileset is None:
            return
        # Show real tile art as a clickable grid when the tileset's sprite
        # sheet resolves to an image on disk; fall back to the text list when
        # it doesn't, so a project without imported art is still authorable.
        image = self._texture_cache.get(texture_path) if texture_path else None
        frames = getattr(sprite_sheet, "frames", None) or ()
        has_art = image is not None and bool(frames)
        self.list.setViewMode(
            QListWidget.IconMode if has_art else QListWidget.ListMode
        )
        for item in build_tile_palette(tileset):
            suffix = []
            if item.terrain:
                suffix.append(item.terrain)
            if item.collision != "none":
                suffix.append(item.collision)
            meta = f"  · {' / '.join(suffix)}" if suffix else ""
            label = f"Tile {item.tile_id}{meta}"
            entry = QListWidgetItem()
            entry.setToolTip(label)
            icon = self._tile_icon(image, frames, item.frame_index) if has_art else None
            if icon is None:
                entry.setText(label)
            else:
                entry.setIcon(icon)
            self.list.addItem(entry)

    def _tile_icon(self, image, frames, frame_index):
        if not 0 <= frame_index < len(frames):
            return None
        frame = frames[frame_index]
        cropped = image.copy(
            QRect(int(frame.x), int(frame.y), int(frame.width), int(frame.height))
        )
        if cropped.isNull():
            return None
        # Nearest-neighbour: tile art is pixel art, smooth scaling blurs it.
        pixmap = QPixmap.fromImage(cropped).scaled(
            _TILE_THUMBNAIL_SIZE,
            _TILE_THUMBNAIL_SIZE,
            Qt.KeepAspectRatio,
            Qt.FastTransformation,
        )
        return QIcon(pixmap)

    def set_layer(self, layer):
        self.layer_label.setText(
            f"Layer: {layer.name}" if layer is not None else "Layer: —"
        )

    def show_hint(self, text):
        self.layer_label.setText(text)
