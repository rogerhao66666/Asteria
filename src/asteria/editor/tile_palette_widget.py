try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QSpinBox,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Signal = None
    Qt = None

from .tile_palette import build_tile_palette, terrain_ids


class TilePaletteWidget(QWidget):
    if Signal is not None:
        tileSelected = Signal(int)
        modeChanged = Signal(str)
        terrainChanged = Signal(str)
        regionChanged = Signal(int, bool)
        doodadChanged = Signal(object)

    def __init__(self, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._tileset = None
        self._doodads = {}
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        tools = QHBoxLayout()
        self.select_button = QToolButton()
        self.select_button.setText("Select")
        self.paint_button = QToolButton()
        self.paint_button.setText("Paint")
        self.erase_button = QToolButton()
        self.erase_button.setText("Erase")
        self.fill_button = QToolButton()
        self.fill_button.setText("Fill")
        self.rect_button = QToolButton()
        self.rect_button.setText("Rectangle")
        for button in (
            self.select_button,
            self.paint_button,
            self.erase_button,
            self.fill_button,
            self.rect_button,
        ):
            button.setCheckable(True)
            tools.addWidget(button)
        self.select_button.setChecked(True)
        layout.addLayout(tools)

        brushes = QHBoxLayout()
        self.terrain_button = QToolButton()
        self.terrain_button.setText("Terrain")
        self.region_button = QToolButton()
        self.region_button.setText("Region")
        self.doodad_button = QToolButton()
        self.doodad_button.setText("Doodad")
        for button in (self.terrain_button, self.region_button, self.doodad_button):
            button.setCheckable(True)
            brushes.addWidget(button)
        layout.addLayout(brushes)

        self.terrain_combo = QComboBox()
        self.terrain_combo.setToolTip("Terrains: tiles with a terrain id and mask:<n> tags")
        self.region_spin = QSpinBox()
        self.region_spin.setRange(0, 255)
        self.region_spin.setValue(1)
        self.region_erase = QCheckBox("Erase region")
        self.doodad_combo = QComboBox()
        for label, widget in (
            ("Terrain", self.terrain_combo),
            ("Region id", self.region_spin),
            (None, self.region_erase),
            ("Doodad", self.doodad_combo),
        ):
            row = QHBoxLayout()
            if label:
                row.addWidget(QLabel(label))
            row.addWidget(widget, 1)
            layout.addLayout(row)

        self.layer_label = QLabel("Layer: —")
        self.layer_label.setObjectName("MutedLabel")
        layout.addWidget(self.layer_label)

        self.list = QListWidget()
        self.list.setObjectName("TilePaletteList")
        layout.addWidget(self.list, 1)

        self.select_button.clicked.connect(lambda: self._set_mode("select"))
        self.paint_button.clicked.connect(lambda: self._set_mode("paint"))
        self.erase_button.clicked.connect(lambda: self._set_mode("erase"))
        self.fill_button.clicked.connect(lambda: self._set_mode("fill"))
        self.rect_button.clicked.connect(lambda: self._set_mode("rectangle"))
        self.terrain_button.clicked.connect(lambda: self._set_mode("terrain"))
        self.region_button.clicked.connect(lambda: self._set_mode("region"))
        self.doodad_button.clicked.connect(lambda: self._set_mode("doodad"))
        self.terrain_combo.currentTextChanged.connect(self.terrainChanged.emit)
        self.region_spin.valueChanged.connect(self._region_changed)
        self.region_erase.toggled.connect(self._region_changed)
        self.doodad_combo.currentTextChanged.connect(self._doodad_changed)
        self.list.currentRowChanged.connect(self._row_changed)

    def _set_mode(self, mode):
        mapping = {
            "select": self.select_button,
            "paint": self.paint_button,
            "erase": self.erase_button,
            "fill": self.fill_button,
            "rectangle": self.rect_button,
            "terrain": self.terrain_button,
            "region": self.region_button,
            "doodad": self.doodad_button,
        }
        for name, button in mapping.items():
            button.setChecked(name == mode)
        self.modeChanged.emit(mode)

    def _region_changed(self, *_):
        self.regionChanged.emit(self.region_spin.value(), self.region_erase.isChecked())

    def _doodad_changed(self, name):
        self.doodadChanged.emit(self._doodads.get(name))

    def set_doodads(self, doodads):
        """Offer the project's doodad definitions (``{id: DoodadDefinition}``) to place."""
        self._doodads = dict(doodads or {})
        self.doodad_combo.blockSignals(True)
        self.doodad_combo.clear()
        self.doodad_combo.addItems(sorted(self._doodads))
        self.doodad_combo.blockSignals(False)
        self.doodadChanged.emit(self._doodads.get(self.doodad_combo.currentText()))

    def _row_changed(self, row):
        if self._tileset is None or row < 0:
            return
        items = build_tile_palette(self._tileset)
        if row < len(items):
            self.tileSelected.emit(items[row].tile_id)

    def set_tileset(self, tileset):
        self._tileset = tileset
        self.list.clear()
        self.terrain_combo.blockSignals(True)
        self.terrain_combo.clear()
        if tileset is not None:
            self.terrain_combo.addItems(terrain_ids(tileset))
        self.terrain_combo.blockSignals(False)
        self.terrainChanged.emit(self.terrain_combo.currentText())
        if tileset is None:
            return
        for item in build_tile_palette(tileset):
            suffix = []
            if item.terrain:
                suffix.append(item.terrain)
            if item.collision != "none":
                suffix.append(item.collision)
            meta = f"  · {' / '.join(suffix)}" if suffix else ""
            self.list.addItem(f"Tile {item.tile_id}{meta}")

    def set_layer(self, layer):
        self.layer_label.setText(f"Layer: {layer.name}" if layer is not None else "Layer: —")
