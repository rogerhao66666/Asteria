from __future__ import annotations

try:
    from PySide6.QtCore import QSize, Qt, QTimer, Signal
    from PySide6.QtGui import QIcon, QImage, QPixmap
    from PySide6.QtWidgets import (
        QComboBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QListWidget,
        QListWidgetItem,
        QPushButton,
        QScrollArea,
        QSpinBox,
        QTabWidget,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Qt = QTimer = Signal = QImage = QPixmap = None

from PIL import Image, ImageDraw

from asteria.assets.character_generator import DIRECTIONS, LAYER_ORDER
from asteria.graphics.character_placement import CharacterPlacement, frame_rect_at_standing_point


def character_grid_preview(image, *, canvas_size=(144, 144), tile_size=(48, 48)):
    canvas = Image.new("RGBA", canvas_size, (24, 27, 32, 255))
    draw = ImageDraw.Draw(canvas)
    left = (canvas_size[0] - tile_size[0]) // 2
    top = (canvas_size[1] - tile_size[1]) // 2
    draw.rectangle((left, top, left + tile_size[0], top + tile_size[1]), outline=(79, 88, 104, 255), width=1)
    draw.line((left, top + tile_size[1], left + tile_size[0], top + tile_size[1]), fill=(235, 183, 76, 255), width=2)
    standing = (left + tile_size[0] / 2, top + tile_size[1])
    x1, y1, _, _ = frame_rect_at_standing_point(standing, CharacterPlacement(image.size))
    canvas.alpha_composite(image.convert("RGBA"), (round(x1), round(y1)))
    return canvas


def checkerboard_preview(image, *, square=16):
    source = image.convert("RGBA")
    canvas = Image.new("RGBA", source.size, (238, 238, 238, 255))
    draw = ImageDraw.Draw(canvas)
    for y in range(0, source.height, square):
        for x in range(0, source.width, square):
            if (x // square + y // square) % 2:
                draw.rectangle(
                    (x, y, min(x + square - 1, source.width - 1), min(y + square - 1, source.height - 1)),
                    fill=(205, 205, 205, 255),
                )
    canvas.alpha_composite(source)
    return canvas


class CharacterGeneratorWidget(QWidget):
    """Polished editor surface for the Qt-neutral CharacterGeneratorWorkspace.

    This widget authors ordinary canonical assets. It is intentionally not a
    runtime character type and does not constrain imported/custom artwork.
    """

    if Signal is not None:
        generated = Signal(object)

    def __init__(self, workspace, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.workspace = workspace
        self.direction = "down"
        self.frame_index = 1
        self._build_ui()
        self.refresh_choices()
        self.refresh_preview()

    def _build_ui(self):
        if self.workspace.is_mv:
            self._build_mv_ui()
            return
        self._build_generic_ui()

    def _build_generic_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(16)
        controls = QFrame()
        controls.setObjectName("CharacterGeneratorControls")
        left = QVBoxLayout(controls)
        left.setSpacing(10)
        title = QLabel("CHARACTER GENERATOR")
        title.setObjectName("SectionLabel")
        left.addWidget(title)
        self.name_edit = QLineEdit(self.workspace.recipe.id)
        self.name_edit.setPlaceholderText("Character asset name")
        left.addWidget(self.name_edit)
        self.selectors = {}
        form = QFormLayout()
        form.setSpacing(8)
        for category in LAYER_ORDER:
            combo = QComboBox()
            combo.setProperty("category", category)
            combo.currentIndexChanged.connect(lambda _i, c=category: self._select_changed(c))
            self.selectors[category] = combo
            form.addRow(category.replace("_", " ").title(), combo)
        left.addLayout(form)
        left.addStretch(1)
        self.generate_button = QPushButton("Generate Character Asset")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self._generate)
        left.addWidget(self.generate_button)
        root.addWidget(controls, 0)

        preview = QFrame()
        preview.setObjectName("CharacterGeneratorPreview")
        pv = QVBoxLayout(preview)
        pv.setContentsMargins(18, 18, 18, 18)
        pv.setSpacing(12)
        heading = QLabel("LIVE PREVIEW")
        heading.setObjectName("SectionLabel")
        pv.addWidget(heading)
        self.canvas = QLabel()
        self.canvas.setObjectName("CharacterPreviewCanvas")
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setMinimumSize(320, 320)
        pv.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(list(DIRECTIONS))
        self.direction_combo.currentTextChanged.connect(self._direction_changed)
        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self._play_toggled)
        row.addWidget(QLabel("Facing"))
        row.addWidget(self.direction_combo)
        row.addStretch(1)
        row.addWidget(self.play_button)
        pv.addLayout(row)
        self.status = QLabel("RPG-like 48×48 preset · custom artwork remains fully supported")
        self.status.setObjectName("MutedLabel")
        pv.addWidget(self.status)
        root.addWidget(preview, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self._advance)

    def _build_mv_ui(self):
        self.ground_line_visible = True
        root = QHBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(14)

        profile = QFrame()
        profile.setObjectName("CharacterGeneratorControls")
        left = QVBoxLayout(profile)
        left.addWidget(QLabel("CHARACTER PROFILE"))
        self.name_edit = QLineEdit(self.workspace.recipe.id)
        left.addWidget(self.name_edit)
        self.gender_combo = QComboBox()
        self.gender_combo.addItems(["Male", "Female", "Kid"])
        self.gender_combo.currentTextChanged.connect(self._family_changed)
        left.addWidget(self.gender_combo)
        if not self.workspace.recipe.parts.get("body"):
            self.workspace.set_body_family(self.gender_combo.currentText())
        self.category_combo = QComboBox()
        self.category_combo.addItems([c for c in LAYER_ORDER])
        self.category_combo.currentTextChanged.connect(self.refresh_choices)
        left.addWidget(self.category_combo)
        self.color_combo = QComboBox()
        for label, value in (
            ("Original", ""),
            ("Black", "#20222c"),
            ("Brown", "#754a2b"),
            ("Blonde", "#e5ad37"),
            ("Red", "#bd4242"),
            ("Blue", "#428ccc"),
            ("Green", "#59a777"),
            ("Purple", "#8d68b7"),
            ("White", "#eae7e0"),
        ):
            self.color_combo.addItem(label, value)
        self.color_combo.currentIndexChanged.connect(self._color_changed)
        left.addWidget(QLabel("PART COLOR"))
        left.addWidget(self.color_combo)
        cell_row = QHBoxLayout()
        self.cell_x_spin = QSpinBox()
        self.cell_x_spin.setRange(0, 9999)
        self.cell_x_spin.setPrefix("X ")
        self.cell_y_spin = QSpinBox()
        self.cell_y_spin.setRange(0, 9999)
        self.cell_y_spin.setPrefix("Y ")
        cell_row.addWidget(self.cell_x_spin)
        cell_row.addWidget(self.cell_y_spin)
        left.addWidget(QLabel("MAP CELL"))
        left.addLayout(cell_row)
        self.selected_label = QLabel("No parts selected")
        self.selected_label.setWordWrap(True)
        left.addWidget(self.selected_label)
        left.addStretch(1)
        self.generate_button = QPushButton("Create Character on Map")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self._generate)
        left.addWidget(self.generate_button)
        self.load_recipe_button = QPushButton("Load Character Recipe")
        self.load_recipe_button.clicked.connect(self._load_recipe)
        left.addWidget(self.load_recipe_button)
        root.addWidget(profile, 0)

        browser = QFrame()
        browser.setObjectName("CharacterPartBrowser")
        middle = QVBoxLayout(browser)
        middle.addWidget(QLabel("PARTS"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search parts")
        self.search_edit.textChanged.connect(self.refresh_choices)
        middle.addWidget(self.search_edit)
        self.part_grid = QListWidget()
        self.part_grid.setObjectName("CharacterPartGrid")
        self.part_grid.setViewMode(QListWidget.IconMode)
        self.part_grid.setIconSize(QSize(64, 64))
        self.part_grid.setResizeMode(QListWidget.Adjust)
        self.part_grid.itemSelectionChanged.connect(self._mv_part_selected)
        middle.addWidget(self.part_grid, 1)
        root.addWidget(browser, 1)

        preview = QFrame()
        preview.setObjectName("CharacterGeneratorPreview")
        right = QVBoxLayout(preview)
        right.addWidget(QLabel("SYNCHRONIZED PREVIEW"))
        self.preview_tabs = QTabWidget()
        self.walking_canvas = QLabel()
        self.walking_canvas.setObjectName("CharacterPreviewCanvas")
        self.walking_canvas.setAlignment(Qt.AlignCenter)
        self.walking_canvas.setMinimumSize(288, 384)
        self.face_canvas = QLabel()
        self.face_canvas.setAlignment(Qt.AlignCenter)
        self.face_canvas.setMinimumSize(288, 288)
        self.damaged_canvas = QLabel()
        self.damaged_canvas.setAlignment(Qt.AlignCenter)
        self.damaged_canvas.setMinimumSize(288, 96)
        self.side_view_canvas = QLabel()
        self.side_view_canvas.setAlignment(Qt.AlignCenter)
        self.side_view_canvas.setMinimumSize(576, 384)
        for canvas, name in (
            (self.walking_canvas, "Walking"),
            (self.face_canvas, "Face"),
            (self.damaged_canvas, "Damaged"),
            (self.side_view_canvas, "Side View"),
        ):
            scroll = QScrollArea()
            scroll.setWidgetResizable(False)
            scroll.setAlignment(Qt.AlignCenter)
            scroll.setWidget(canvas)
            self.preview_tabs.addTab(scroll, name)
        right.addWidget(self.preview_tabs, 1)
        self.frame_canvas = QLabel()
        self.frame_canvas.setAlignment(Qt.AlignCenter)
        self.frame_canvas.setMinimumSize(144, 144)
        frame_controls = QHBoxLayout()
        self.frame_rep_combo = QComboBox()
        self.frame_rep_combo.addItems(["Walking", "Damaged", "Side View"])
        self.frame_rep_combo.currentTextChanged.connect(self._frame_rep_changed)
        self.frame_spin = QSpinBox()
        self.frame_spin.setRange(0, 11)
        self.frame_spin.valueChanged.connect(self.refresh_preview)
        self.sheet_info = QLabel("144×192 · 3×4 · 48px frames")
        frame_controls.addWidget(QLabel("Inspect frame"))
        frame_controls.addWidget(self.frame_rep_combo)
        frame_controls.addWidget(self.frame_spin)
        frame_controls.addWidget(self.sheet_info)
        right.addLayout(frame_controls)
        right.addWidget(self.frame_canvas)
        row = QHBoxLayout()
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(list(DIRECTIONS))
        self.direction_combo.currentTextChanged.connect(self._direction_changed)
        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        self.play_button.toggled.connect(self._play_toggled)
        row.addWidget(QLabel("Facing"))
        row.addWidget(self.direction_combo)
        row.addWidget(self.play_button)
        right.addLayout(row)
        self.status = QLabel("Select a part to preview all available representations")
        right.addWidget(self.status)
        root.addWidget(preview, 2)
        self.timer = QTimer(self)
        self.timer.setInterval(180)
        self.timer.timeout.connect(self._advance)

    def refresh_choices(self):
        if self.workspace.is_mv:
            category = self.category_combo.currentText()
            selected = self.workspace.recipe.parts.get(category)
            self.part_grid.blockSignals(True)
            self.part_grid.clear()
            empty = QListWidgetItem("None")
            empty.setData(Qt.UserRole, None)
            self.part_grid.addItem(empty)
            if selected is None:
                empty.setSelected(True)
            for part in self.workspace.choices(category, self.search_edit.text(), self.gender_combo.currentText()):
                item = QListWidgetItem(f"{part.source_category} p{part.part_number}")
                item.setData(Qt.UserRole, part.id)
                if part.thumbnail and part.thumbnail.images:
                    item.setIcon(QIcon(str(part.thumbnail.images[0])))
                self.part_grid.addItem(item)
                if part.id == selected:
                    item.setSelected(True)
            self.part_grid.blockSignals(False)
            part = self.workspace._part(selected) if selected else None
            has_mask = bool(part and any(rep and rep.masks for rep in (part.walking, part.side_view, part.damaged)))
            self.color_combo.setEnabled(has_mask)
            self.color_combo.blockSignals(True)
            index = self.color_combo.findData(self.workspace.recipe.palette.get(category, ""))
            self.color_combo.setCurrentIndex(max(0, index))
            self.color_combo.blockSignals(False)
            return
        for category, combo in self.selectors.items():
            selected = self.workspace.recipe.parts.get(category)
            combo.blockSignals(True)
            combo.clear()
            combo.addItem("None", None)
            for part in self.workspace.choices(category):
                combo.addItem(part.display_name or part.id, part.id)
            idx = combo.findData(selected)
            combo.setCurrentIndex(idx if idx >= 0 else 0)
            combo.blockSignals(False)

    def _select_changed(self, category):
        self.workspace.select(category, self.selectors[category].currentData())
        self.refresh_preview()

    def _mv_part_selected(self):
        items = self.part_grid.selectedItems()
        if not items:
            return
        category = self.category_combo.currentText()
        self.workspace.select(category, items[0].data(Qt.UserRole))
        self.selected_label.setText("\n".join(f"{c}: {p}" for c, p in self.workspace.selected_summary()))
        self.refresh_choices()
        self.refresh_preview()

    def _family_changed(self, family):
        cleared = self.workspace.set_body_family(family)
        self.status.setText(
            "Changed body family; cleared " + ", ".join(cleared) if cleared else f"{family} body selected"
        )
        self.selected_label.setText("\n".join(f"{c}: {p}" for c, p in self.workspace.selected_summary()))
        self.refresh_choices()
        self.refresh_preview()

    def _color_changed(self, _index):
        category = self.category_combo.currentText()
        color = self.color_combo.currentData()
        if color:
            self.workspace.recipe.palette[category] = color
        else:
            self.workspace.recipe.palette.pop(category, None)
        self.refresh_preview()

    def _direction_changed(self, value):
        self.direction = value
        self.frame_index = 1
        if self.workspace.is_mv and self.frame_rep_combo.currentText() == "Walking":
            self.frame_spin.setValue(("down", "left", "right", "up").index(value) * 3 + 1)
        self.refresh_preview()

    def _frame_rep_changed(self, value):
        label, maximum = {
            "Walking": ("144×192 · 3×4 · 48px frames", 11),
            "Damaged": ("144×48 · 3×1 · 48px frames", 2),
            "Side View": ("576×384 · 9×6 · 64px frames", 53),
        }[value]
        self.sheet_info.setText(label)
        self.frame_spin.setRange(0, maximum)
        self.refresh_preview()

    def _play_toggled(self, on):
        self.play_button.setText("Pause" if on else "Play")
        self.timer.start() if on else self.timer.stop()

    def _advance(self):
        if self.workspace.is_mv:
            count = self.frame_spin.maximum() + 1
            self.frame_spin.setValue((self.frame_spin.value() + 1) % count)
            return
        count = self.workspace.generator.preset.frames_per_direction
        self.frame_index = (self.frame_index + 1) % count
        self.refresh_preview()

    def refresh_preview(self):
        if self.workspace.is_mv:
            inspected = self.frame_rep_combo.currentText()
            index = self.frame_spin.value()
            if inspected == "Walking":
                directions = ("down", "left", "right", "up")
                frame = self.workspace.preview_frame(directions[index // 3], index % 3)
            else:
                source = self.workspace.preview_representation("damaged" if inspected == "Damaged" else "side_view")
                cell = 48 if inspected == "Damaged" else 64
                columns = 3 if inspected == "Damaged" else 9
                frame = (
                    None
                    if source is None
                    else source.crop(
                        (
                            (index % columns) * cell,
                            (index // columns) * cell,
                            (index % columns + 1) * cell,
                            (index // columns + 1) * cell,
                        )
                    )
                )
            if frame is None:
                self.frame_canvas.setPixmap(QPixmap())
            else:
                single = character_grid_preview(frame) if inspected == "Walking" else checkerboard_preview(frame)
                self.frame_canvas.setPixmap(
                    self._pixmap(single).scaled(144, 144, Qt.KeepAspectRatio, Qt.FastTransformation)
                )
            for name, canvas, scale in (
                ("walking", self.walking_canvas, 2),
                ("face", self.face_canvas, 2),
                ("damaged", self.damaged_canvas, 2),
                ("side_view", self.side_view_canvas, 1),
            ):
                image = self.workspace.preview_representation(name)
                if image is None:
                    canvas.setPixmap(QPixmap())
                    canvas.setText(self.workspace.unavailable_reason(name))
                else:
                    canvas.setText("")
                    pixmap = self._pixmap(checkerboard_preview(image))
                    if scale != 1:
                        pixmap = pixmap.scaled(
                            image.width * scale, image.height * scale, Qt.IgnoreAspectRatio, Qt.FastTransformation
                        )
                    canvas.setPixmap(pixmap)
            return
        image = character_grid_preview(self.workspace.preview_frame(self.direction, self.frame_index))
        pix = self._pixmap(image).scaled(288, 288, Qt.KeepAspectRatio, Qt.FastTransformation)
        self.canvas.setPixmap(pix)

    @staticmethod
    def _pixmap(image):
        raw = image.tobytes("raw", "RGBA")
        qimg = QImage(raw, image.width, image.height, QImage.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimg)

    def _generate(self):
        self.workspace.recipe.id = self.name_edit.text().strip() or "new_character"
        out = QFileDialog.getExistingDirectory(self, "Generate Character Asset")
        if not out:
            return
        result = self.workspace.generate(out)
        if self.workspace.is_mv:
            self.status.setText(f"Generated walking, face and side-view: {result.output_dir}")
        else:
            self.status.setText(f"Generated {result.width}×{result.height}: {result.sheet_path}")
        self.generated.emit(result)

    def _load_recipe(self):
        filename, _ = QFileDialog.getOpenFileName(
            self, "Load Character Recipe", "", "Character Bundle (character.bundle.json)"
        )
        if not filename:
            return
        try:
            self.workspace.load_bundle(filename)
        except (OSError, ValueError, KeyError) as exc:
            self.status.setText(f"Cannot load character recipe: {exc}")
            return
        self.name_edit.setText(self.workspace.recipe.id)
        self.gender_combo.blockSignals(True)
        self.gender_combo.setCurrentText(self.workspace.recipe.body_family or "Male")
        self.gender_combo.blockSignals(False)
        self.selected_label.setText("\n".join(f"{c}: {p}" for c, p in self.workspace.selected_summary()))
        self.refresh_choices()
        self.refresh_preview()
        self.status.setText(f"Loaded editable recipe: {filename}")
