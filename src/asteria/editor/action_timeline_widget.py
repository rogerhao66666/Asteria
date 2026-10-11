"""Action timeline editor (EDT-06): channel lanes, draggable beats, beat inspector, scrub preview."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import (
    QComboBox,
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .action_timeline_authoring import CHANNELS, ROLES, TARGETS, ActionTimelineController, ActionTimelineError

LANE_HEIGHT = 28
LEFT = 84
COLORS = {
    "animation": "#7cb3ff",
    "vfx": "#f0a050",
    "audio": "#8ad18a",
    "camera": "#d08ae0",
    "screen_fx": "#f0d060",
    "timing": "#e06060",
}


class TimelineView(QWidget):
    """Lanes per channel; beats are markers that can be selected and dragged in time."""

    beatSelected = Signal(str)
    beatMoved = Signal(str, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.sequence = None
        self.selected = None
        self.playhead = 0.0
        self._drag = None
        self.setMinimumHeight(LANE_HEIGHT * len(CHANNELS) + 24)

    def set_sequence(self, sequence, selected=None):
        self.sequence, self.selected = sequence, selected
        self.update()

    def _x(self, t):
        span = max(self.sequence.duration, 0.1) if self.sequence else 1.0
        return LEFT + (self.width() - LEFT - 12) * (t / span)

    def _t(self, x):
        span = max(self.sequence.duration, 0.1) if self.sequence else 1.0
        return max(0.0, min(span, (x - LEFT) / max(1.0, self.width() - LEFT - 12) * span))

    def beat_rect(self, beat):
        lane = CHANNELS.index(beat.channel) if beat.channel in CHANNELS else 0
        return QRectF(self._x(beat.at) - 5, 20 + lane * LANE_HEIGHT + 4, 10, LANE_HEIGHT - 8)

    def beat_at(self, x, y):
        if self.sequence is None:
            return None
        for beat in self.sequence.beats:
            if self.beat_rect(beat).adjusted(-3, -2, 3, 2).contains(x, y):
                return beat.beat_id
        return None

    def mousePressEvent(self, event):  # noqa: N802 - Qt API
        beat = self.beat_at(event.position().x(), event.position().y())
        if beat is not None:
            self.selected = beat
            self._drag = beat
            self.beatSelected.emit(beat)
            self.update()

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt API
        if self._drag is not None:
            beat, self._drag = self._drag, None
            self.beatMoved.emit(beat, round(self._t(event.position().x()), 3))

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#16191e"))
        if self.sequence is None:
            return
        painter.setPen(QColor("#8a93a3"))
        steps = max(1, int(self.sequence.duration / 0.1))
        for i in range(steps + 1):
            t = i * 0.1
            x = self._x(t)
            painter.drawLine(int(x), 14, int(x), 18)
            if i % 2 == 0:
                painter.drawText(int(x) - 10, 12, f"{t:.1f}")
        for lane, channel in enumerate(CHANNELS):
            y = 20 + lane * LANE_HEIGHT
            painter.fillRect(LEFT, y + 1, self.width() - LEFT - 12, LANE_HEIGHT - 2, QColor("#1e232b"))
            painter.setPen(QColor("#c8d0dc"))
            painter.drawText(6, y + LANE_HEIGHT // 2 + 5, channel)
        for beat in self.sequence.beats:
            rect = self.beat_rect(beat)
            painter.fillRect(rect, QColor(COLORS.get(beat.channel, "#cccccc")))
            if beat.beat_id == self.selected:
                painter.setPen(QPen(QColor("#ffffff"), 2))
                painter.drawRect(rect.adjusted(-2, -2, 2, 2))
        painter.setPen(QPen(QColor("#f05a5a"), 1))
        x = self._x(self.playhead)
        painter.drawLine(int(x), 14, int(x), self.height())


class ActionTimelineWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = ActionTimelineController(document)
        self.sequence_list = QListWidget()
        self.sequence_list.currentTextChanged.connect(lambda _: self._load())
        new_button, dup_button, del_button = QPushButton("New…"), QPushButton("Duplicate…"), QPushButton("Delete")
        new_button.clicked.connect(self._new_clicked)
        dup_button.clicked.connect(self._duplicate_clicked)
        del_button.clicked.connect(self.delete_sequence)
        left = QVBoxLayout()
        left.addWidget(QLabel("Ability timelines"))
        left.addWidget(self.sequence_list, 1)
        row = QHBoxLayout()
        for b in (new_button, dup_button, del_button):
            row.addWidget(b)
        left.addLayout(row)
        left_box = QWidget()
        left_box.setLayout(left)

        self.view = TimelineView()
        self.view.beatSelected.connect(self._select_beat)
        self.view.beatMoved.connect(self.move_beat)
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.05, 30.0)
        self.duration.setDecimals(3)
        apply_duration = QPushButton("Set Length")
        apply_duration.clicked.connect(self.apply_duration)
        center = QVBoxLayout()
        top = QHBoxLayout()
        top.addWidget(QLabel("Length (s)"))
        top.addWidget(self.duration)
        top.addWidget(apply_duration)
        top.addStretch(1)
        center.addLayout(top)
        center.addWidget(self.view, 1)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 1000)
        self.scrub.valueChanged.connect(self._scrubbed)
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        transport = QHBoxLayout()
        transport.addWidget(self.play_button)
        transport.addWidget(self.scrub, 1)
        center.addLayout(transport)
        self.released = QLabel("")
        self.released.setWordWrap(True)
        center.addWidget(self.released)
        center_box = QWidget()
        center_box.setLayout(center)

        self.beat_id = QLineEdit()
        self.beat_id.setReadOnly(True)
        self.at = QDoubleSpinBox()
        self.at.setRange(0.0, 30.0)
        self.at.setDecimals(3)
        self.at.setSingleStep(0.01)
        self.channel = QComboBox()
        self.channel.addItems(list(CHANNELS))
        self.channel.currentTextChanged.connect(self._channel_changed)
        self.cue = QComboBox()
        self.cue.setEditable(True)
        self.member = QComboBox()
        self.member.addItems(list(TARGETS))
        apply_beat, add_beat, remove_beat = (
            QPushButton("Apply Beat"),
            QPushButton("Add Beat…"),
            QPushButton("Remove Beat"),
        )
        apply_beat.clicked.connect(self.apply_beat)
        add_beat.clicked.connect(self._add_clicked)
        remove_beat.clicked.connect(self.remove_beat)
        inspector = QGroupBox("Beat")
        form = QFormLayout(inspector)
        form.addRow("ID", self.beat_id)
        form.addRow("Time (s)", self.at)
        form.addRow("Channel", self.channel)
        form.addRow("Cue", self.cue)
        form.addRow("Member", self.member)
        form.addRow(apply_beat)
        form.addRow(add_beat)
        form.addRow(remove_beat)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        right.addWidget(inspector)
        right.addWidget(self.status)
        right.addStretch(1)
        right_box = QWidget()
        right_box.setLayout(right)

        split = QSplitter()
        split.addWidget(left_box)
        split.addWidget(center_box)
        split.addWidget(right_box)
        split.setStretchFactor(1, 1)
        layout = QVBoxLayout(self)
        layout.addWidget(split)
        self.timer = QTimer(self)
        self.timer.setInterval(16)
        self.timer.timeout.connect(lambda: self.tick(0.016))
        self.playing = False
        self.refresh()

    @property
    def sequence_id(self):
        item = self.sequence_list.currentItem()
        return None if item is None else item.text()

    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        current = select or self.sequence_id
        self.sequence_list.blockSignals(True)
        self.sequence_list.clear()
        ids = self.api.sequences()
        self.sequence_list.addItems(list(ids))
        self.sequence_list.blockSignals(False)
        if ids:
            self.sequence_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load()

    def _load(self, beat=None):
        if not self.sequence_id:
            self.view.set_sequence(None)
            return
        sequence = self.api.get(self.sequence_id)
        self.duration.setValue(sequence.duration)
        beat = beat or self.view.selected
        if beat not in {b.beat_id for b in sequence.beats}:
            beat = sequence.beats[0].beat_id if sequence.beats else None
        self.view.set_sequence(sequence, beat)
        self._select_beat(beat)

    def _select_beat(self, beat_id):
        if not beat_id or not self.sequence_id:
            return
        beat = next((b for b in self.api.beats(self.sequence_id) if b.beat_id == beat_id), None)
        if beat is None:
            return
        self.view.selected = beat_id
        self.beat_id.setText(beat.beat_id)
        self.at.setValue(beat.at)
        self.channel.setCurrentText(beat.channel)
        self._channel_changed(beat.channel)
        self.cue.setCurrentText(beat.cue)
        self.member.setCurrentText(beat.member_id or "@source")
        self.view.update()

    def _channel_changed(self, channel):
        suggestions = {
            "animation": ROLES,
            "vfx": self.api.known_vfx(),
            "audio": ("hit", "heal", "confirm"),
            "camera": ("shake",),
            "screen_fx": ("flash",),
        }.get(channel, ())
        text = self.cue.currentText()
        self.cue.clear()
        self.cue.addItems(list(suggestions))
        self.cue.setCurrentText(text if text else (suggestions[0] if suggestions else ""))

    def _report(self, text, ok=True):
        self.status.setStyleSheet("" if ok else "color: #d9534f;")
        self.status.setText(text)

    def _try(self, action, message, beat=None, select=None):
        try:
            action()
        except ActionTimelineError as exc:
            self._report(str(exc), ok=False)
            return False
        self._report(message)
        self.changed.emit()
        self.refresh(select)
        if beat:
            self._load(beat)
        return True

    # -- edits ----------------------------------------------------------------------
    def apply_beat(self):
        sid, beat = self.sequence_id, self.beat_id.text()
        if not sid or not beat:
            return False
        return self._try(
            lambda: self.api.edit_beat(
                sid,
                beat,
                at=self.at.value(),
                channel=self.channel.currentText(),
                cue=self.cue.currentText(),
                member=self.member.currentText(),
            ),
            f"Applied {beat}",
            beat,
        )

    def add_beat(self, beat_id, at=0.0, channel="vfx", cue=None):
        sid = self.sequence_id
        cue = cue or (self.api.known_vfx()[0] if channel == "vfx" and self.api.known_vfx() else "attack")
        return self._try(lambda: self.api.add_beat(sid, beat_id, at, channel, cue), f"Added {beat_id}", beat_id)

    def remove_beat(self):
        sid, beat = self.sequence_id, self.beat_id.text()
        if not sid or not beat:
            return False
        return self._try(lambda: self.api.remove_beat(sid, beat), f"Removed {beat}")

    def move_beat(self, beat_id, at):
        sid = self.sequence_id
        return self._try(lambda: self.api.move_beat(sid, beat_id, at), f"Moved {beat_id} to {at:.3f}s", beat_id)

    def apply_duration(self):
        sid = self.sequence_id
        return self._try(lambda: self.api.set_duration(sid, self.duration.value()), "Length updated")

    def new_sequence(self, sequence_id):
        return self._try(lambda: self.api.create(sequence_id), f"Created {sequence_id}", select=sequence_id)

    def duplicate_sequence(self, new_id):
        sid = self.sequence_id
        return self._try(lambda: self.api.duplicate(sid, new_id), f"Duplicated as {new_id}", select=new_id)

    def delete_sequence(self):
        sid = self.sequence_id
        if not sid:
            return False
        return self._try(lambda: self.api.delete(sid), f"Deleted {sid}")

    def _new_clicked(self):
        name, ok = QInputDialog.getText(self, "New Timeline", "Ability id:")
        if ok and name.strip():
            self.new_sequence(name.strip())

    def _duplicate_clicked(self):
        name, ok = QInputDialog.getText(self, "Duplicate Timeline", "New ability id:")
        if ok and name.strip():
            self.duplicate_sequence(name.strip())

    def _add_clicked(self):
        name, ok = QInputDialog.getText(self, "Add Beat", "Beat id:")
        if ok and name.strip():
            self.add_beat(name.strip(), self.view.playhead, self.channel.currentText(), self.cue.currentText())

    # -- preview --------------------------------------------------------------------
    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.setText("Pause" if self.playing else "Play")
        if self.playing and self.view.playhead >= (self.view.sequence.duration if self.view.sequence else 0):
            self.view.playhead = 0.0
        self.timer.start() if self.playing else self.timer.stop()

    def _scrubbed(self, value):
        if self.view.sequence is None:
            return
        self.set_playhead(value / 1000.0 * self.view.sequence.duration)

    def tick(self, dt):
        if self.view.sequence is None:
            return
        self.set_playhead(self.view.playhead + dt)
        if self.view.playhead >= self.view.sequence.duration and self.playing:
            self.toggle_play()

    def set_playhead(self, t):
        if self.view.sequence is None:
            return
        self.view.playhead = max(0.0, min(float(t), self.view.sequence.duration))
        preview = self.api.preview(self.sequence_id, self.view.playhead)
        self.released.setText(
            f"t = {self.view.playhead:.2f}s  fired: "
            + ", ".join(f"{c}:{q}@{at:.2f}" for at, c, q, _ in preview["released"])
        )
        self.view.update()
