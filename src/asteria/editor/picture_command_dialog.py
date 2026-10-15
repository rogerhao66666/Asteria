"""Structured editor and screen-space preview for picture world commands."""

from pathlib import Path

from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from .scene_render import resolve_texture_source

PICTURE_COMMANDS = (
    "SHOW_PICTURE",
    "MOVE_PICTURE",
    "SET_PICTURE_FRAME",
    "ERASE_PICTURE",
)


class _PicturePreview(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setMinimumSize(280, 180)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 26, 30))
        stage = self.owner.stage_size
        scale = min(self.width() / stage[0], self.height() / stage[1])
        stage_w, stage_h = stage[0] * scale, stage[1] * scale
        ox, oy = (self.width() - stage_w) / 2, (self.height() - stage_h) / 2
        painter.setPen(QPen(QColor(78, 82, 92), 1))
        painter.drawRect(int(ox), int(oy), int(stage_w), int(stage_h))
        x = ox + self.owner.x.value() * scale
        y = oy + self.owner.y.value() * scale
        pixmap = self.owner.frame_pixmap()
        if not pixmap.isNull():
            width = pixmap.width() * self.owner.picture_scale.value() * scale
            height = pixmap.height() * self.owner.picture_scale.value() * scale
            painter.setOpacity(self.owner.opacity.value())
            painter.drawPixmap(int(x), int(y), max(1, round(width)), max(1, round(height)), pixmap)
            painter.setOpacity(1.0)
        else:
            painter.setPen(QPen(QColor(105, 220, 210), 1))
            painter.drawRect(int(x), int(y), 36 * scale, 24 * scale)
            painter.drawText(int(x) + 4, int(y) + 16 * scale, self.owner.picture_id.text())


class PictureCommandDialog(QDialog):
    """Edit the exact argument shape consumed by one of the four picture commands."""

    stage_size = (816.0, 624.0)
    _fields = {
        "SHOW_PICTURE": {
            "picture_id",
            "asset_id",
            "x",
            "y",
            "scale",
            "opacity",
            "frame",
            "columns",
            "rows",
            "layer",
            "click_event",
        },
        "MOVE_PICTURE": {
            "picture_id",
            "x",
            "y",
            "scale",
            "opacity",
            "duration",
            "easing",
        },
        "SET_PICTURE_FRAME": {"picture_id", "frame"},
        "ERASE_PICTURE": {"picture_id"},
    }

    def __init__(self, command, args=None, *, document=None, parent=None):
        super().__init__(parent)
        self.document = document
        self._initial_args = dict(args or {})
        self.setWindowTitle("Picture Command")
        root = QVBoxLayout(self)
        content = QHBoxLayout()
        form_box = QWidget(self)
        form = QFormLayout(form_box)
        self.command = QComboBox(form_box)
        self.command.addItems(PICTURE_COMMANDS)
        self.command.setCurrentText(str(command).upper())
        self.picture_id = QLineEdit(self._text("picture_id", "picture_1"), form_box)
        self.asset_id = QLineEdit(self._text("asset_id", ""), form_box)
        self.x = self._float("x", 0, form_box)
        self.y = self._float("y", 0, form_box)
        self.picture_scale = self._float("scale", 1, form_box, maximum=100)
        self.opacity = self._float("opacity", 1, form_box, maximum=1)
        self.frame = self._int("frame", 0, form_box)
        self.columns = self._int("columns", 1, form_box, minimum=1)
        self.rows = self._int("rows", 1, form_box, minimum=1)
        self.layer = QLineEdit(self._text("layer", "screen"), form_box)
        self.click_event = QLineEdit(self._text("click_event", ""), form_box)
        self.duration = self._float("duration", 0, form_box, maximum=3600)
        self.easing = QComboBox(form_box)
        self.easing.addItems(("linear", "ease_in", "ease_out", "ease_in_out"))
        self.easing.setCurrentText(self._text("easing", "linear"))
        self._form_fields = {
            "command": self.command,
            "picture_id": self.picture_id,
            "asset_id": self.asset_id,
            "x": self.x,
            "y": self.y,
            "scale": self.picture_scale,
            "opacity": self.opacity,
            "frame": self.frame,
            "columns": self.columns,
            "rows": self.rows,
            "layer": self.layer,
            "click_event": self.click_event,
            "duration": self.duration,
            "easing": self.easing,
        }
        labels = {
            "command": "Command",
            "picture_id": "Picture ID",
            "asset_id": "Texture asset ID",
            "x": "X",
            "y": "Y",
            "scale": "Scale",
            "opacity": "Opacity",
            "frame": "Frame",
            "columns": "Sheet columns",
            "rows": "Sheet rows",
            "layer": "Layer",
            "click_event": "Click event",
            "duration": "Move duration (seconds)",
            "easing": "Easing",
        }
        for name, field in self._form_fields.items():
            form.addRow(labels[name], field)
        self.preview = _PicturePreview(self)
        content.addWidget(form_box, 1)
        content.addWidget(self.preview, 1)
        root.addLayout(content)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)
        self.command.currentTextChanged.connect(self._sync_command_fields)
        for field in (
            self.asset_id,
            self.x,
            self.y,
            self.picture_scale,
            self.opacity,
            self.frame,
            self.columns,
            self.rows,
        ):
            signal = field.textChanged if isinstance(field, QLineEdit) else field.valueChanged
            signal.connect(self.preview.update)
        self._sync_command_fields()

    def _text(self, key, default):
        value = self._initial_args.get(key, default)
        return str(value if value is not None else default)

    def _float(self, key, default, parent, *, maximum=1000000):
        field = QDoubleSpinBox(parent)
        field.setRange(-1000000, maximum)
        field.setDecimals(3)
        field.setValue(float(self._initial_args.get(key, default)))
        return field

    def _int(self, key, default, parent, *, minimum=0):
        field = QSpinBox(parent)
        field.setRange(minimum, 1000000)
        field.setValue(int(self._initial_args.get(key, default)))
        return field

    def _sync_command_fields(self):
        active = self._fields[self.command.currentText()]
        for name, field in self._form_fields.items():
            field.setEnabled(name == "command" or name in active)
        self.preview.update()

    def frame_pixmap(self):
        if self.document is None or self.document.project is None:
            return QPixmap()
        path = resolve_texture_source(self.document, self.asset_id.text().strip())
        if path is None or not Path(path).is_file():
            return QPixmap()
        pixmap = QPixmap(str(path))
        columns, rows = self.columns.value(), self.rows.value()
        frame = self.frame.value()
        if pixmap.isNull() or frame >= columns * rows:
            return pixmap if frame == 0 else QPixmap()
        width, height = pixmap.width() // columns, pixmap.height() // rows
        if width <= 0 or height <= 0:
            return QPixmap()
        return pixmap.copy((frame % columns) * width, (frame // columns) * height, width, height)

    def result_args(self):
        command = self.command.currentText()
        all_values = {
            "picture_id": self.picture_id.text().strip(),
            "asset_id": self.asset_id.text().strip(),
            "x": self.x.value(),
            "y": self.y.value(),
            "scale": self.picture_scale.value(),
            "opacity": self.opacity.value(),
            "frame": self.frame.value(),
            "columns": self.columns.value(),
            "rows": self.rows.value(),
            "layer": self.layer.text().strip(),
            "click_event": self.click_event.text().strip(),
            "duration": self.duration.value(),
            "easing": self.easing.currentText(),
        }
        return {name: all_values[name] for name in self._fields[command]}
