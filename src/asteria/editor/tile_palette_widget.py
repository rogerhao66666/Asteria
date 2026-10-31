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
    """The tileset as a picture: click a tile, or drag over a block of tiles to paint with the
    whole block (a stamp). Tiles are drawn ``zoom`` times their size so they can be told apart,
    and a tileset wider than the panel is cut into strips laid under each other (the way RPG
    Maker's palette wraps a tileset), each strip keeping its tiles side by side."""

    if Signal is not None:
        blockSelected = Signal(object)  # rows of tile ids

    GAP = 12  # pixels between two strips (a rule is drawn through the middle)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("TilePaletteGrid")
        self.setMouseTracking(False)
        self._image = None
        self._cells = {}  # (col, row) -> tile id
        self._frames = {}  # (col, row) -> the tile's picture rect in the texture
        self._columns = self._rows = 0
        self._pages, self._pieces, self._col_place, self._col_at, self._lines = [], [], {}, {}, 0
        self._tile_size = (16, 16)
        self._zoom = 1
        self._selection = None  # (c0, r0, c1, r1), tileset cells
        self._drag = None
        self.setMinimumHeight(60)

    def set_source(self, tileset, sprite_sheet=None, texture_path=None):
        from PySide6.QtGui import QImage

        self._cells, self._frames, self._selection = {}, {}, None
        self._image = None
        if tileset is None:
            self._columns = self._rows = 0
            self._pages, self._pieces, self._col_place, self._col_at = [], [], {}, {}
            self._lines = 0
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
        if texture_path is not None:
            image = QImage(str(texture_path))
            self._image = None if image.isNull() else image
        self._compact()
        self._fit()
        self.update()

    def _compact(self):
        """Drop the atlas's empty rows, and read its empty columns as the gaps between the
        pages the artist drew side by side (a terrain block, then the next): each page is laid
        out whole where it fits, so a tree or a wall is not cut at the panel's edge."""
        for cell in self._blank_cells():  # see-through tiles filling a whole row or column
            self._cells.pop(cell, None)
            self._frames.pop(cell, None)
        rows = sorted({r for _, r in self._cells})
        row_at = {r: i for i, r in enumerate(rows)}
        self._cells = {(c, row_at[r]): t for (c, r), t in self._cells.items()}
        self._frames = {(c, row_at[r]): f for (c, r), f in self._frames.items()}
        self._rows = len(rows)
        columns = sorted({c for c, _ in self._cells})
        self._columns = (columns[-1] + 1) if columns else 0
        self._pages = []  # (first column, last column) of each run of used columns
        for column in columns:
            if self._pages and self._pages[-1][1] == column - 1:
                self._pages[-1] = (self._pages[-1][0], column)
            else:
                self._pages.append((column, column))
        self._place()

    def _blank_cells(self):
        """The cells of the atlas's fully see-through columns and rows: a tileset often lists
        every cell of its picture as a tile, the empty lanes between its pages included."""
        if self._image is None or not self._frames:
            return ()
        try:
            import numpy as np
            from PySide6.QtGui import QImage
        except ImportError:
            return ()
        image = self._image.convertToFormat(QImage.Format_ARGB32)
        width, height = image.width(), image.height()
        data = np.frombuffer(image.constBits(), dtype=np.uint8)
        alpha = data.reshape(height, image.bytesPerLine())[:, : width * 4].reshape(
            height, width, 4
        )[:, :, 3]
        tw, th = self._tile_size
        columns = {c for c, _ in self._cells}
        rows = {r for _, r in self._cells}

        def blank(cells):
            return all(
                frame is None
                or not alpha[frame[1] : frame[1] + th, frame[0] : frame[0] + tw].any()
                for frame in (self._frames.get(cell) for cell in cells)
            )

        blank_columns = {c for c in columns if blank([(c, r) for r in rows])}
        blank_rows = {r for r in rows if blank([(c, r) for c in columns])}
        return [(c, r) for (c, r) in self._cells if c in blank_columns or r in blank_rows]

    def _place(self):
        """Lay the pages out in lines as wide as the panel: a page wider than the panel is cut
        into pieces, a page that fits stays whole, pages share a line when they fit together
        with a column between them."""
        per = self.per_strip()
        self._col_place = {}  # atlas column -> (line, shown column)
        self._col_at = {}  # (line, shown column) -> atlas column
        self._pieces = []  # (line, shown column, first atlas column, last atlas column)
        line, x = 0, 0
        for first, last in getattr(self, "_pages", ()):
            column = first
            while column <= last:
                width = min(per, last - column + 1)
                if x and x + width > per:  # no room on this line: the next one
                    line, x = line + 1, 0
                self._pieces.append((line, x, column, column + width - 1))
                for offset in range(width):
                    self._col_place[column + offset] = (line, x + offset)
                    self._col_at[(line, x + offset)] = column + offset
                x += width + 1  # a column between two pages on one line
                column += width
        self._lines = line + 1 if self._pieces else 0

    def set_zoom(self, zoom):
        """Draw tiles at ``zoom`` times their size (1-4)."""
        self._zoom = max(1, min(4, int(zoom)))
        self._fit()
        self.update()

    def zoom(self):
        return self._zoom

    def _cell_px(self):
        """``(width, height)`` of a drawn tile."""
        return self._tile_size[0] * self._zoom, self._tile_size[1] * self._zoom

    def per_strip(self):
        """How many tileset columns fit side by side in the panel."""
        return max(1, self.width() // max(1, self._cell_px()[0]))

    def strips(self):
        """How many lines the pages take."""
        return getattr(self, "_lines", 0)

    def _strip_height(self):
        return self._rows * self._cell_px()[1] + self.GAP

    def _fit(self):
        self._place()
        lines = self.strips()
        height = lines * self._strip_height() - self.GAP if lines else 0
        self.setMinimumHeight(max(60, height))

    def resizeEvent(self, event):  # noqa: N802 - Qt API
        super().resizeEvent(event)
        self._fit()

    def rect_of(self, col, row):
        """Where tileset cell ``(col, row)`` is drawn: ``(x, y, width, height)``."""
        cw, ch = self._cell_px()
        line, shown = self._col_place.get(col, (0, col))
        return shown * cw, line * self._strip_height() + row * ch, cw, ch

    def _piece_of(self, col):
        """The piece (a page, or the part of one on a line) holding atlas column ``col``."""
        for piece in self._pieces:
            if piece[2] <= col <= piece[3]:
                return piece
        return None

    def _cell_at(self, pos):
        cw, ch = self._cell_px()
        x, y = int(pos.x()), int(pos.y())
        if x < 0 or y < 0:
            return None
        line, offset = divmod(y, self._strip_height())
        shown, row = x // cw, offset // ch
        col = self._col_at.get((line, shown))
        if col is None or row >= self._rows:
            return None
        return col, row

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
        piece = self._piece_of(self._drag[0])
        if piece is not None:  # a block stays inside the piece it started in
            cell = (min(max(cell[0], piece[2]), piece[3]), cell[1])
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

        from .theme import CURRENT

        palette = CURRENT["palette"]
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(palette.raised))
        if not self._cells:  # nothing to paint with: say so instead of an empty box
            from .i18n import translate

            painter.setPen(QColor(palette.text_muted))
            painter.drawText(
                self.rect(), Qt.AlignCenter, translate("This scene has no tile map yet")
            )
            painter.end()
            return
        cw, ch = self._cell_px()
        for (col, row), _tile in self._cells.items():
            target = QRect(*self.rect_of(col, row))
            frame = self._frames.get((col, row))
            if self._image is not None and frame is not None:
                painter.drawImage(target, self._image, QRect(*frame))
            else:
                painter.fillRect(target.adjusted(1, 1, -1, -1), QColor(70, 76, 92))
        painter.setPen(QPen(QColor(255, 255, 255, 28), 1))
        height = self._rows * ch
        for line, shown, first, last in self._pieces:  # a faint grid over each piece
            left, top = shown * cw, line * self._strip_height()
            width = (last - first + 1) * cw
            for col in range(last - first + 2):
                painter.drawLine(left + col * cw, top, left + col * cw, top + height)
            for row in range(self._rows + 1):
                painter.drawLine(left, top + row * ch, left + width, top + row * ch)
        painter.setPen(QPen(QColor(palette.border_strong), 1))
        for line in range(1, self.strips()):  # a rule through the gap above each line
            y = line * self._strip_height() - self.GAP // 2
            painter.drawLine(0, y, self.width(), y)
        if self._selection is not None:
            c0, r0, c1, r1 = self._selection
            c0, c1 = sorted((c0, c1))
            r0, r1 = sorted((r0, r1))
            x, y, _w, _h = self.rect_of(c0, r0)
            painter.setPen(QPen(QColor(255, 206, 96), 2))
            painter.drawRect(x, y, (c1 - c0 + 1) * cw, (r1 - r0 + 1) * ch)
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
        # the tool strip over the map shows these tools; the buttons keep the mode (and the
        # tests' handle)
        for button in (
            self.select_button,
            self.paint_button,
            self.erase_button,
            self.fill_button,
            self.rect_button,
            self.terrain_button,
            self.region_button,
            self.doodad_button,
        ):
            button.hide()

        self.terrain_combo = QComboBox()
        self.terrain_combo.setToolTip("Terrains: tiles with a terrain id and mask:<n> tags")
        self.region_spin = QSpinBox()
        self.region_spin.setObjectName("RegionIdSpin")
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
        self.layer_label.setWordWrap(True)  # a narrow dock wraps a long layer name
        self.layer_label.hide()  # the Layers panel names the active layer
        brush_row = QHBoxLayout()
        brush_row.addWidget(QLabel("Brush"))
        self.brush_spin = QSpinBox()
        self.brush_spin.setObjectName("BrushSizeSpin")
        self.brush_spin.setRange(1, 9)
        self.brush_spin.setSuffix(" × tiles")
        # keep room for "9 × tiles" and the arrows
        self.brush_spin.setMinimumWidth(
            self.brush_spin.fontMetrics().horizontalAdvance("9 × tiles") + 64
        )
        self.brush_spin.setToolTip(
            "Paint / Erase brush width in tiles ([ and ] change it). "
            "Drag over several tiles below to paint with the whole block."
        )
        brush_row.addWidget(self.brush_spin)
        brush_row.addStretch(1)
        zoom_row = QHBoxLayout()  # the tiles' size on screen
        zoom_row.addWidget(QLabel("Zoom"))
        self.zoom_spin = QSpinBox()
        self.zoom_spin.setObjectName("TileZoomSpin")
        self.zoom_spin.setRange(1, 4)
        self.zoom_spin.setValue(1)
        self.zoom_spin.setSuffix(" ×")
        self.zoom_spin.setToolTip("How many times their size the tiles below are drawn")
        zoom_row.addWidget(self.zoom_spin)
        zoom_row.addStretch(1)
        # right under the tool buttons: the brush, the zoom and the tileset picture come first
        layout.insertLayout(2, brush_row)
        layout.insertLayout(3, zoom_row)
        self.tool_hint = QLabel(
            "B Paint · G Fill · R Rectangle · E Erase · S Select · right-click: pick from map"
        )
        self.tool_hint.setObjectName("MutedLabel")
        self.tool_hint.setWordWrap(True)
        layout.insertWidget(4, self.tool_hint)
        self.tool_hint.hide()  # the keys are written on the tool strip's buttons

        self.grid = TileGrid()
        self.zoom_spin.valueChanged.connect(self.grid.set_zoom)
        layout.insertWidget(5, self.grid)

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
        QTimer.singleShot(0, self, self._update_area_rule_height)

    def eventFilter(self, watched, event):
        if (
            watched is getattr(self._dock_scroll_area, "viewport", lambda: None)()
            and event.type() == QEvent.Resize
        ):
            QTimer.singleShot(0, self, self._update_area_rule_height)
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
