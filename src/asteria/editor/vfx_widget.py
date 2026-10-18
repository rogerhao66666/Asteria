"""VFX tool (EDT-08): battle VFX list, import, in-battle placement, playback preview and where each
VFX is used."""

from __future__ import annotations

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QPushButton,
    QSlider,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from asteria.runtime.battle_visuals import VFX_ALIGNS, VFX_ANCHORS, VFX_BLENDS, vfx_rect

from .vfx_authoring import PREVIEW_BODY_HEIGHT, VFXAuthoringController, VFXAuthoringError


class VFXStage(QWidget):
    """A member stand-in on the battle ground with the VFX frame drawn where the battle draws
    it."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(220, 260)
        self.pixmap = None
        self.source = None
        self.rect = None
        self.placement = None

    def show_frame(self, pixmap, source, rect, placement):
        self.pixmap, self.source, self.rect, self.placement = pixmap, source, rect, placement
        self.update()

    def feet(self):
        return self.width() / 2, self.height() * 0.78

    def paintEvent(self, _event):  # noqa: N802 - Qt API
        p = QPainter(self)
        p.fillRect(self.rect_all(), QColor("#1d2330"))
        fx, fy = self.feet()
        p.setPen(QPen(QColor("#3c4658"), 1))
        p.drawLine(0, int(fy), self.width(), int(fy))
        body = QRectF(fx - 22, fy - PREVIEW_BODY_HEIGHT, 44, PREVIEW_BODY_HEIGHT)
        p.setPen(QPen(QColor("#6b7a90"), 1, Qt.DashLine))
        p.drawRoundedRect(body, 10, 10)
        p.setPen(QPen(QColor("#8fa3bf"), 1))
        for anchor, lift in (("feet", 0.0), ("center", 0.5), ("head", 1.0)):
            y = fy - lift * PREVIEW_BODY_HEIGHT
            p.drawLine(int(fx - 30), int(y), int(fx - 24), int(y))
            p.drawText(int(fx - 70), int(y + 4), anchor)
        if self.pixmap is not None and self.rect is not None and not self.pixmap.isNull():
            cx, cy, w, h = self.rect
            target = QRectF(fx + cx - w / 2, fy + cy - h / 2, w, h)
            p.setOpacity(self.placement["opacity"])
            if self.placement["blend"] == "add":
                p.setCompositionMode(QPainter.CompositionMode_Plus)
            p.drawPixmap(target, self.pixmap, QRectF(*self.source))
            p.setOpacity(1.0)
            p.setCompositionMode(QPainter.CompositionMode_SourceOver)
            p.setPen(QPen(QColor("#f0a050"), 1))
            p.drawEllipse(target.center(), 3, 3)
        p.end()

    def rect_all(self):
        return QRectF(0, 0, self.width(), self.height())


class VFXEditorWidget(QWidget):
    changed = Signal()
    openTimeline = Signal(str)  # sequence id
    openAnimation = Signal(str)  # sheet asset id

    def __init__(self, document, parent=None, *, resource_root=None):
        super().__init__(parent)
        self.api = VFXAuthoringController(document, resource_root=resource_root)
        self.last_error = None
        self._pixmaps = {}

        self.vfx_list = QListWidget()
        self.vfx_list.currentTextChanged.connect(lambda _t: self._load())
        import_button, use_button, unuse_button = (
            QPushButton("Import…"),
            QPushButton("Add Existing Sheet…"),
            QPushButton("Remove from Effects"),
        )
        import_button.setToolTip("Copy a sprite sheet image into the project and add it as a VFX")
        use_button.setToolTip("Mark an existing sprite sheet as a battle VFX")
        import_button.clicked.connect(self._import_clicked)
        use_button.clicked.connect(self._use_clicked)
        unuse_button.clicked.connect(lambda: self.mark_selected(False))
        left = QVBoxLayout()
        left.addWidget(QLabel("Battle Effects"))
        left.addWidget(self.vfx_list, 1)
        row = QHBoxLayout()
        for b in (import_button, use_button, unuse_button):
            row.addWidget(b)
        left.addLayout(row)
        left_box = QWidget()
        left_box.setLayout(left)

        self.stage = VFXStage()
        self.play_button = QPushButton("Play")
        self.play_button.clicked.connect(self.toggle_play)
        self.scrub = QSlider(Qt.Horizontal)
        self.scrub.setRange(0, 1000)
        self.scrub.valueChanged.connect(lambda _v: self._render())
        self.time_label = QLabel("")
        transport = QHBoxLayout()
        transport.addWidget(self.play_button)
        transport.addWidget(self.scrub, 1)
        transport.addWidget(self.time_label)
        center = QVBoxLayout()
        center.addWidget(self.stage, 1)
        center.addLayout(transport)
        center_box = QWidget()
        center_box.setLayout(center)

        self.anchor = QComboBox()
        self.anchor.addItems(list(VFX_ANCHORS))
        self.offset_x, self.offset_y = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self.offset_x, self.offset_y):
            spin.setRange(-512, 512)
            spin.setDecimals(1)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.05, 8.0)
        self.scale.setSingleStep(0.05)
        self.opacity = QDoubleSpinBox()
        self.opacity.setRange(0.0, 1.0)
        self.opacity.setSingleStep(0.05)
        self.blend = QComboBox()
        self.blend.addItems(list(VFX_BLENDS))
        self.align = QComboBox()  # content: the drawn picture lands on the member
        self.align.addItems(list(VFX_ALIGNS))
        for widget in (self.anchor, self.blend, self.align):
            widget.currentTextChanged.connect(lambda _t: self._render())
        for widget in (self.offset_x, self.offset_y, self.scale, self.opacity):
            widget.valueChanged.connect(lambda _v: self._render())
        apply_button = QPushButton("Apply Placement")
        apply_button.clicked.connect(self.apply_placement)
        offset_row = QHBoxLayout()
        offset_row.addWidget(self.offset_x)
        offset_row.addWidget(self.offset_y)
        placement = QGroupBox("Battle Placement")
        form = QFormLayout(placement)
        form.addRow("Anchor on member", self.anchor)
        form.addRow("Offset x / y", offset_row)
        form.addRow("Scale", self.scale)
        form.addRow("Opacity", self.opacity)
        form.addRow("Blend", self.blend)
        form.addRow("Centre on (picture / frame)", self.align)
        form.addRow(apply_button)
        self.info = QLabel("")
        self.info.setWordWrap(True)
        edit_frames = QPushButton("Edit Frames && Timing…")
        edit_frames.clicked.connect(lambda: self.vfx_id and self.openAnimation.emit(self.vfx_id))
        self.usages = QListWidget()
        self.usages.itemActivated.connect(
            lambda item: self.openTimeline.emit(item.text().split(".", 1)[0])
        )
        self.problems = QListWidget()
        self.status = QLabel("")
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        right.addWidget(placement)
        right.addWidget(self.info)
        right.addWidget(edit_frames)
        right.addWidget(QLabel("Cued by action timelines (double-click to open)"))
        right.addWidget(self.usages, 1)
        right.addWidget(QLabel("Checks"))
        right.addWidget(self.problems, 1)
        right.addWidget(self.status)
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

    # -- state ----------------------------------------------------------------------
    @property
    def vfx_id(self):
        item = self.vfx_list.currentItem()
        return None if item is None else item.text()

    def refresh(self, select=None):
        if self.api.document.project is None:
            self.vfx_list.clear()
            return
        current = select or self.vfx_id
        ids = self.api.vfx_ids()
        self.vfx_list.blockSignals(True)
        self.vfx_list.clear()
        self.vfx_list.addItems(list(ids))
        self.vfx_list.blockSignals(False)
        if ids:
            self.vfx_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load()

    def select_vfx(self, asset_id):
        self.refresh(select=asset_id)
        return self.vfx_id == asset_id

    def _load(self):
        asset_id = self.vfx_id
        self.usages.clear()
        self.problems.clear()
        if asset_id is None:
            self.stage.show_frame(None, None, None, None)
            return
        placement = self.api.placement(asset_id)
        widgets = (
            self.anchor,
            self.blend,
            self.align,
            self.offset_x,
            self.offset_y,
            self.scale,
            self.opacity,
        )
        for w in widgets:
            w.blockSignals(True)
        self.anchor.setCurrentText(placement["anchor"])
        self.blend.setCurrentText(placement["blend"])
        self.align.setCurrentText(placement["align"])
        self.offset_x.setValue(placement["offset"][0])
        self.offset_y.setValue(placement["offset"][1])
        self.scale.setValue(placement["scale"])
        self.opacity.setValue(placement["opacity"])
        for w in widgets:
            w.blockSignals(False)
        data = self.api.animation.data(asset_id)
        frames = len(data["clips"].get("play", {}).get("frames", []))
        self.info.setText(
            f"{self.api.asset(asset_id).source.uri}\n"
            f"{data['frame_size'][0]}×{data['frame_size'][1]} px frames, {frames} in 'play', "
            f"{self.api.duration(asset_id):.2f}s"
        )
        self.usages.addItems([f"{s}.{b}" for s, b in self.api.usages(asset_id)] or [])
        problems = self.api.problems(asset_id)
        self.problems.addItems(problems or ["No problems"])
        self._render()

    def form_placement(self):
        return {
            "anchor": self.anchor.currentText(),
            "offset": [self.offset_x.value(), self.offset_y.value()],
            "scale": self.scale.value(),
            "opacity": self.opacity.value(),
            "blend": self.blend.currentText(),
            "align": self.align.currentText(),
        }

    def _pixmap(self, asset_id):
        if asset_id not in self._pixmaps:
            path = self.api.animation.image_path(asset_id)
            self._pixmaps[asset_id] = QPixmap(str(path)) if path and path.is_file() else QPixmap()
        return self._pixmaps[asset_id]

    def _render(self):
        asset_id = self.vfx_id
        if asset_id is None:
            return None
        try:
            preview = self.api.preview(
                asset_id, self.scrub.value() / 1000 * self.api.duration(asset_id)
            )
        except VFXAuthoringError as exc:
            self.status.setText(str(exc))
            self.stage.show_frame(None, None, None, None)
            return None
        placement = (
            self.form_placement()
        )  # unsaved form values preview with the battle's placement rule
        fw, fh = preview.source[2], preview.source[3]
        rect = vfx_rect(placement, 0.0, 0.0, PREVIEW_BODY_HEIGHT, fw, fh)
        self.stage.show_frame(self._pixmap(asset_id), preview.source, rect, placement)
        self.time_label.setText(
            f"{self.scrub.value() / 1000 * preview.duration:.2f}s  frame {preview.frame_index}"
        )
        return rect

    # -- playback ---------------------------------------------------------------------
    def toggle_play(self):
        self.playing = not self.playing
        self.play_button.setText("Stop" if self.playing else "Play")
        if self.playing:
            self.timer.start()
        else:
            self.timer.stop()

    def tick(self, dt):
        duration = self.api.duration(self.vfx_id) if self.vfx_id else 0.0
        if duration <= 0:
            return
        value = self.scrub.value() + int(dt / duration * 1000)
        self.scrub.setValue(value % 1000)  # loops in the editor; the battle plays it once

    # -- edits ------------------------------------------------------------------------
    def _try(self, action, message, select=None):
        try:
            result = action()
        except (VFXAuthoringError, ValueError, OSError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self.refresh(select=select)
        self.changed.emit()
        return result if result is not None else True

    def apply_placement(self):
        asset_id = self.vfx_id
        values = self.form_placement()
        return asset_id and self._try(
            lambda: self.api.set_placement(asset_id, **values), "Placement saved"
        )

    def mark_selected(self, enabled):
        asset_id = self.vfx_id
        return asset_id and self._try(lambda: self.api.mark_as_vfx(asset_id, enabled), "Updated")

    def use_sheet(self, asset_id):
        return self._try(
            lambda: self.api.mark_as_vfx(asset_id, True),
            f"{asset_id} is now a VFX",
            select=asset_id,
        )

    def import_vfx(self, asset_id, path, frame_width, frame_height, frame_duration=0.06):
        return self._try(
            lambda: self.api.import_sheet(
                asset_id, path, frame_width, frame_height, frame_duration=frame_duration
            ),
            f"Imported {asset_id}",
            select=asset_id,
        )

    def _import_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import VFX Sprite Sheet", "", "Images (*.png *.webp)"
        )
        if not path:
            return
        asset_id, ok = QInputDialog.getText(self, "Import VFX", "Asset id:", text="battle.fx.new")
        if not ok or not asset_id.strip():
            return
        size, ok = QInputDialog.getText(
            self, "Import VFX", "Frame size (width x height):", text="64x64"
        )
        if not ok:
            return
        try:
            width, height = (int(v) for v in size.lower().replace(" ", "").split("x"))
        except ValueError:
            self.status.setText("Frame size must look like 64x64")
            return
        self.import_vfx(asset_id.strip(), path, width, height)

    def _use_clicked(self):
        options = list(self.api.other_sheets())
        if not options:
            self.status.setText("No other sprite sheets in the project")
            return
        asset_id, ok = QInputDialog.getItem(
            self, "Use Sheet as VFX", "Sprite sheet:", options, 0, False
        )
        if ok:
            self.use_sheet(asset_id)
