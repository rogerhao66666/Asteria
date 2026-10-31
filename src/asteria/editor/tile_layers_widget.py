"""The Layers panel: the map's layers as rows, each with an eye that shows or hides it, a
swatch of the layer's colour and its name (a "collision" mark on a collision layer), the way
LDtk lists layers; below, the controls to add, remove and reorder them and the collision switch.
"""

try:
    from PySide6.QtCore import QSize, Qt, Signal
    from PySide6.QtGui import QColor, QPainter
    from PySide6.QtWidgets import (
        QCheckBox,
        QHBoxLayout,
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

# a layer's colour, by its place in the map (a collision layer is always the coral)
LAYER_COLOURS = ("#8a6a4a", "#86bf58", "#dca545", "#9a84e0", "#4aa9dc", "#55aeb8", "#e8894a")
COLLISION_COLOUR = "#e06a5c"


def layer_colour(index, collision=False):
    if collision:
        return COLLISION_COLOUR
    return LAYER_COLOURS[index % len(LAYER_COLOURS)]


class _Swatch(QWidget):
    """A small rounded bar of one colour."""

    def __init__(self, colour, parent=None):
        super().__init__(parent)
        self.colour = QColor(colour)
        self.setFixedSize(4, 15)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(self.colour)
        painter.drawRoundedRect(self.rect(), 2, 2)
        painter.end()


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
        self.eye_buttons = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
        layer_group = QWidget()
        layer_group.setObjectName("LayerListGroup")
        group_layout = QVBoxLayout(layer_group)
        group_layout.setContentsMargins(0, 0, 0, 0)
        group_layout.setSpacing(0)

        header = QLabel("Map Layers")
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

        self.collision = QCheckBox("Collision layer")
        layout.addWidget(self.collision)

        self.list.currentRowChanged.connect(self._on_selected)
        self.add_button.clicked.connect(lambda: self.addRequested.emit())
        self.remove_button.clicked.connect(self._on_remove)
        self.up_button.clicked.connect(lambda: self._on_move(-1))
        self.down_button.clicked.connect(lambda: self._on_move(1))
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

    def _on_collision(self, value):
        layer = self.current_layer()
        if layer is not None:
            self.collisionChanged.emit(layer, bool(value))

    def _row(self, index, layer):
        """One layer's row: the eye, the colour, the name and a mark on a collision layer."""
        from .icons import icon

        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(4, 0, 6, 0)
        box.setSpacing(7)
        eye = QToolButton(row)
        eye.setObjectName("LayerEyeButton")
        eye.setCheckable(True)
        eye.setChecked(bool(layer.visible))
        eye.setIconSize(QSize(15, 15))
        eye.setIcon(icon("eye" if layer.visible else "eye_off"))
        eye.setToolTip("Show or hide this layer")
        eye.toggled.connect(lambda on, item=layer: self.visibilityChanged.emit(item, bool(on)))
        box.addWidget(eye)
        box.addWidget(_Swatch(layer_colour(index, layer.collision_enabled), row))
        name = QLabel(layer.name, row)
        name.setObjectName("LayerName")
        name.setProperty("off", not layer.visible)
        box.addWidget(name, 1)
        if layer.collision_enabled:
            badge = QLabel("collision", row)
            badge.setObjectName("LayerBadge")
            box.addWidget(badge)
        self.eye_buttons.append(eye)
        return row

    def set_tilemap(self, tilemap, active_layer=None):
        self._tilemap = tilemap
        self.list.clear()
        self.eye_buttons = []
        if tilemap is None:
            return
        for index, layer in enumerate(tilemap.layers):
            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 28))
            self.list.addItem(item)
            self.list.setItemWidget(item, self._row(index, layer))
        if tilemap.layers:
            index = tilemap.layers.index(active_layer) if active_layer in tilemap.layers else 0
            self.list.setCurrentRow(index)
