"""Particle Effects editor (VFX-01): the project's particle effects, every emitter setting, a live preview.

The preview runs the same ``ParticleSystem`` the game runs, with the form's current values, so a change
shows at once; Apply records it (one undo step). New effects start from a preset (fire, smoke, sparkle,
heal, poison, explosion, rain splash) and every value can then be changed.
"""

from __future__ import annotations

import math
from dataclasses import fields as dataclass_fields

from PySide6.QtCore import QPointF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from asteria.presentation.particles import (
    EMITTER_SHAPES,
    PARTICLE_BLENDS,
    PARTICLE_SHAPES,
    PRESETS,
    ParticleEffectDefinition,
    ParticleSystem,
)

from .particle_authoring import ParticleAuthoringController, ParticleAuthoringError
from .responsive_form import ResponsiveForm

LABELS = {
    "rate": "Rate (per second)",
    "burst": "Burst at start",
    "duration": "Emit for (s, 0 = loop)",
    "max_particles": "Max particles",
    "lifetime": "Lifetime (s)",
    "speed": "Speed",
    "direction": "Direction (°, -90 = up)",
    "spread": "Spread (± °)",
    "gravity": "Gravity",
    "drag": "Drag (per second)",
    "shape": "Emitter shape",
    "shape_size": "Shape size",
    "size": "Size",
    "size_jitter": "Size jitter (±)",
    "color_start": "Colour at birth",
    "color_end": "Colour at death",
    "particle": "Particle",
    "image": "Image (image particles)",
    "blend": "Blend",
    "spin": "Spin (°/s)",
    "local": "Move with the emitter",
}
PAIR_NAMES = {
    "lifetime": ("min", "max"),
    "speed": ("min", "max"),
    "gravity": ("x", "y"),
    "shape_size": ("w / radius", "h"),
    "size": ("birth", "death"),
    "spin": ("min", "max"),
}
CHOICES = {"shape": EMITTER_SHAPES, "particle": PARTICLE_SHAPES, "blend": PARTICLE_BLENDS}


def _spin(value, *, integer=False):
    box = QSpinBox() if integer else QDoubleSpinBox()
    box.setRange(0 if integer else -1_000_000, 1_000_000)
    if not integer:
        box.setDecimals(2)
    box.setValue(value)
    return box


class _ColorButton(QPushButton):
    def __init__(self, rgba, parent=None):
        super().__init__(parent)
        self.rgba = tuple(rgba)
        self.clicked.connect(self._pick)
        self._show()

    def _show(self):
        r, g, b, a = self.rgba
        self.setText(f"{r}, {g}, {b}  α {a}")
        text = "#111" if (r * 299 + g * 587 + b * 114) / 1000 > 140 else "#fff"
        self.setStyleSheet(f"background: rgba({r},{g},{b},{max(a, 60)}); color: {text};")

    def _pick(self):
        color = QColorDialog.getColor(QColor(*self.rgba), self, "Particle colour", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.set_rgba((color.red(), color.green(), color.blue(), color.alpha()))

    def set_rgba(self, rgba):
        self.rgba = tuple(int(v) for v in rgba)
        self._show()
        changed = getattr(self, "changed", None)
        if changed is not None:
            changed()


class ParticlePreview(QWidget):
    """Runs a ParticleSystem at 30 fps and paints it (alpha or additive) around the emitter point."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(260, 220)
        self.system = None
        self.zoom = 2.0
        self.image = None  # QPixmap for image particles
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._tick)
        self.timer.start(33)

    def set_definition(self, definition, image=None):
        self.image = image
        self.system = None if definition is None else ParticleSystem(definition, seed="preview")

    def restart(self):
        if self.system is not None:
            self.system = ParticleSystem(self.system.definition, seed="preview")

    def _tick(self):
        if self.system is None or not self.isVisible():
            return
        self.system.update(0.033)
        if self.system.finished:  # one-shots replay so they stay visible while editing
            self.restart()
        self.update()

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor(18, 21, 30))
        ox, oy = self.width() / 2, self.height() * 0.62
        painter.setPen(QPen(QColor(70, 78, 98), 1, Qt.DashLine))
        painter.drawLine(QPointF(ox - 8, oy), QPointF(ox + 8, oy))
        painter.drawLine(QPointF(ox, oy - 8), QPointF(ox, oy + 8))
        if self.system is None:
            painter.end()
            return
        d = self.system.definition
        if d.blend == "add":
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.setPen(Qt.NoPen)
        z = self.zoom
        for p in self.system.views():
            color = QColor(*p.color)
            x, y, r = ox + p.x * z, oy + p.y * z, max(0.5, p.size * z / 2)
            if d.particle == "image" and self.image is not None:
                painter.save()
                painter.setOpacity(p.color[3] / 255)
                painter.translate(x, y)
                painter.rotate(p.angle)
                side = r * 2
                painter.drawPixmap(int(-side / 2), int(-side / 2), int(side), int(side), self.image)
                painter.restore()
            elif d.particle == "spark":
                a = math.radians(p.angle)
                dx, dy = math.cos(a) * r * 1.6, math.sin(a) * r * 1.6
                painter.setPen(QPen(color, max(1.0, r / 3)))
                painter.drawLine(QPointF(x - dx, y - dy), QPointF(x + dx, y + dy))
                painter.drawLine(QPointF(x + dy, y - dx), QPointF(x - dy, y + dx))
                painter.setPen(Qt.NoPen)
            elif d.particle in ("square", "image"):
                a = math.radians(p.angle + 45)
                k = r * math.sqrt(2)
                points = [
                    QPointF(x + math.cos(a + i * math.pi / 2) * k, y + math.sin(a + i * math.pi / 2) * k)
                    for i in range(4)
                ]
                painter.setBrush(color)
                painter.drawPolygon(QPolygonF(points))
            else:
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x, y), r, r)
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(QColor(150, 160, 185))
        painter.drawText(8, self.height() - 8, f"{self.system.count} particles")
        painter.end()


class ParticleEffectWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.api = ParticleAuthoringController(document)
        self.inputs = {}
        self._loading = False

        self.list = QListWidget()
        self.list.currentTextChanged.connect(self._select)
        new = QPushButton("New Effect…")
        new.clicked.connect(self.new_effect)
        duplicate = QPushButton("Duplicate…")
        duplicate.clicked.connect(self.duplicate_effect)
        delete = QPushButton("Delete")
        delete.clicked.connect(self.delete_effect)
        left = QVBoxLayout()
        title = QLabel("Particle Effects")
        title.setObjectName("SectionTitle")
        left.addWidget(title)
        left.addWidget(self.list, 1)
        for button in (new, duplicate, delete):
            left.addWidget(button)
        left_panel = QWidget()
        left_panel.setLayout(left)

        self.form = ResponsiveForm(column_width=230)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.form)
        self.status = QLabel()
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        self.usage = QLabel()
        self.usage.setObjectName("MutedLabel")
        self.usage.setWordWrap(True)
        apply = QPushButton("Apply")
        apply.clicked.connect(self.apply)
        revert = QPushButton("Revert")
        revert.clicked.connect(lambda: self._select(self.selected_id))
        buttons = QHBoxLayout()
        buttons.addWidget(apply)
        buttons.addWidget(revert)
        buttons.addStretch(1)
        middle = QVBoxLayout()
        middle.addWidget(scroll, 1)
        middle.addWidget(self.status)
        middle.addWidget(self.usage)
        middle.addLayout(buttons)
        middle_panel = QWidget()
        middle_panel.setLayout(middle)

        self.preview = ParticlePreview()
        restart = QPushButton("Restart Preview")
        restart.clicked.connect(self.preview.restart)
        right = QVBoxLayout()
        right.addWidget(self.preview, 1)
        right.addWidget(restart)
        right_panel = QWidget()
        right_panel.setLayout(right)

        splitter = QSplitter()
        splitter.addWidget(left_panel)
        splitter.addWidget(middle_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(1, 2)
        splitter.setStretchFactor(2, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(splitter)
        self._build_form()
        self.refresh()

    def showEvent(self, event):  # noqa: N802 - Qt API: pick up edits made elsewhere (undo, other tools)
        super().showEvent(event)
        self.refresh()

    # -- form -------------------------------------------------------------------------------------
    def _build_form(self):
        sample = ParticleEffectDefinition("sample")
        for f in dataclass_fields(ParticleEffectDefinition):
            if f.name == "effect_id":
                continue
            value = getattr(sample, f.name)
            if f.name in CHOICES:
                widget = QComboBox()
                widget.addItems(CHOICES[f.name])
                widget.currentTextChanged.connect(self._edited)
            elif f.name == "image":
                widget = QComboBox()
                widget.setEditable(True)
                widget.currentTextChanged.connect(self._edited)
            elif f.name.startswith("color"):
                widget = _ColorButton(value)
                widget.changed = self._edited
            elif isinstance(value, bool):
                widget = QCheckBox()
                widget.toggled.connect(self._edited)
            elif isinstance(value, tuple):
                widget = QWidget()
                row = QHBoxLayout(widget)
                row.setContentsMargins(0, 0, 0, 0)
                widget.parts = []
                for name, part in zip(PAIR_NAMES[f.name], value, strict=True):
                    box = _spin(part)
                    box.setToolTip(name)
                    box.setPrefix(f"{name} ")
                    box.valueChanged.connect(self._edited)
                    row.addWidget(box)
                    widget.parts.append(box)
            else:
                widget = _spin(value, integer=isinstance(value, int))
                widget.valueChanged.connect(self._edited)
            self.inputs[f.name] = widget
            self.form.add_row(LABELS.get(f.name, f.name), widget)

    def _set_inputs(self, definition):
        self._loading = True
        try:
            from .image_tools import icon_choices

            image = self.inputs["image"]
            image.clear()
            image.addItem("")
            for choice, icon in icon_choices(self.document):
                if icon is not None:
                    image.addItem(icon, choice)
                else:
                    image.addItem(choice)
            for name, widget in self.inputs.items():
                value = getattr(definition, name)
                if name in CHOICES:
                    widget.setCurrentText(value)
                elif name == "image":
                    widget.setCurrentText(value)
                elif name.startswith("color"):
                    widget.rgba = tuple(value)
                    widget._show()
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif hasattr(widget, "parts"):
                    for box, part in zip(widget.parts, value, strict=True):
                        box.setValue(part)
                else:
                    widget.setValue(value)
        finally:
            self._loading = False

    def form_definition(self):
        """The definition the form shows now (raises ValueError when a value is not accepted)."""
        values = {}
        for name, widget in self.inputs.items():
            if name in CHOICES or name == "image":
                values[name] = widget.currentText().strip()
            elif name.startswith("color"):
                values[name] = widget.rgba
            elif isinstance(widget, QCheckBox):
                values[name] = widget.isChecked()
            elif hasattr(widget, "parts"):
                values[name] = tuple(box.value() for box in widget.parts)
            else:
                values[name] = widget.value()
        return ParticleEffectDefinition(self.selected_id or "preview", **values)

    def _edited(self, *_):
        if self._loading:
            return
        try:
            definition = self.form_definition()
        except (TypeError, ValueError) as exc:
            self.status.setText(f"Not applied: {exc}")
            return
        self.status.setText("Changed — Apply to keep it (the preview already shows it).")
        self._preview(definition)

    def _preview(self, definition):
        image = None
        if definition.particle == "image" and definition.image:
            from .image_tools import icon_choices

            image = next((i for c, i in icon_choices(self.document) if c == definition.image), None)
            image = image.pixmap(32, 32) if image is not None else None
        self.preview.set_definition(definition, image)

    # -- list -------------------------------------------------------------------------------------
    @property
    def selected_id(self):
        item = self.list.currentItem()
        return item.text() if item is not None else None

    def refresh(self, select=None):
        if self.document.project is None:
            return
        current = select or self.selected_id
        self.list.blockSignals(True)
        self.list.clear()
        ids = self.api.ids()
        self.list.addItems(list(ids))
        self.list.blockSignals(False)
        if ids:
            self.list.setCurrentRow(ids.index(current) if current in ids else 0)
            self._select(self.selected_id)
        else:
            self.preview.set_definition(None)
            self.status.setText("No particle effects yet — New Effect… starts from a preset.")

    def _select(self, effect_id):
        if not effect_id:
            return
        try:
            definition = self.api.definition(effect_id)
        except ParticleAuthoringError as exc:
            self.status.setText(str(exc))
            return
        self._set_inputs(definition)
        self._preview(definition)
        used = self.api.usages(effect_id)
        self.usage.setText("Used by: " + ", ".join(used) if used else "Not used yet")
        self.status.setText("")

    def apply(self):
        effect_id = self.selected_id
        if effect_id is None:
            return False
        try:
            changed = self.api.update(effect_id, self.form_definition())
        except (TypeError, ValueError, ParticleAuthoringError) as exc:
            self.status.setText(f"Not applied: {exc}")
            return False
        self.status.setText("Applied." if changed else "No changes.")
        if changed:
            self.changed.emit()
        return changed

    def new_effect(self, effect_id=None, preset_name=None):
        if preset_name is None:
            preset_name, ok = QInputDialog.getItem(self, "New Particle Effect", "Start from:", list(PRESETS), 0, False)
            if not ok:
                return None
        if effect_id is None:
            effect_id, ok = QInputDialog.getText(self, "New Particle Effect", "Id:", text=f"particles.{preset_name}")
            if not ok:
                return None
        try:
            created = self.api.create(effect_id, preset_name)
        except ParticleAuthoringError as exc:
            QMessageBox.warning(self, "New Particle Effect", str(exc))
            return None
        self.refresh(select=created)
        self.changed.emit()
        return created

    def duplicate_effect(self, new_id=None):
        source = self.selected_id
        if source is None:
            return None
        if new_id is None:
            new_id, ok = QInputDialog.getText(self, "Duplicate Particle Effect", "New id:", text=f"{source}_copy")
            if not ok:
                return None
        try:
            created = self.api.duplicate(source, new_id)
        except ParticleAuthoringError as exc:
            QMessageBox.warning(self, "Duplicate Particle Effect", str(exc))
            return None
        self.refresh(select=created)
        self.changed.emit()
        return created

    def delete_effect(self, *, confirm=None):
        effect_id = self.selected_id
        if effect_id is None:
            return False
        used = self.api.usages(effect_id)
        if used:
            text = f"{effect_id} is used by {', '.join(used)}. Delete it anyway? (Undo restores it.)"
            answer = confirm if confirm is not None else QMessageBox.question(self, "Delete Particle Effect", text)
            if answer not in (True, QMessageBox.Yes):
                return False
        self.api.delete(effect_id)
        self.refresh()
        self.changed.emit()
        return True
