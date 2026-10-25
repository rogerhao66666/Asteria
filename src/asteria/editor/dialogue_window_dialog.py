"""Presentation ▸ Menu Screens ▸ Layout ▸ Picture message window…: the game's own message
window drawn at its picture's resolution (V2, ``presentation.dialogue_window``).

Every setting is a field here: the window picture, the text area inside it, the line height,
the bitmap font and its two colours, the typing speed (and one per Text speed option), the
"next" arrow strip (frame size, place, frame time) and the choice box (its 3 x 3 frame, inside
colour, edges and line height), the cancel key's answer and the sound of closing a line.
"From the game folder's manifest" turns an older game's ``playable_test_manifest.json`` window
into these settings (its font into a bitmap font) in one step.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from asteria.presentation.dialogue_window import DialogueWindowStyle


def _spin(low, high, value=0):
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    box.setMinimumWidth(64)
    return box


def _row(*pairs):
    row = QHBoxLayout()
    for name, box in pairs:
        row.addWidget(QLabel(name))
        row.addWidget(box, 1)
    return row


class OptionalNumber(QWidget):
    """A number or "the engine's" (None)."""

    def __init__(self, low, high, parent=None):
        super().__init__(parent)
        self.own = QCheckBox("Own")
        self.box = _spin(low, high)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.own)
        layout.addWidget(self.box, 1)
        self.own.toggled.connect(self.box.setEnabled)
        self.box.setEnabled(False)

    def value(self):
        return self.box.value() if self.own.isChecked() else None

    def setValue(self, value):  # noqa: N802 - Qt-style
        self.own.setChecked(value is not None)
        self.box.setValue(int(value or 0))
        self.box.setEnabled(value is not None)


class DialogueWindowDialog(QDialog):
    """The picture message window's settings; ``style()`` is the result (None: none)."""

    def __init__(self, document, style, fonts=(), parent=None, *, convert=None):
        super().__init__(parent)
        self.setWindowTitle("Picture Message Window")
        self.resize(560, 760)
        self.document = document
        self.convert = convert  # () -> DialogueWindowStyle | None (the manifest's)
        from .menu_layout_widget import AssetField, ColorField

        self.enabled = QCheckBox("Use the picture window (off: the ordinary window)")
        self.window = AssetField(document, "image")
        self.text_area = [_spin(-512, 2048) for _ in range(4)]
        self.line_height = _spin(1, 256, 16)
        self.font = QComboBox()
        self.font.addItem("none (a small system face)", "")
        for font_id in fonts:
            self.font.addItem(font_id, font_id)
        self.letter, self.shadow = ColorField(), ColorField()
        self.speed = QDoubleSpinBox()
        self.speed.setRange(0.0, 2000.0)
        self.speed.setSpecialValueText("all at once")
        self.speeds = QLineEdit()
        self.speeds.setPlaceholderText("e.g. 20, 40, 120 (slow, mid, fast)")
        self.arrow = AssetField(document, "image")
        self.arrow_size = [_spin(1, 512) for _ in range(2)]
        self.arrow_at = [_spin(-512, 2048) for _ in range(2)]
        self.arrow_ms = _spin(1, 5000, 160)
        self.choice_frame = AssetField(document, "image")
        self.choice_fill = ColorField()
        self.choice_right = OptionalNumber(-512, 2048)
        self.choice_bottom = OptionalNumber(-512, 2048)
        self.choice_line = _spin(1, 256, 16)
        self.cancel_last = QCheckBox("The cancel key picks a choice's last option")
        self.sound = AssetField(document, "sound")
        form = QFormLayout()
        form.addRow(self.enabled)
        form.addRow("Window picture", self.window)
        x, y, w, h = self.text_area
        form.addRow("Text area", _row(("x", x), ("y", y)))
        form.addRow("", _row(("w", w), ("h", h)))
        form.addRow("Line height", self.line_height)
        form.addRow("Bitmap font", self.font)
        form.addRow("Letter colour", self.letter)
        form.addRow("Shadow colour", self.shadow)
        form.addRow("Letters a second", self.speed)
        form.addRow("By the Text speed option", self.speeds)
        form.addRow("'Next' arrow (strip)", self.arrow)
        form.addRow("Arrow frame size", _row(("w", self.arrow_size[0]), ("h", self.arrow_size[1])))
        form.addRow("Arrow place", _row(("x", self.arrow_at[0]), ("y", self.arrow_at[1])))
        form.addRow("Arrow frame time (ms)", self.arrow_ms)
        form.addRow("Choice box frame (3 x 3)", self.choice_frame)
        form.addRow("Choice box inside", self.choice_fill)
        form.addRow("Choice box right edge", self.choice_right)
        form.addRow("Choice box bottom edge", self.choice_bottom)
        form.addRow("Choice line height", self.choice_line)
        form.addRow(self.cancel_last)
        form.addRow("Sound when a line closes", self.sound)
        body = QWidget()
        body.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        convert_button = QPushButton("From the game folder's manifest")
        convert_button.setToolTip(
            "Turn playable_test_manifest.json's dialogue window into these settings"
        )
        convert_button.clicked.connect(self._convert)
        convert_button.setEnabled(convert is not None)
        remove = QPushButton("Remove the picture window")
        remove.clicked.connect(self._remove)
        self.status = QLabel()
        self.status.setWordWrap(True)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        tools = QHBoxLayout()
        tools.addWidget(convert_button)
        tools.addWidget(remove)
        tools.addStretch(1)
        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.status)
        layout.addWidget(buttons)
        self._removed = False
        self.load(style or DialogueWindowStyle())

    def load(self, style):
        self.enabled.setChecked(style.enabled)
        self.window.setText(style.window)
        for box, value in zip(self.text_area, style.text_area, strict=True):
            box.setValue(value)
        self.line_height.setValue(style.line_height)
        if style.font and self.font.findData(style.font) < 0:
            self.font.addItem(style.font, style.font)
        self.font.setCurrentIndex(max(0, self.font.findData(style.font)))
        self.letter.setColor(style.letter_color)
        self.shadow.setColor(style.shadow_color)
        self.speed.setValue(style.speed)
        self.speeds.setText(", ".join(f"{v:g}" for v in style.speeds))
        self.arrow.setText(style.arrow)
        for box, value in zip(self.arrow_size, style.arrow_size, strict=True):
            box.setValue(value)
        for box, value in zip(self.arrow_at, style.arrow_at, strict=True):
            box.setValue(value)
        self.arrow_ms.setValue(style.arrow_frame_ms)
        self.choice_frame.setText(style.choice_frame)
        self.choice_fill.setColor(style.choice_fill)
        self.choice_right.setValue(style.choice_right)
        self.choice_bottom.setValue(style.choice_bottom)
        self.choice_line.setValue(style.choice_line_height)
        self.cancel_last.setChecked(style.cancel_picks_last)
        self.sound.setText(style.confirm_sound)

    def style(self):
        """The window as the fields say (None when removed or it has no picture)."""
        if self._removed or not self.window.text():
            return None
        speeds = []
        for part in self.speeds.text().replace(";", ",").split(","):
            try:
                speeds.append(float(part))
            except ValueError:
                continue
        return DialogueWindowStyle(
            window=self.window.text(),
            enabled=self.enabled.isChecked(),
            text_area=tuple(b.value() for b in self.text_area),
            line_height=self.line_height.value(),
            font=self.font.currentData() or "",
            letter_color=self.letter.color() or (98, 98, 98),
            shadow_color=self.shadow.color() or (213, 213, 205),
            speed=self.speed.value(),
            speeds=tuple(speeds),
            arrow=self.arrow.text(),
            arrow_size=tuple(b.value() for b in self.arrow_size),
            arrow_at=tuple(b.value() for b in self.arrow_at),
            arrow_frame_ms=self.arrow_ms.value(),
            choice_frame=self.choice_frame.text(),
            choice_fill=self.choice_fill.color(),
            choice_right=self.choice_right.value(),
            choice_bottom=self.choice_bottom.value(),
            choice_line_height=self.choice_line.value(),
            cancel_picks_last=self.cancel_last.isChecked(),
            confirm_sound=self.sound.text(),
        )

    def _convert(self):
        style = self.convert() if self.convert is not None else None
        if style is None:
            self.status.setText("The game folder's manifest has no dialogue window.")
            return
        if style.font and self.font.findData(style.font) < 0:
            self.font.addItem(style.font, style.font)
        self._removed = False
        self.load(style)
        self.status.setText("Read from the manifest (its font is now a bitmap font).")

    def _remove(self):
        self._removed = True
        self.window.setText("")
        self.status.setText("OK removes the picture window: the ordinary window is drawn.")


__all__ = ["DialogueWindowDialog"]
