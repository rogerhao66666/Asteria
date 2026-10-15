"""A small dock that plays an imported 2D skeleton so a rig can be checked before use."""

try:
    from PySide6.QtCore import Qt, QTimer
    from PySide6.QtGui import QColor, QPainter, QPen
    from PySide6.QtWidgets import (
        QComboBox,
        QFileDialog,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QSlider,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Qt = None

from .skeleton_view import bone_segments, bounds, load_rig


class _Canvas(QWidget):
    def __init__(self, owner):
        super().__init__()
        self.owner = owner
        self.setMinimumHeight(180)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(32, 34, 38))
        segments = self.owner.segments()
        if not segments:
            return
        left, top, right, bottom = bounds(segments)
        scale = min(self.width() / max(right - left, 1), self.height() / max(bottom - top, 1))
        ox = (self.width() - (right - left) * scale) / 2 - left * scale
        oy = (self.height() - (bottom - top) * scale) / 2 - top * scale
        painter.setPen(QPen(QColor(120, 200, 255), 2))
        for s in segments:
            painter.drawLine(
                int(s.x0 * scale + ox),
                int(s.y0 * scale + oy),
                int(s.x1 * scale + ox),
                int(s.y1 * scale + oy),
            )
        painter.setPen(QPen(QColor(255, 210, 90), 4))
        for s in segments:
            painter.drawPoint(int(s.x0 * scale + ox), int(s.y0 * scale + oy))


class SkeletonViewerWidget(QWidget):
    TICKS = 100  # slider steps across a clip

    def __init__(self, parent=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.skeleton = None
        self.time = 0.0
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.open_button = QPushButton("Open rig…")
        self.clip_combo = QComboBox()
        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        for widget in (self.open_button, self.clip_combo, self.play_button):
            top.addWidget(widget)
        layout.addLayout(top)
        self.canvas = _Canvas(self)
        layout.addWidget(self.canvas, 1)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, self.TICKS)
        layout.addWidget(self.slider)
        self.status = QLabel("No rig loaded")
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self.open_button.clicked.connect(self._choose)
        self.clip_combo.currentTextChanged.connect(lambda _: self._set_time(0.0))
        self.play_button.toggled.connect(
            lambda on: self._timer.start() if on else self._timer.stop()
        )
        self.slider.valueChanged.connect(self._scrub)

    def _choose(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open rig", "", "Skeleton JSON (*.json)")
        if path:
            self.open_rig(path)

    def open_rig(self, path):
        """Load a rig file; the problem is shown in the status line when it cannot be read."""
        try:
            skeleton, notes = load_rig(path)
        except (OSError, ValueError) as exc:
            self.status.setText(f"Could not load: {exc}")
            return False
        self.set_skeleton(skeleton)
        note = f" · skipped: {', '.join(notes)}" if notes else ""
        self.status.setText(f"{skeleton.skeleton_id}: {len(skeleton.bones)} bones{note}")
        return True

    def set_skeleton(self, skeleton):
        self.skeleton = skeleton
        self.clip_combo.blockSignals(True)
        self.clip_combo.clear()
        self.clip_combo.addItems(sorted(skeleton.clips))
        self.clip_combo.blockSignals(False)
        self._set_time(0.0)

    def clip(self):
        if self.skeleton is None:
            return None
        return self.skeleton.clips.get(self.clip_combo.currentText())

    def segments(self):
        if self.skeleton is None:
            return ()
        clip = self.clip()
        return bone_segments(self.skeleton, clip.name if clip else None, self.time)

    def _set_time(self, seconds):
        clip = self.clip()
        duration = clip.duration if clip else 0.0
        self.time = seconds % duration if duration else 0.0
        self.slider.blockSignals(True)
        self.slider.setValue(int(self.TICKS * self.time / duration) if duration else 0)
        self.slider.blockSignals(False)
        self.canvas.update()

    def _scrub(self, value):
        clip = self.clip()
        if clip:
            self._set_time(clip.duration * value / self.TICKS)

    def _advance(self):
        self._set_time(self.time + self._timer.interval() / 1000.0)
