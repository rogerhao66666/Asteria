"""Character Composition tab (CMP-01, CMP-02, CMP-04): sockets, attachments and layers with a frame preview.

The preview places parts with the same ``CompositionPart`` data and rules the
battle screen uses (attachments from the body pivot, layers from the frame's
top-left), so what is shown here is what the game draws.
"""

from __future__ import annotations

from math import cos, radians, sin

from PySide6.QtCore import QRectF, Signal
from PySide6.QtGui import QBrush, QColor, QPen, QPixmap, QTransform
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGraphicsScene,
    QGraphicsView,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QPushButton,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from asteria.presentation.attachment_runtime import AttachmentRuntime
from asteria.presentation.attachments import Transform2D

from .animation_authoring import AnimationAuthoringError
from .character_composition_authoring import CharacterCompositionAuthoring, CompositionAuthoringError

PREVIEW_SCALE = 3.0


def _spin(low, high, value=0.0, step=1.0):
    box = QDoubleSpinBox()
    box.setRange(low, high)
    box.setSingleStep(step)
    box.setValue(value)
    return box


class CharacterCompositionWidget(QWidget):
    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.api = CharacterCompositionAuthoring(document)
        self.last_error = None
        self._pixmaps = {}

        self.sheet_list = QListWidget()
        self.sheet_list.currentTextChanged.connect(lambda _t: self._load())
        self.frame = QSpinBox()
        self.frame.setRange(0, 999)
        self.frame.valueChanged.connect(lambda _v: self._draw_preview())
        self.clip = QComboBox()
        self.clip.currentTextChanged.connect(lambda _t: self._draw_preview())
        self.preview = QGraphicsView(QGraphicsScene(self))
        self.preview.setMinimumSize(220, 220)

        # sockets
        self.sockets = QListWidget()
        self.sockets.currentTextChanged.connect(self._socket_selected)
        self.socket_id = QLineEdit()
        self.socket_parent = QComboBox()
        self.socket_x, self.socket_y = _spin(-512, 512), _spin(-512, 512)
        self.socket_rotation = _spin(-360, 360, step=5)
        add_socket, key_socket, remove_socket = (
            QPushButton("Add Socket"),
            QPushButton("Key at Frame"),
            QPushButton("Remove"),
        )
        add_socket.clicked.connect(self.add_socket_from_form)
        key_socket.clicked.connect(self.key_socket_from_form)
        remove_socket.clicked.connect(
            lambda: self._try(lambda: self.api.remove_socket(self.sheet, self._current(self.sockets)), "Socket removed")
        )
        sockets_box = QGroupBox("Sockets (body pixels from the pivot; key per frame)")
        form = QFormLayout()
        form.addRow("Id", self.socket_id)
        form.addRow("Parent", self.socket_parent)
        form.addRow("X / Y", self._pair(self.socket_x, self.socket_y))
        form.addRow("Rotation", self.socket_rotation)
        column = QVBoxLayout(sockets_box)
        column.addWidget(self.sockets, 1)
        column.addLayout(form)
        column.addLayout(self._row(add_socket, key_socket, remove_socket))

        # attachments
        self.attachments = QListWidget()
        self.attachment_id = QLineEdit()
        self.item_sheet = QComboBox()
        self.attach_socket = QComboBox()
        self.item_frame = QSpinBox()
        self.item_frame.setRange(0, 999)
        self.attach_scale = _spin(0.05, 8, 1.0, 0.05)
        self.attach_rotation = _spin(-360, 360, step=5)
        self.grip_x, self.grip_y = _spin(-512, 512), _spin(-512, 512)
        self.front = QCheckBox("In front of the body")
        self.front.setChecked(True)
        attach, detach = QPushButton("Attach"), QPushButton("Detach")
        attach.clicked.connect(self.attach_from_form)
        detach.clicked.connect(
            lambda: self._try(
                lambda: self.api.detach(self.sheet, self._current(self.attachments).split()[0]), "Detached"
            )
        )
        attachments_box = QGroupBox("Attachments (worn on a socket)")
        form = QFormLayout()
        form.addRow("Id", self.attachment_id)
        form.addRow("Sprite sheet", self.item_sheet)
        form.addRow("Frame", self.item_frame)
        form.addRow("Socket", self.attach_socket)
        form.addRow("Scale / Rotation", self._pair(self.attach_scale, self.attach_rotation))
        form.addRow("Grip X / Y", self._pair(self.grip_x, self.grip_y))
        form.addRow("", self.front)
        column = QVBoxLayout(attachments_box)
        column.addWidget(self.attachments, 1)
        column.addLayout(form)
        column.addLayout(self._row(attach, detach))

        # layers
        self.layers = QListWidget()
        self.layer_sheet = QComboBox()
        self.layer_component = QLineEdit("foreground")
        self.layer_z = _spin(-10, 10, 1.0)
        self.layer_clips = QLineEdit()
        self.layer_clips.setPlaceholderText("clips, comma separated (empty = all)")
        add_layer, remove_layer = QPushButton("Add Layer"), QPushButton("Remove Layer")
        add_layer.clicked.connect(self.add_layer_from_form)
        remove_layer.clicked.connect(
            lambda: self._try(lambda: self.api.remove_layer(self.sheet, self.layers.currentRow()), "Layer removed")
        )
        layers_box = QGroupBox("Layers (same frame of another sheet; z < 0 draws behind)")
        form = QFormLayout()
        form.addRow("Sprite sheet", self.layer_sheet)
        form.addRow("Component", self.layer_component)
        form.addRow("Z", self.layer_z)
        form.addRow("Clips", self.layer_clips)
        column = QVBoxLayout(layers_box)
        column.addWidget(self.layers, 1)
        column.addLayout(form)
        column.addLayout(self._row(add_layer, remove_layer))

        self.status = QLabel("Sockets, attachments and layers are saved on the body sheet and drawn in battle.")
        self.status.setWordWrap(True)
        left = QWidget()
        lv = QVBoxLayout(left)
        lv.addWidget(QLabel("Body Sheets"))
        lv.addWidget(self.sheet_list, 1)
        middle = QWidget()
        mv = QVBoxLayout(middle)
        mv.addLayout(self._row(QLabel("Frame"), self.frame, QLabel("Clip"), self.clip))
        mv.addWidget(self.preview, 1)
        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(sockets_box)
        rv.addWidget(attachments_box)
        rv.addWidget(layers_box)
        splitter = QSplitter()
        for pane in (left, middle, right):
            splitter.addWidget(pane)
        splitter.setSizes([180, 420, 380])
        layout = QVBoxLayout(self)
        layout.addWidget(splitter, 1)
        layout.addWidget(self.status)
        self.refresh()

    @staticmethod
    def _row(*widgets):
        row = QHBoxLayout()
        for w in widgets:
            row.addWidget(w)
        return row

    def _pair(self, a, b):
        holder = QWidget()
        row = self._row(a, b)
        row.setContentsMargins(0, 0, 0, 0)
        holder.setLayout(row)
        return holder

    @staticmethod
    def _current(listing):
        item = listing.currentItem()
        if item is None:
            raise CompositionAuthoringError("select an entry first")
        return item.text().split()[0]

    @property
    def sheet(self):
        item = self.sheet_list.currentItem()
        return None if item is None else item.text()

    # -- loading -------------------------------------------------------------------------------------
    def refresh(self, select=None):
        if self.api.document.project is None:
            return
        current = select or self.sheet
        ids = list(self.api.sheets())
        self.sheet_list.blockSignals(True)
        self.sheet_list.clear()
        self.sheet_list.addItems(ids)
        self.sheet_list.blockSignals(False)
        for combo in (self.item_sheet, self.layer_sheet):
            text = combo.currentText()
            combo.clear()
            combo.addItems(ids)
            if text in ids:
                combo.setCurrentText(text)
        self._pixmaps.clear()
        if ids:
            self.sheet_list.setCurrentRow(ids.index(current) if current in ids else 0)
        self._load()

    def _load(self):
        if self.sheet is None:
            return
        rig, attachments, layers = self.api.composition(self.sheet)
        self.sockets.clear()
        for socket in rig.sockets.values():
            keys = ", ".join(str(k.frame) for k in socket.keys)
            self.sockets.addItem(
                f"{socket.id}  ({socket.default.x:g}, {socket.default.y:g})"
                + (f"  parent {socket.parent}" if socket.parent else "")
                + (f"  keys {keys}" if keys else "")
            )
        for combo in (self.socket_parent, self.attach_socket):
            text = combo.currentText()
            combo.clear()
            if combo is self.socket_parent:
                combo.addItem("")
            combo.addItems(list(rig.sockets))
            if text:
                combo.setCurrentText(text)
        self.attachments.clear()
        for a in attachments:
            side = "front" if a.local.z_offset >= 0 else "back"
            self.attachments.addItem(f"{a.id}  {a.asset_id}[{a.metadata.get('frame', 0)}] on {a.socket_id} ({side})")
        self.layers.clear()
        for layer in layers.layers:
            clips = ", ".join(layer.clips) or "all clips"
            self.layers.addItem(f"{layer.component_id}  {layer.asset_id}  z {layer.z:g}  ({clips})")
        clip = self.clip.currentText()
        self.clip.blockSignals(True)
        self.clip.clear()
        self.clip.addItems(["", *self.api.animation.data(self.sheet)["clips"]])
        self.clip.setCurrentText(clip)
        self.clip.blockSignals(False)
        self._draw_preview()

    def _socket_selected(self, text):
        if not text or self.sheet is None:
            return
        rig, _, _ = self.api.composition(self.sheet)
        socket = rig.sockets.get(text.split()[0])
        if socket is not None:
            sample = socket.sample(self.frame.value())
            self.socket_id.setText(socket.id)
            self.socket_x.setValue(sample.x)
            self.socket_y.setValue(sample.y)
            self.socket_rotation.setValue(sample.rotation_deg)

    # -- preview -------------------------------------------------------------------------------------
    def _frame_pixmap(self, asset_id, index):
        if asset_id not in self._pixmaps:
            self._pixmaps[asset_id] = QPixmap(str(self.api.animation.image_path(asset_id)))
        sheet = self._pixmaps[asset_id]
        columns, rows = self.api.animation.grid(asset_id)
        if sheet.isNull() or columns * rows == 0:
            return None
        x, y, w, h = self.api.animation.frame_rect(asset_id, index % (columns * rows))
        return sheet.copy(x, y, w, h)

    def _draw_preview(self):
        scene = self.preview.scene()
        scene.clear()
        if self.sheet is None:
            return
        try:
            body = self._frame_pixmap(self.sheet, self.frame.value())
            parts = self.api.parts(self.sheet, self.frame.value(), self.clip.currentText())
            rig, _, _ = self.api.composition(self.sheet)
        except (AnimationAuthoringError, CompositionAuthoringError, ValueError, KeyError) as exc:
            scene.addSimpleText(str(exc))
            return
        if body is None:
            scene.addSimpleText("sheet image missing")
            return
        pivot_x, pivot_y = self.api.animation.data(self.sheet)["pivot"]
        px, py = body.width() * pivot_x, body.height() * pivot_y  # pivot in body pixels from the frame top-left
        s = PREVIEW_SCALE
        scene.addRect(QRectF(0, 0, body.width() * s, body.height() * s), QPen(QColor("#3a4152")))

        def place(part):
            pixmap = self._frame_pixmap(part.asset_id, part.frame_index)
            if pixmap is None:
                return
            ox, oy = (part.x, part.y) if part.kind == "layer" else (px + part.x, py + part.y)
            item = scene.addPixmap(pixmap)
            transform = QTransform()
            transform.scale(s, s)
            transform.translate(ox, oy)
            transform.rotate(part.rotation_deg)
            transform.scale(part.scale_x, part.scale_y)
            item.setTransform(transform)
            item.setOpacity(part.opacity)

        for part in parts:
            if part.behind:
                place(part)
        body_item = scene.addPixmap(body)
        body_item.setTransform(QTransform.fromScale(s, s))
        for part in parts:
            if not part.behind:
                place(part)
        marker = QPen(QColor("#f0c674"))
        runtime = AttachmentRuntime(rig, Transform2D())
        for socket_id in rig.sockets:
            t = runtime.socket_world_transform(socket_id, self.frame.value())
            cx, cy = (px + t.x) * s, (py + t.y) * s
            scene.addEllipse(QRectF(cx - 4, cy - 4, 8, 8), marker, QBrush(QColor(240, 198, 116, 120)))
            a = radians(t.rotation_deg)
            scene.addLine(cx, cy, cx + 14 * cos(a), cy + 14 * sin(a), marker)
            scene.addSimpleText(socket_id).setPos(cx + 6, cy - 16)
        scene.addEllipse(QRectF(px * s - 3, py * s - 3, 6, 6), QPen(QColor("#d9534f")))

    # -- edits ---------------------------------------------------------------------------------------
    def _try(self, action, message):
        try:
            result = action()
        except (CompositionAuthoringError, AnimationAuthoringError, ValueError, KeyError, TypeError, IndexError) as exc:
            self.last_error = str(exc)
            self.status.setStyleSheet("color: #d9534f;")
            self.status.setText(str(exc))
            return None
        self.last_error = None
        self.status.setStyleSheet("")
        self.status.setText(message)
        self._load()
        self.changed.emit()
        return result if result is not None else True

    def add_socket_from_form(self):
        socket_id = self.socket_id.text().strip()
        return self._try(
            lambda: self.api.add_socket(
                self.sheet,
                socket_id,
                self.socket_x.value(),
                self.socket_y.value(),
                parent=self.socket_parent.currentText() or None,
            ),
            f"Socket {socket_id} added",
        )

    def key_socket_from_form(self):
        socket_id = self.socket_id.text().strip()
        frame = self.frame.value()
        return self._try(
            lambda: self.api.set_socket_key(
                self.sheet, socket_id, frame, self.socket_x.value(), self.socket_y.value(), self.socket_rotation.value()
            ),
            f"{socket_id} keyed at frame {frame}",
        )

    def attach_from_form(self):
        attachment_id = self.attachment_id.text().strip()
        return self._try(
            lambda: self.api.attach(
                self.sheet,
                attachment_id,
                self.item_sheet.currentText(),
                self.attach_socket.currentText(),
                rotation=self.attach_rotation.value(),
                scale=self.attach_scale.value(),
                front=self.front.isChecked(),
                frame=self.item_frame.value(),
                grip=(self.grip_x.value(), self.grip_y.value()),
            ),
            f"{attachment_id} attached",
        )

    def add_layer_from_form(self):
        clips = tuple(c.strip() for c in self.layer_clips.text().split(",") if c.strip())
        return self._try(
            lambda: self.api.add_layer(
                self.sheet,
                self.layer_sheet.currentText(),
                component_id=self.layer_component.text().strip() or "foreground",
                z=self.layer_z.value(),
                clips=clips,
            ),
            "Layer added",
        )
