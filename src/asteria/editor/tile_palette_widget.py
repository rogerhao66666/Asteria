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
        QListWidget,
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


class TilePaletteWidget(QWidget):
    if Signal is not None:
        tileSelected = Signal(int)
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
        self.apply_region_rule.clicked.connect(self._apply_region_rule)
        self.remove_region_rule.clicked.connect(
            lambda: self.areaRuleRemoved.emit(self.region_spin.value())
        )
        self.create_map_ruleset.clicked.connect(self.createMapRuleSetRequested.emit)
        self.doodad_combo.currentTextChanged.connect(self._doodad_changed)
        self.list.currentRowChanged.connect(self._row_changed)

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
