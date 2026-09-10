try:
    from PySide6.QtCore import Qt, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QHBoxLayout,
        QLabel,
        QListWidget,
        QSizePolicy,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Signal = None
    Qt = None


class TileLayersWidget(QWidget):
    if Signal is not None:
        layerSelected = Signal(object)
        addRequested = Signal()
        removeRequested = Signal(object)
        moveRequested = Signal(object, int)
        visibilityChanged = Signal(object, bool)
        collisionChanged = Signal(object, bool)

    def __init__(self, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self._tilemap = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layer_group = QWidget()
        layer_group.setObjectName("LayerListGroup")
        group_layout = QVBoxLayout(layer_group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(0)

        header = QLabel("MAP LAYERS")
        header.setObjectName("LayerSectionLabel")
        group_layout.addWidget(header)

        self.list = QListWidget()
        self.list.setObjectName("LayerList")
        group_layout.addWidget(self.list, 1)

        controls = QWidget()
        controls.setObjectName("LayerControlRow")
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(0)
        controls.setLayout(row)
        self.add_button = QToolButton()
        self.add_button.setText("+")
        self.remove_button = QToolButton()
        self.remove_button.setText("−")
        self.up_button = QToolButton()
        self.up_button.setText("↑")
        self.down_button = QToolButton()
        self.down_button.setText("↓")
        for b in (
            self.add_button,
            self.remove_button,
            self.up_button,
            self.down_button,
        ):
            b.setObjectName("LayerControlButton")
            b.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            b.setMinimumHeight(36)
            row.addWidget(b, 1)
        group_layout.addWidget(controls)
        layout.addWidget(layer_group, 1)

        self.visible = QCheckBox("Visible")
        self.collision = QCheckBox("Collision layer")
        layout.addWidget(self.visible)
        layout.addWidget(self.collision)

        self.list.currentRowChanged.connect(self._on_selected)
        self.add_button.clicked.connect(lambda: self.addRequested.emit())
        self.remove_button.clicked.connect(self._on_remove)
        self.up_button.clicked.connect(lambda: self._on_move(-1))
        self.down_button.clicked.connect(lambda: self._on_move(1))
        self.visible.toggled.connect(self._on_visible)
        self.collision.toggled.connect(self._on_collision)

    def _layers(self):
        return () if self._tilemap is None else tuple(self._tilemap.layers)

    def current_layer(self):
        layers = self._layers()
        row = self.list.currentRow()
        return layers[row] if 0 <= row < len(layers) else None

    def _on_selected(self, row):
        layer = self.current_layer()
        if layer is None:
            return
        self.visible.blockSignals(True)
        self.visible.setChecked(layer.visible)
        self.visible.blockSignals(False)
        self.collision.blockSignals(True)
        self.collision.setChecked(layer.collision_enabled)
        self.collision.blockSignals(False)
        self.layerSelected.emit(layer)

    def _on_remove(self):
        layer = self.current_layer()
        if layer is not None:
            self.removeRequested.emit(layer)

    def _on_move(self, delta):
        layer = self.current_layer()
        if layer is not None:
            self.moveRequested.emit(layer, self.list.currentRow() + delta)

    def _on_visible(self, value):
        layer = self.current_layer()
        if layer is not None:
            self.visibilityChanged.emit(layer, bool(value))

    def _on_collision(self, value):
        layer = self.current_layer()
        if layer is not None:
            self.collisionChanged.emit(layer, bool(value))

    def set_tilemap(self, tilemap, active_layer=None):
        self._tilemap = tilemap
        self.list.clear()
        if tilemap is None:
            return
        for layer in tilemap.layers:
            badges = []
            if not layer.visible:
                badges.append("hidden")
            if layer.collision_enabled:
                badges.append("collision")
            suffix = f"  · {' / '.join(badges)}" if badges else ""
            self.list.addItem(layer.name + suffix)
        if tilemap.layers:
            index = (
                tilemap.layers.index(active_layer)
                if active_layer in tilemap.layers
                else 0
            )
            self.list.setCurrentRow(index)
