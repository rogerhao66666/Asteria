from __future__ import annotations

try:
    from PySide6.QtCore import Qt, QTimer, Signal
    from PySide6.QtGui import QImage, QPixmap
    from PySide6.QtWidgets import (
        QWidget, QLabel, QComboBox, QPushButton, QHBoxLayout, QVBoxLayout,
        QFormLayout, QFrame, QLineEdit, QFileDialog
    )
except ImportError:
    QWidget = object
    Qt = QTimer = Signal = QImage = QPixmap = None

from asteria.assets.character_generator import DIRECTIONS, LAYER_ORDER


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

    def refresh_choices(self):
        for category, combo in self.selectors.items():
            selected = self.workspace.recipe.parts.get(category)
            combo.blockSignals(True); combo.clear(); combo.addItem("None", None)
            for part in self.workspace.choices(category): combo.addItem(part.display_name or part.id, part.id)
            idx = combo.findData(selected); combo.setCurrentIndex(idx if idx >= 0 else 0); combo.blockSignals(False)

    def _select_changed(self, category):
        self.workspace.select(category, self.selectors[category].currentData()); self.refresh_preview()

    def _direction_changed(self, value): self.direction = value; self.frame_index = 1; self.refresh_preview()
    def _play_toggled(self, on): self.play_button.setText("Pause" if on else "Play"); self.timer.start() if on else self.timer.stop()
    def _advance(self):
        self.frame_index = (self.frame_index + 1) % self.workspace.generator.preset.frames_per_direction; self.refresh_preview()

    def refresh_preview(self):
        image = self.workspace.preview_frame(self.direction, self.frame_index)
        raw = image.tobytes("raw", "RGBA")
        qimg = QImage(raw, image.width, image.height, QImage.Format_RGBA8888).copy()
        pix = QPixmap.fromImage(qimg).scaled(288,288,Qt.KeepAspectRatio,Qt.FastTransformation)
        self.canvas.setPixmap(pix)

    def _generate(self):
        self.workspace.recipe.id = self.name_edit.text().strip() or "new_character"
        out = QFileDialog.getExistingDirectory(self, "Generate Character Asset")
        if not out: return
        result = self.workspace.generate(out); self.status.setText(f"Generated {result.width}×{result.height}: {result.sheet_path}")
        self.generated.emit(result)
