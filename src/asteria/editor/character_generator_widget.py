from __future__ import annotations

try:
    from PySide6.QtCore import Qt, QTimer, Signal, QSize
    from PySide6.QtGui import QImage, QPixmap, QIcon
    from PySide6.QtWidgets import (
        QWidget, QLabel, QComboBox, QPushButton, QHBoxLayout, QVBoxLayout,
        QFormLayout, QFrame, QLineEdit, QFileDialog, QListWidget, QListWidgetItem,
        QTabWidget
    )
except ImportError:
    QWidget = object
    Qt = QTimer = Signal = QImage = QPixmap = None

from asteria.assets.character_generator import DIRECTIONS, LAYER_ORDER
from asteria.graphics.character_placement import CharacterPlacement, frame_rect_at_standing_point
from PIL import Image, ImageDraw


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
        root = QHBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(16)
        controls = QFrame(); controls.setObjectName("CharacterGeneratorControls")
        left = QVBoxLayout(controls); left.setSpacing(10)
        title = QLabel("CHARACTER GENERATOR"); title.setObjectName("SectionLabel"); left.addWidget(title)
        self.name_edit = QLineEdit(self.workspace.recipe.id); self.name_edit.setPlaceholderText("Character asset name")
        left.addWidget(self.name_edit)
        self.selectors = {}
        form = QFormLayout(); form.setSpacing(8)
        for category in LAYER_ORDER:
            combo = QComboBox(); combo.setProperty("category", category)
            combo.currentIndexChanged.connect(lambda _i, c=category: self._select_changed(c))
            self.selectors[category] = combo; form.addRow(category.replace('_',' ').title(), combo)
        left.addLayout(form); left.addStretch(1)
        self.generate_button = QPushButton("Generate Character Asset")
        self.generate_button.setObjectName("PrimaryButton"); self.generate_button.clicked.connect(self._generate)
        left.addWidget(self.generate_button)
        root.addWidget(controls, 0)

        preview = QFrame(); preview.setObjectName("CharacterGeneratorPreview")
        pv = QVBoxLayout(preview); pv.setContentsMargins(18,18,18,18); pv.setSpacing(12)
        heading = QLabel("LIVE PREVIEW"); heading.setObjectName("SectionLabel"); pv.addWidget(heading)
        self.canvas = QLabel(); self.canvas.setObjectName("CharacterPreviewCanvas")
        self.canvas.setAlignment(Qt.AlignCenter); self.canvas.setMinimumSize(320,320)
        pv.addWidget(self.canvas, 1)
        row = QHBoxLayout()
        self.direction_combo = QComboBox(); self.direction_combo.addItems(list(DIRECTIONS)); self.direction_combo.currentTextChanged.connect(self._direction_changed)
        self.play_button = QPushButton("Play"); self.play_button.setCheckable(True); self.play_button.toggled.connect(self._play_toggled)
        row.addWidget(QLabel("Facing")); row.addWidget(self.direction_combo); row.addStretch(1); row.addWidget(self.play_button); pv.addLayout(row)
        self.status = QLabel("RPG-like 48×48 preset · custom artwork remains fully supported"); self.status.setObjectName("MutedLabel"); pv.addWidget(self.status)
        root.addWidget(preview, 1)
        self.timer = QTimer(self); self.timer.setInterval(180); self.timer.timeout.connect(self._advance)

    def _build_mv_ui(self):
        self.ground_line_visible = True
        root = QHBoxLayout(self); root.setContentsMargins(14,14,14,14); root.setSpacing(14)

        profile = QFrame(); profile.setObjectName("CharacterGeneratorControls")
        left = QVBoxLayout(profile)
        left.addWidget(QLabel("CHARACTER PROFILE"))
        self.name_edit = QLineEdit(self.workspace.recipe.id); left.addWidget(self.name_edit)
        self.gender_combo = QComboBox(); self.gender_combo.addItems(["Male", "Female"])
        self.gender_combo.currentTextChanged.connect(self.refresh_choices); left.addWidget(self.gender_combo)
        self.category_combo = QComboBox(); self.category_combo.addItems([c for c in LAYER_ORDER])
        self.category_combo.currentTextChanged.connect(self.refresh_choices); left.addWidget(self.category_combo)
        self.selected_label = QLabel("No parts selected"); self.selected_label.setWordWrap(True); left.addWidget(self.selected_label)
        left.addStretch(1)
        self.generate_button = QPushButton("Create Character Bundle"); self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self._generate); left.addWidget(self.generate_button)
        root.addWidget(profile, 0)

        browser = QFrame(); browser.setObjectName("CharacterPartBrowser")
        middle = QVBoxLayout(browser); middle.addWidget(QLabel("PARTS"))
        self.search_edit = QLineEdit(); self.search_edit.setPlaceholderText("Search parts")
        self.search_edit.textChanged.connect(self.refresh_choices); middle.addWidget(self.search_edit)
        self.part_grid = QListWidget(); self.part_grid.setObjectName("CharacterPartGrid")
        self.part_grid.setViewMode(QListWidget.IconMode); self.part_grid.setIconSize(QSize(64,64)); self.part_grid.setResizeMode(QListWidget.Adjust)
        self.part_grid.itemSelectionChanged.connect(self._mv_part_selected); middle.addWidget(self.part_grid, 1)
        root.addWidget(browser, 1)

        preview = QFrame(); preview.setObjectName("CharacterGeneratorPreview")
        right = QVBoxLayout(preview); right.addWidget(QLabel("SYNCHRONIZED PREVIEW"))
        self.preview_tabs = QTabWidget()
        self.walking_canvas = QLabel(); self.walking_canvas.setObjectName("CharacterPreviewCanvas"); self.walking_canvas.setAlignment(Qt.AlignCenter); self.walking_canvas.setMinimumSize(288,288)
        self.face_canvas = QLabel(); self.face_canvas.setAlignment(Qt.AlignCenter); self.face_canvas.setMinimumSize(288,288)
        self.side_view_canvas = QLabel(); self.side_view_canvas.setAlignment(Qt.AlignCenter); self.side_view_canvas.setMinimumSize(576,384)
        self.preview_tabs.addTab(self.walking_canvas, "Walking"); self.preview_tabs.addTab(self.face_canvas, "Face"); self.preview_tabs.addTab(self.side_view_canvas, "Side View")
        right.addWidget(self.preview_tabs, 1)
        row = QHBoxLayout(); self.direction_combo = QComboBox(); self.direction_combo.addItems(list(DIRECTIONS)); self.direction_combo.currentTextChanged.connect(self._direction_changed)
        self.play_button = QPushButton("Play"); self.play_button.setCheckable(True); self.play_button.toggled.connect(self._play_toggled)
        row.addWidget(QLabel("Facing")); row.addWidget(self.direction_combo); row.addWidget(self.play_button); right.addLayout(row)
        self.status = QLabel("Select a part to preview all available representations"); right.addWidget(self.status)
        root.addWidget(preview, 2)
        self.timer = QTimer(self); self.timer.setInterval(180); self.timer.timeout.connect(self._advance)

    def refresh_choices(self):
        if self.workspace.is_mv:
            category = self.category_combo.currentText()
            selected = self.workspace.recipe.parts.get(category)
            self.part_grid.blockSignals(True); self.part_grid.clear()
            for part in self.workspace.choices(category, self.search_edit.text(), self.gender_combo.currentText()):
                item = QListWidgetItem(f"{part.source_category} p{part.part_number}")
                item.setData(Qt.UserRole, part.id)
                if part.thumbnail and part.thumbnail.images:
                    item.setIcon(QIcon(str(part.thumbnail.images[0])))
                self.part_grid.addItem(item)
                if part.id == selected: item.setSelected(True)
            self.part_grid.blockSignals(False)
            return
        for category, combo in self.selectors.items():
            selected = self.workspace.recipe.parts.get(category)
            combo.blockSignals(True); combo.clear(); combo.addItem("None", None)
            for part in self.workspace.choices(category): combo.addItem(part.display_name or part.id, part.id)
            idx = combo.findData(selected); combo.setCurrentIndex(idx if idx >= 0 else 0); combo.blockSignals(False)

    def _select_changed(self, category):
        self.workspace.select(category, self.selectors[category].currentData()); self.refresh_preview()

    def _mv_part_selected(self):
        items = self.part_grid.selectedItems()
        if not items: return
        category = self.category_combo.currentText()
        self.workspace.select(category, items[0].data(Qt.UserRole))
        self.selected_label.setText("\n".join(f"{c}: {p}" for c,p in self.workspace.selected_summary()))
        self.refresh_preview()

    def _direction_changed(self, value): self.direction = value; self.frame_index = 1; self.refresh_preview()
    def _play_toggled(self, on): self.play_button.setText("Pause" if on else "Play"); self.timer.start() if on else self.timer.stop()
    def _advance(self):
        count = 3 if self.workspace.is_mv else self.workspace.generator.preset.frames_per_direction
        self.frame_index = (self.frame_index + 1) % count; self.refresh_preview()

    def refresh_preview(self):
        if self.workspace.is_mv:
            walking = character_grid_preview(self.workspace.preview_frame(self.direction, self.frame_index))
            self.walking_canvas.setPixmap(self._pixmap(walking).scaled(288,288,Qt.KeepAspectRatio,Qt.FastTransformation))
            for name, canvas in (("face", self.face_canvas), ("side_view", self.side_view_canvas)):
                image = self.workspace.preview_representation(name)
                if image is None:
                    canvas.setPixmap(QPixmap()); canvas.setText(self.workspace.unavailable_reason(name))
                else:
                    canvas.setText(""); canvas.setPixmap(self._pixmap(image))
            return
        image = character_grid_preview(self.workspace.preview_frame(self.direction, self.frame_index))
        pix = self._pixmap(image).scaled(288,288,Qt.KeepAspectRatio,Qt.FastTransformation)
        self.canvas.setPixmap(pix)

    @staticmethod
    def _pixmap(image):
        raw = image.tobytes("raw", "RGBA")
        qimg = QImage(raw, image.width, image.height, QImage.Format_RGBA8888).copy()
        return QPixmap.fromImage(qimg)

    def _generate(self):
        self.workspace.recipe.id = self.name_edit.text().strip() or "new_character"
        out = QFileDialog.getExistingDirectory(self, "Generate Character Asset")
        if not out: return
        result = self.workspace.generate(out)
        if self.workspace.is_mv: self.status.setText(f"Generated walking, face and side-view: {result.output_dir}")
        else: self.status.setText(f"Generated {result.width}×{result.height}: {result.sheet_path}")
        self.generated.emit(result)
