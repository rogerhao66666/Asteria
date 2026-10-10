"""Animation editor (EDT-05, ANI-04, AST-02): sheet grid, clips, events, pivot and live preview.

Layout (progressive disclosure): sheets + clips on the left, the frame grid
in the centre (click a cell to append it to the clip), clip / event / pivot
properties on the right, and a preview strip at the bottom that plays the
clip through the runtime animation path.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .animation_authoring import AnimationAuthoringController, AnimationAuthoringError


class FrameGridView(QWidget):
    """Shows a sprite sheet with its frame grid; emits the clicked frame index."""

    frameClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pixmap = None
        self.frame_size = (16, 16)
        self.highlight = ()
        self.scale = 1.0
        self.setMinimumSize(240, 160)

    def set_sheet(self, pixmap, frame_size, highlight=()):
        self.pixmap, self.frame_size, self.highlight = pixmap, tuple(frame_size), tuple(highlight)
        self.update()

    def _layout(self):
        if self.pixmap is None or self.pixmap.isNull():
            return 1.0
        return max(0.25, min(self.width() / self.pixmap.width(), self.height() / self.pixmap.height(), 4.0))

    def cell_at(self, x, y):
        if self.pixmap is None:
            return None
        scale = self._layout()
        fw, fh = self.frame_size
        columns = max(1, self.pixmap.width() // fw)
        rows = max(1, self.pixmap.height() // fh)
        column, row = int(x / (fw * scale)), int(y / (fh * scale))
        if 0 <= column < columns and 0 <= row < rows:
            return row * columns + column
        return None

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        index = self.cell_at(event.position().x(), event.position().y())
        if index is not None:
            self.frameClicked.emit(index)

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#16191e"))
        if self.pixmap is None or self.pixmap.isNull():
            painter.setPen(QColor("#8a93a3"))
            painter.drawText(self.rect(), Qt.AlignCenter, "No sprite sheet")
            return
        scale = self._layout()
        painter.drawPixmap(
            QRect(0, 0, int(self.pixmap.width() * scale), int(self.pixmap.height() * scale)), self.pixmap
        )
        fw, fh = self.frame_size
        columns = max(1, self.pixmap.width() // fw)
        rows = max(1, self.pixmap.height() // fh)
        painter.setPen(QPen(QColor(124, 145, 190, 160), 1))
        for c in range(columns + 1):
            painter.drawLine(int(c * fw * scale), 0, int(c * fw * scale), int(rows * fh * scale))
        for r in range(rows + 1):
            painter.drawLine(0, int(r * fh * scale), int(columns * fw * scale), int(r * fh * scale))
        painter.setPen(QPen(QColor(240, 201, 93), 2))
        for order, index in enumerate(self.highlight):
            rect = QRect(
                int((index % columns) * fw * scale),
                int((index // columns) * fh * scale),
                int(fw * scale),
                int(fh * scale),
            )
            painter.drawRect(rect.adjusted(1, 1, -1, -1))
            painter.drawText(rect.adjusted(4, 2, 0, 0), Qt.AlignLeft | Qt.AlignTop, str(order + 1))


class AnimationEditorWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None, *, resource_root=None):
        super().__init__(parent)
        self.api = AnimationAuthoringController(document, resource_root=resource_root)
        self._pixmaps = {}
        self.time = 0.0
        self.playing = False

        self.sheet_list = QListWidget()
        self.clip_list = QListWidget()
        self.sheet_list.currentTextChanged.connect(self._sheet_changed)
        self.clip_list.currentTextChanged.connect(self._clip_changed)
        add_clip, remove_clip, rename_clip = QPushButton("New Clip…"), QPushButton("Delete"), QPushButton("Rename…")
        add_clip.clicked.connect(self._new_clip_clicked)
        remove_clip.clicked.connect(self.remove_clip)
        rename_clip.clicked.connect(self._rename_clicked)
        left = QVBoxLayout()
        left.addWidget(QLabel("Sprite sheets"))
        left.addWidget(self.sheet_list, 1)
        left.addWidget(QLabel("Clips"))
        left.addWidget(self.clip_list, 1)
        buttons = QHBoxLayout()
        for b in (add_clip, rename_clip, remove_clip):
            buttons.addWidget(b)
        left.addLayout(buttons)
        left_box = QWidget()
        left_box.setLayout(left)

        self.grid = FrameGridView()
        self.grid.frameClicked.connect(self.append_frame)

        self.frames = QLineEdit()
        self.frames.setPlaceholderText("frame indices, e.g. 0, 1, 2, 1")
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.01, 10.0)
        self.duration.setDecimals(3)
        self.duration.setSingleStep(0.01)
        self.loop = QCheckBox("Loop")
        self.events = QLineEdit()
        self.events.setPlaceholderText("keyframe:event, e.g. 2:hit")
        apply_clip = QPushButton("Apply Clip")
        apply_clip.clicked.connect(self.apply_clip)
        clip_box = QGroupBox("Clip")
        clip_form = QFormLayout(clip_box)
        clip_form.addRow("Frames", self.frames)
        clip_form.addRow("Frame time (s)", self.duration)
        clip_form.addRow("", self.loop)
        clip_form.addRow("Events", self.events)
        clip_form.addRow(apply_clip)

        self.frame_w, self.frame_h = QSpinBox(), QSpinBox()
        for spin in (self.frame_w, self.frame_h):
            spin.setRange(1, 4096)
        self.pivot_x, self.pivot_y = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self.pivot_x, self.pivot_y):
            spin.setRange(0.0, 1.0)
            spin.setSingleStep(0.05)
            spin.setDecimals(3)
        apply_sheet = QPushButton("Apply Grid / Pivot")
        apply_sheet.clicked.connect(self.apply_sheet)
        sheet_box = QGroupBox("Sheet")
        sheet_form = QFormLayout(sheet_box)
        size_row = QHBoxLayout()
        size_row.addWidget(self.frame_w)
        size_row.addWidget(self.frame_h)
        pivot_row = QHBoxLayout()
        pivot_row.addWidget(self.pivot_x)
        pivot_row.addWidget(self.pivot_y)
        sheet_form.addRow("Frame size", size_row)
        sheet_form.addRow("Pivot (x, y)", pivot_row)
        sheet_form.addRow(apply_sheet)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        right.addWidget(clip_box)
        right.addWidget(sheet_box)
        right.addWidget(self.status)
        right.addStretch(1)
        right_box = QWidget()
        right_box.setLayout(right)

        self.preview = QLabel()
        self.preview.setFixedSize(160, 160)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: #121419; border: 1px solid #343a44;")
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 1000)
        self.scrub.valueChanged.connect(self._scrubbed)
        self.preview_info = QLabel("")
        preview_row = QHBoxLayout()
        preview_row.addWidget(self.preview)
        controls = QVBoxLayout()
        controls.addWidget(self.play_button)
        controls.addWidget(self.scrub)
        controls.addWidget(self.preview_info)
        controls.addStretch(1)
        preview_row.addLayout(controls, 1)

        split = QSplitter()
        split.addWidget(left_box)
        split.addWidget(self.grid)
        split.addWidget(right_box)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split, 1)
        layout.addLayout(preview_row)

        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(lambda: self.tick(0.016))
        self.refresh()

    # -- state --------------------------------------------------------------------
    @property
    def sheet(self):
        item = self.sheet_list.currentItem()
        return None if item is None else item.text()

    @property
    def clip(self):
        item = self.clip_list.currentItem()
        return None if item is None else item.text()

    def _pixmap(self, asset_id):
        path = self.api.image_path(asset_id)
        if path not in self._pixmaps:
            self._pixmaps[path] = QPixmap(str(path))
        return self._pixmaps[path]

    def refresh(self, sheet=None, clip=None):
        sheet = sheet or self.sheet
        clip = clip or self.clip
        if self.api.document.project is None:
            return
        self.sheet_list.blockSignals(True)
        self.sheet_list.clear()
        sheets = self.api.sheets()
        self.sheet_list.addItems(list(sheets))
        self.sheet_list.blockSignals(False)
        if sheets:
            self.sheet_list.setCurrentRow(sheets.index(sheet) if sheet in sheets else 0)
            self._sheet_changed(self.sheet, clip)

    def _sheet_changed(self, asset_id, clip=None):
        if not asset_id:
            return
        data = self.api.data(asset_id)
        self.clip_list.blockSignals(True)
        self.clip_list.clear()
        names = sorted(data["clips"])
        self.clip_list.addItems(names)
        self.clip_list.blockSignals(False)
        self.frame_w.setValue(data["frame_size"][0])
        self.frame_h.setValue(data["frame_size"][1])
        self.pivot_x.setValue(data["pivot"][0])
        self.pivot_y.setValue(data["pivot"][1])
        if names:
            self.clip_list.setCurrentRow(names.index(clip) if clip in names else 0)
        self._clip_changed(self.clip)

    def _clip_changed(self, name):
        if not self.sheet:
            return
        clip = self.api.data(self.sheet)["clips"].get(name or "", {})
        self.frames.setText(", ".join(str(f) for f in clip.get("frames", [])))
        self.duration.setValue(float(clip.get("frame_duration", 0.12)))
        self.loop.setChecked(bool(clip.get("loop", True)))
        self.events.setText(", ".join(f"{k}:{n}" for k, names in dict(clip.get("events", {})).items() for n in names))
        self.time = 0.0
        self._render()

    def _report(self, text, ok=True):
        self.status.setStyleSheet("" if ok else "color: #d9534f;")
        self.status.setText(text)

    def _try(self, action, message):
        try:
            action()
        except AnimationAuthoringError as exc:
            self._report(str(exc), ok=False)
            return False
        self._report(message)
        self.changed.emit()
        return True

    # -- edits ----------------------------------------------------------------------
    def _frames_from_text(self):
        return [int(x) for x in self.frames.text().replace(" ", "").split(",") if x != ""]

    def append_frame(self, index):
        frames = self._frames_from_text() + [int(index)]
        self.frames.setText(", ".join(str(f) for f in frames))
        self._render(highlight_only=True)

    def apply_clip(self):
        sheet, clip = self.sheet, self.clip
        if not sheet or not clip:
            return False
        try:
            frames = self._frames_from_text()
            events = {}
            for chunk in self.events.text().split(","):
                if ":" in chunk:
                    position, name = chunk.split(":", 1)
                    events.setdefault(int(position), []).append(name.strip())
        except ValueError:
            self._report("frames and event positions must be numbers", ok=False)
            return False

        def apply():
            self.api.set_clip(
                sheet, clip, frames=frames, frame_duration=self.duration.value(), loop=self.loop.isChecked()
            )
            current = {int(k) for k in self.api.data(sheet)["clips"][clip].get("events", {})}
            for position in current | set(events):
                self.api.set_events(sheet, clip, position, events.get(position, []))

        ok = self._try(apply, f"Applied {clip}")
        self.refresh(sheet, clip)
        return ok

    def apply_sheet(self):
        sheet = self.sheet
        if not sheet:
            return False

        def apply():
            data = self.api.data(sheet)
            if tuple(data["frame_size"]) != (self.frame_w.value(), self.frame_h.value()):
                self.api.set_frame_size(sheet, self.frame_w.value(), self.frame_h.value())
            if tuple(data["pivot"]) != (self.pivot_x.value(), self.pivot_y.value()):
                self.api.set_pivot(sheet, self.pivot_x.value(), self.pivot_y.value())

        ok = self._try(apply, f"Applied grid / pivot for {sheet}")
        self.refresh(sheet, self.clip)
        return ok

    def new_clip(self, name):
        sheet = self.sheet
        ok = self._try(lambda: self.api.add_clip(sheet, name, [0]), f"Created {name}")
        self.refresh(sheet, name)
        return ok

    def remove_clip(self):
        sheet, clip = self.sheet, self.clip
        if not sheet or not clip:
            return False
        ok = self._try(lambda: self.api.remove_clip(sheet, clip), f"Deleted {clip}")
        self.refresh(sheet)
        return ok

    def rename_clip(self, new_name):
        sheet, clip = self.sheet, self.clip
        ok = self._try(lambda: self.api.rename_clip(sheet, clip, new_name), f"Renamed {clip}")
        self.refresh(sheet, new_name)
        return ok

    def _new_clip_clicked(self):
        name, ok = QInputDialog.getText(self, "New Clip", "Clip name:")
        if ok and name.strip():
            self.new_clip(name.strip())

    def _rename_clicked(self):
        name, ok = QInputDialog.getText(self, "Rename Clip", "New name:", text=self.clip or "")
        if ok and name.strip():
            self.rename_clip(name.strip())

    # -- preview --------------------------------------------------------------------
    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.setText("Pause" if self.playing else "Play")
        self.timer.start() if self.playing else self.timer.stop()

    def _scrubbed(self, value):
        if self.playing or not self.sheet or not self.clip:
            return
        clip = self.api.data(self.sheet)["clips"].get(self.clip)
        if clip:
            self.time = value / 1000.0 * len(clip["frames"]) * float(clip["frame_duration"])
            self._render()

    def tick(self, dt):
        self.time += float(dt)
        self._render()

    def current_frame(self):
        if not self.sheet or not self.clip:
            return None
        return self.api.preview_frame(self.sheet, self.clip, self.time)

    def _render(self, highlight_only=False):
        sheet = self.sheet
        if not sheet:
            return
        pixmap = self._pixmap(sheet)
        data = self.api.data(sheet)
        try:
            highlight = self._frames_from_text()
        except ValueError:
            highlight = []
        self.grid.set_sheet(pixmap, data["frame_size"], highlight)
        if highlight_only or not self.clip or pixmap.isNull():
            return
        index = self.current_frame()
        x, y, w, h = self.api.frame_rect(sheet, index)
        frame = pixmap.copy(x, y, w, h).scaled(150, 150, Qt.KeepAspectRatio, Qt.FastTransformation)
        canvas = QPixmap(160, 160)
        canvas.fill(QColor("#121419"))
        painter = QPainter(canvas)
        ox, oy = (160 - frame.width()) // 2, (160 - frame.height()) // 2
        painter.drawPixmap(ox, oy, frame)
        px = ox + data["pivot"][0] * frame.width()
        py = oy + data["pivot"][1] * frame.height()
        painter.setPen(QPen(QColor(240, 90, 90), 1))
        painter.drawLine(int(px - 6), int(py), int(px + 6), int(py))
        painter.drawLine(int(px), int(py - 6), int(px), int(py + 6))
        painter.end()
        self.preview.setPixmap(canvas)
        self.preview_info.setText(f"t = {self.time:.2f}s   frame {index}")
