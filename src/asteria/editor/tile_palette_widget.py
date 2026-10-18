try:
    from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
    from PySide6.QtWidgets import (
        QCheckBox,
        QComboBox,
        QDoubleSpinBox,
        QFormLayout,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QSizePolicy,
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


class TileGrid(QWidget):
    """The tileset as a picture, laid out the way its atlas is: click a tile, or drag over a
    block of tiles to paint with the whole block (a stamp)."""

    if Signal is not None:
        blockSelected = Signal(object)  # rows of tile ids

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TilePaletteGrid")
        self.setMouseTracking(False)
        self._image = None
        self._cells = {}  # (col, row) -> tile id
        self._frames = {}  # (col, row) -> the tile's picture rect in the texture
        self._columns = self._rows = 0
        self._tile_size = (16, 16)
        self._selection = None  # (c0, r0, c1, r1)
        self._drag = None
        self.setMinimumHeight(60)

    def set_source(self, tileset, sprite_sheet=None, texture_path=None):
        from PySide6.QtGui import QImage

        self._cells, self._frames, self._selection = {}, {}, None
        self._image = None
        if tileset is None:
            self._columns = self._rows = 0
            self.updateGeometry()
            self.update()
            return
        tw, th = int(tileset.tile_width), int(tileset.tile_height)
        self._tile_size = (tw, th)
        frames = list(getattr(sprite_sheet, "frames", None) or ())
        for item in build_tile_palette(tileset):
            if 0 <= item.frame_index < len(frames):
                frame = frames[item.frame_index]
                cell = (int(frame.x) // tw, int(frame.y) // th)
                self._frames.setdefault(
                    cell, (int(frame.x), int(frame.y), int(frame.width), int(frame.height))
                )
            else:  # no picture known: tiles in id order, eight to a row
                cell = (len(self._cells) % 8, len(self._cells) // 8)
            self._cells.setdefault(cell, item.tile_id)
        self._columns = max((c for c, _ in self._cells), default=-1) + 1
        self._rows = max((r for _, r in self._cells), default=-1) + 1
        if texture_path is not None:
            image = QImage(str(texture_path))
            self._image = None if image.isNull() else image
        self._fit()
        self.update()

    def _cell_px(self):
        width = max(1, self.width())
        return max(12, min(48, width // max(1, self._columns)))

    def _fit(self):
        self.setMinimumHeight(max(60, self._rows * self._cell_px()))

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._fit()

    def _cell_at(self, pos):
        size = self._cell_px()
        col, row = int(pos.x()) // size, int(pos.y()) // size
        if 0 <= col < self._columns and 0 <= row < self._rows:
            return col, row
        return None

    def select_tile(self, tile_id, rows=None):
        """Highlight a picked tile (or the block ``rows`` when it is laid out that way)."""
        where = [cell for cell, t in self._cells.items() if t == tile_id]
        if not where:
            self._selection = None
        else:
            c, r = min(where)
            h = len(rows) if rows else 1
            w = len(rows[0]) if rows else 1
            block = (
                all(
                    self._cells.get((c + x, r + y)) == rows[y][x]
                    for y in range(h)
                    for x in range(w)
                )
                if rows
                else True
            )
            self._selection = (c, r, c + w - 1, r + h - 1) if block else (c, r, c, r)
        self.update()

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        cell = self._cell_at(event.position())
        if cell is None:
            return
        self._drag = cell
        self._selection = (*cell, *cell)
        self.update()

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt API
        if self._drag is None:
            return
        cell = self._cell_at(event.position()) or self._drag
        self._selection = (*self._drag, *cell)
        self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if self._drag is None or self._selection is None:
            return
        self._drag = None
        c0, r0, c1, r1 = self._selection
        c0, c1 = sorted((c0, c1))
        r0, r1 = sorted((r0, r1))
        self._selection = (c0, r0, c1, r1)
        from asteria.graphics import EMPTY_TILE

        rows = tuple(
            tuple(self._cells.get((c, r), EMPTY_TILE) for c in range(c0, c1 + 1))
            for r in range(r0, r1 + 1)
        )
        if any(t != EMPTY_TILE for row in rows for t in row) and Signal is not None:
            self.blockSelected.emit(rows)
        self.update()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        from PySide6.QtCore import QRect
        from PySide6.QtGui import QColor, QPainter, QPen

        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(28, 30, 38))
        size = self._cell_px()
        for (col, row), _tile in self._cells.items():
            target = QRect(col * size, row * size, size, size)
            frame = self._frames.get((col, row))
            if self._image is not None and frame is not None:
                painter.drawImage(target, self._image, QRect(*frame))
            else:
                painter.fillRect(target.adjusted(1, 1, -1, -1), QColor(70, 76, 92))
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        for col in range(self._columns + 1):
            painter.drawLine(col * size, 0, col * size, self._rows * size)
        for row in range(self._rows + 1):
            painter.drawLine(0, row * size, self._columns * size, row * size)
        if self._selection is not None:
            c0, r0, c1, r1 = self._selection
            c0, c1 = sorted((c0, c1))
            r0, r1 = sorted((r0, r1))
            painter.setPen(QPen(QColor(255, 206, 96), 2))
            painter.drawRect(c0 * size, r0 * size, (c1 - c0 + 1) * size, (r1 - r0 + 1) * size)
        painter.end()


class TilePaletteWidget(QWidget):
    if Signal is not None:
        tileSelected = Signal(int)
        stampSelected = Signal(object)  # rows of tile ids (one row of one: a single tile)
        brushSizeChanged = Signal(int)
        modeChanged = Signal(str)
        terrainChanged = Signal(str)
        regionChanged = Signal(int, bool)
        areaRuleChanged = Signal(object)
        areaRuleRemoved = Signal(int)
        createMapRuleSetRequested = Signal()
        doodadChanged = Signal(object)

    def __init__(self, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        self._tileset = None
        self._doodads = {}
        self._area_rule_set = None
        self._dock_scroll_area = None
        self._updating_area_rule_height = False
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
        self.region_spin.setObjectName("RegionIdSpin")
        self.region_spin.setMinimumHeight(30)
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

        self.region_rules = QGroupBox()
        self.region_rules.setObjectName("AreaRuleCard")
        self.region_rules.setMinimumWidth(0)
        self.region_rules.setMaximumHeight(360)
        region_layout = QVBoxLayout(self.region_rules)
        region_layout.setContentsMargins(8, 8, 8, 8)
        region_layout.setSpacing(8)
        region_title = QLabel("Area Rule")
        region_title.setObjectName("AreaRuleTitle")
        self.region_title = region_title
        region_layout.addWidget(region_title)
        region_content = QWidget()
        region_content_layout = QVBoxLayout(region_content)
        region_content_layout.setContentsMargins(0, 0, 0, 0)
        region_content_layout.setSpacing(6)
        self.region_rule_status = QLabel("Create a map ruleset to edit region rules")
        self.region_rule_status.setObjectName("MutedLabel")
        self.region_rule_status.setWordWrap(True)
        region_content_layout.addWidget(self.region_rule_status)
        self.region_rule_form = QWidget()
        form = QFormLayout(self.region_rule_form)
        form.setProperty("stackFields", True)
        form.setRowWrapPolicy(QFormLayout.WrapAllRows)
        form.setVerticalSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.ExpandingFieldsGrow)
        form.setContentsMargins(0, 0, 0, 0)
        self.region_rule_form.setMinimumWidth(0)
        self.region_rule_form.setMinimumHeight(0)
        self.damage_resource = QLineEdit()
        self.damage_per_second = self._rule_spin()
        self.can_kill = QCheckBox("Can defeat player")
        self.slippery = QCheckBox("Slippery floor")
        self.slip_seconds = self._rule_spin()
        self.footstep_cue = QLineEdit()
        self.step_distance = self._rule_spin(minimum=0.01)
        self.blocks = QLineEdit()
        self.visibility = self._rule_spin()
        self.on_enter = QLineEdit()
        self.on_leave = QLineEdit()
        self.on_step = QLineEdit()
        self.switch = QLineEdit()
        for label, widget in (
            ("Damage Resource", self.damage_resource),
            ("Damage / Second", self.damage_per_second),
            ("Lethal Damage", self.can_kill),
            ("Movement", self.slippery),
            ("Slide Seconds", self.slip_seconds),
            ("Footstep Cue", self.footstep_cue),
            ("Step Distance", self.step_distance),
            ("Blocks Groups", self.blocks),
            ("Enemy Visibility", self.visibility),
            ("On Enter Event", self.on_enter),
            ("On Leave Event", self.on_leave),
            ("On Step Event", self.on_step),
            ("Required Switch", self.switch),
        ):
            form.addRow(label, widget)
        self.region_rule_fields_scroll = QScrollArea(self.region_rules)
        self.region_rule_fields_scroll.setObjectName("AreaRuleFieldsScroll")
        self.region_rule_fields_scroll.setWidgetResizable(True)
        self.region_rule_fields_scroll.setFrameShape(QScrollArea.NoFrame)
        self.region_rule_fields_scroll.setMinimumSize(0, 0)
        self.region_rule_fields_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.region_rule_fields_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        region_content_layout.addWidget(self.region_rule_form)
        self.region_rule_fields_scroll.setViewportMargins(0, 0, 8, 0)
        self.region_rule_fields_scroll.setWidget(region_content)
        region_layout.addWidget(self.region_rule_fields_scroll, 1)
        self.region_layer_label = QLabel("Region layer: regions")
        self.region_layer_label.setObjectName("MutedLabel")
        region_content_layout.addWidget(self.region_layer_label)
        actions = QVBoxLayout()
        self.apply_region_rule = QPushButton("Apply Rule")
        self.remove_region_rule = QPushButton("Remove Rule")
        self.create_map_ruleset = QPushButton("Create Map Ruleset")
        actions.addWidget(self.apply_region_rule)
        actions.addWidget(self.remove_region_rule)
        actions.addWidget(self.create_map_ruleset)
        region_content_layout.addLayout(actions)
        layout.addWidget(self.region_rules)
        layout.addSpacing(24)  # the last card keeps clear of the dock's tabs

        self.layer_label = QLabel("Layer: —")
        self.layer_label.setObjectName("MutedLabel")
        brush_row = QHBoxLayout()
        brush_row.addWidget(self.layer_label, 1)
        brush_row.addWidget(QLabel("Brush"))
        self.brush_spin = QSpinBox()
        self.brush_spin.setObjectName("BrushSizeSpin")
        self.brush_spin.setRange(1, 9)
        self.brush_spin.setSuffix(" × tiles")
        self.brush_spin.setToolTip(
            "Paint / Erase brush width in tiles ([ and ] change it). "
            "Drag over several tiles below to paint with the whole block."
        )
        brush_row.addWidget(self.brush_spin)
        # right under the tool buttons: the brush and the tileset picture come first
        layout.insertLayout(2, brush_row)
        self.tool_hint = QLabel(
            "B Paint · G Fill · R Rectangle · E Erase · S Select · right-click: pick from map"
        )
        self.tool_hint.setObjectName("MutedLabel")
        self.tool_hint.setWordWrap(True)
        layout.insertWidget(3, self.tool_hint)

        self.grid = TileGrid()
        layout.insertWidget(4, self.grid)

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
        self.apply_region_rule.clicked.connect(self._apply_region_rule)
        self.remove_region_rule.clicked.connect(
            lambda: self.areaRuleRemoved.emit(self.region_spin.value())
        )
        self.create_map_ruleset.clicked.connect(self.createMapRuleSetRequested.emit)
        self.doodad_combo.currentTextChanged.connect(self._doodad_changed)
        self.grid.blockSelected.connect(self._block_selected)
        self.brush_spin.valueChanged.connect(self.brushSizeChanged.emit)

    def bind_dock_scroll_area(self, scroll_area):
        """Keep the Area Rule frame within the visible portion of the Tiles dock."""
        self._dock_scroll_area = scroll_area
        scroll_area.viewport().installEventFilter(self)
        scroll_area.verticalScrollBar().valueChanged.connect(self._update_area_rule_height)
        QTimer.singleShot(0, self._update_area_rule_height)

    def eventFilter(self, watched, event):
        if (
            watched is getattr(self._dock_scroll_area, "viewport", lambda: None)()
            and event.type() == QEvent.Resize
        ):
            QTimer.singleShot(0, self._update_area_rule_height)
        return super().eventFilter(watched, event)

    def _update_area_rule_height(self, *_):
        scroll_area = self._dock_scroll_area
        if scroll_area is None or self._updating_area_rule_height:
            return
        viewport = scroll_area.viewport()
        top = self.region_rules.mapTo(viewport, QPoint(0, 0)).y()
        available = viewport.height() - max(0, top) - 24
        maximum = max(200, min(360, available))
        if self.region_rules.maximumHeight() == maximum:
            return
        self._updating_area_rule_height = True
        self.region_rules.setMaximumHeight(maximum)
        self._updating_area_rule_height = False

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
        self._refresh_area_rule_form()

    @staticmethod
    def _rule_spin(*, minimum=0.0):
        spin = QDoubleSpinBox()
        spin.setRange(minimum, 1_000_000_000.0)
        spin.setDecimals(2)
        return spin

    def set_area_rule_set(self, ruleset):
        """Bind the editor to the active runtime ruleset and its region tile layer."""
        self._area_rule_set = ruleset
        self.set_region_layer(ruleset.region_layer if ruleset is not None else "regions")
        self._refresh_area_rule_form()

    def set_region_layer(self, layer_name):
        self.region_layer_label.setText(f"Region layer: {layer_name or 'regions'}")

    def _refresh_area_rule_form(self):
        from asteria.rpg.map_rules import AreaRule

        ruleset = self._area_rule_set
        enabled = ruleset is not None
        self.region_rule_form.setEnabled(enabled)
        self.apply_region_rule.setEnabled(enabled)
        self.remove_region_rule.setEnabled(enabled)
        self.create_map_ruleset.setVisible(not enabled)
        if not enabled:
            self.region_title.setText("Area Rule")
            self.region_rule_status.setText("Create a map ruleset to edit region rules")
            return
        region_id = self.region_spin.value()
        key = f"region:{region_id}"
        existing = ruleset.rule(key)
        rule = existing or AreaRule(key)
        self.region_title.setText(f"Area Rule · {key}")
        self.region_rule_status.setText(
            f"Ruleset: {ruleset.rules_id} · " + ("Existing rule" if existing else "No rule yet")
        )
        self.remove_region_rule.setEnabled(existing is not None)
        values = (
            (self.damage_resource, rule.damage_resource),
            (self.damage_per_second, rule.damage_per_second),
            (self.can_kill, rule.can_kill),
            (self.slippery, rule.slippery),
            (self.slip_seconds, rule.slip_seconds),
            (self.footstep_cue, rule.footstep_cue),
            (self.step_distance, rule.step_distance),
            (self.blocks, ", ".join(rule.blocks)),
            (self.visibility, rule.visibility),
            (self.on_enter, rule.on_enter),
            (self.on_leave, rule.on_leave),
            (self.on_step, rule.on_step),
            (self.switch, rule.switch),
        )
        for widget, value in values:
            widget.blockSignals(True)
            if isinstance(widget, QCheckBox):
                widget.setChecked(bool(value))
            elif isinstance(widget, QDoubleSpinBox):
                widget.setValue(float(value))
            else:
                widget.setText(str(value))
            widget.blockSignals(False)

    def _apply_region_rule(self):
        from asteria.rpg.map_rules import AreaRule

        if self._area_rule_set is None:
            return
        try:
            rule = AreaRule(
                f"region:{self.region_spin.value()}",
                damage_resource=self.damage_resource.text(),
                damage_per_second=self.damage_per_second.value(),
                can_kill=self.can_kill.isChecked(),
                slippery=self.slippery.isChecked(),
                slip_seconds=self.slip_seconds.value(),
                footstep_cue=self.footstep_cue.text(),
                step_distance=self.step_distance.value(),
                blocks=tuple(item.strip() for item in self.blocks.text().split(",")),
                visibility=self.visibility.value(),
                on_enter=self.on_enter.text(),
                on_leave=self.on_leave.text(),
                on_step=self.on_step.text(),
                switch=self.switch.text(),
            )
        except ValueError as exc:
            self.region_rule_status.setText(str(exc))
            return
        self.areaRuleChanged.emit(rule)

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

    def _block_selected(self, rows):
        self.tileSelected.emit(int(rows[0][0]))
        self.stampSelected.emit(rows)
        if self.select_button.isChecked() or self.region_button.isChecked():
            self._set_mode("paint")  # picking a tile means painting with it

    def show_picked(self, rows):
        """The eyedropper took ``rows`` off the map: highlight them here."""
        self.grid.select_tile(int(rows[0][0]), rows)
        self.tileSelected.emit(int(rows[0][0]))

    def handle_tool_key(self, name):
        """A tool key pressed over the map: B / G / R / E / S switch tools, [ ] the brush."""
        if name == "smaller":
            self.brush_spin.setValue(self.brush_spin.value() - 1)
        elif name == "bigger":
            self.brush_spin.setValue(self.brush_spin.value() + 1)
        else:
            self._set_mode(name)

    def set_tileset(self, tileset, sprite_sheet=None, texture_path=None):
        self._tileset = tileset
        self.grid.set_source(tileset, sprite_sheet, texture_path)
        self.terrain_combo.blockSignals(True)
        self.terrain_combo.clear()
        if tileset is not None:
            self.terrain_combo.addItems(terrain_ids(tileset))
        self.terrain_combo.blockSignals(False)
        self.terrainChanged.emit(self.terrain_combo.currentText())
        if tileset is None:
            return

    def set_layer(self, layer):
        self.layer_label.setText(f"Layer: {layer.name}" if layer is not None else "Layer: —")
