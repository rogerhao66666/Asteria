"""A small dock that plays an imported 2D skeleton so a rig can be checked before use."""

import weakref

try:
    from PySide6.QtCore import QEvent, Qt, QTimer, Signal
    from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
    from PySide6.QtWidgets import (
        QComboBox,
        QDoubleSpinBox,
        QFileDialog,
        QFormLayout,
        QFrame,
        QGroupBox,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QPushButton,
        QScrollArea,
        QSlider,
        QVBoxLayout,
        QWidget,
    )
except ImportError:
    QWidget = object
    Qt = None
    Signal = None

from asteria.runtime import SkeletonAnimation2DComponent
from asteria.runtime.skeleton_draw import to_texture_draws

from .commands import (
    AddComponentCommand,
    CommandStack,
    CommandTransaction,
    SetAttributeCommand,
    SetSkeletonCommand,
)
from .scene_render import resolve_texture_source
from .skeleton_editing import add_bone, delete_bone, edit_bone, set_key
from .skeleton_view import bone_segments, bounds, load_rig

try:
    from asteria.graphics.skeleton import Bone
    from asteria.graphics.skeleton_data import save_skeleton
except ImportError:
    Bone = None
    save_skeleton = None


class _Canvas(QWidget):
    def __init__(self, owner):
        super().__init__()
        # a weak reference: the owner holds this widget, and a cycle between a widget and
        # the window it sits in crashed PySide6 6.12's garbage collection (a segfault)
        self._owner = weakref.ref(owner)
        self.setMinimumHeight(180)

    @property
    def owner(self):
        return self._owner()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(32, 34, 38))
        segments = self.owner.segments()
        if not segments:  # say what to do instead of an empty grey box
            painter.setPen(QColor(150, 158, 175))
            painter.drawText(
                self.rect().adjusted(24, 0, -24, 0),
                Qt.AlignCenter | Qt.TextWordWrap,
                'No rig open. Click "Open rig…" to load a skeleton, then pick a bone below '
                'to move it or key it on the timeline; "Attach to selected entity" puts it '
                "on a character in the scene.",
            )
            return
        left, top, right, bottom = bounds(segments)
        scale = min(self.width() / max(right - left, 1), self.height() / max(bottom - top, 1))
        ox = (self.width() - (right - left) * scale) / 2 - left * scale
        oy = (self.height() - (bottom - top) * scale) / 2 - top * scale
        for draw in self.texture_draws(scale, ox, oy):
            self._paint_texture(painter, draw)
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

    def texture_draws(self, scale=None, ox=None, oy=None):
        """Build preview quads through the same Skeleton and runtime draw adapters as the game."""
        owner = self.owner
        if owner.skeleton is None or owner.document is None:
            return ()
        segments = owner.segments()
        if not segments:
            return ()
        left, top, right, bottom = bounds(segments)
        scale = scale or min(
            self.width() / max(right - left, 1), self.height() / max(bottom - top, 1)
        )
        ox = (self.width() - (right - left) * scale) / 2 - left * scale if ox is None else ox
        oy = (self.height() - (bottom - top) * scale) / 2 - top * scale if oy is None else oy

        class Camera:
            zoom = scale

            @staticmethod
            def world_to_screen(x, y):
                return x * scale + ox, y * scale + oy

        clip = owner.clip()
        clip_name = clip.name if clip else None
        pose = owner.skeleton.pose(clip_name, owner.time)
        rows = owner.skeleton.draws(pose, clip_name, owner.time)
        return to_texture_draws(
            rows,
            owner.document.asset_views.sprite_sheet,
            camera=Camera(),
        )

    def _paint_texture(self, painter, draw):
        path = resolve_texture_source(self.owner.document, draw.texture_asset_id)
        if path is None:
            return
        cache = self.owner._texture_cache
        pixmap = cache.get(draw.texture_asset_id)
        if pixmap is None:
            pixmap = QPixmap(str(path))
            cache[draw.texture_asset_id] = pixmap
        if pixmap.isNull():
            return
        source = pixmap.copy(*draw.source)
        painter.save()
        painter.setOpacity(draw.opacity)
        painter.translate(draw.screen_x + draw.width / 2, draw.screen_y + draw.height / 2)
        painter.rotate(draw.rotation_deg)
        if draw.flip_x:
            painter.scale(-1, 1)
        painter.drawPixmap(
            int(-draw.width / 2),
            int(-draw.height / 2),
            max(1, round(draw.width)),
            max(1, round(draw.height)),
            source,
        )
        painter.restore()


class _Timeline(QWidget):
    def __init__(self, owner):
        super().__init__()
        # a weak reference: the owner holds this widget, and a cycle between a widget and
        # the window it sits in crashed PySide6 6.12's garbage collection (a segfault)
        self._owner = weakref.ref(owner)
        self.setMinimumHeight(12)
        self.setMaximumHeight(16)

    @property
    def owner(self):
        return self._owner()

    def key_positions(self):
        clip = self.owner.clip()
        if clip is None:
            return ()
        return tuple(key.time / clip.duration for _track, keys in clip.tracks for key in keys)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(29, 31, 35))
        y = self.height() // 2
        painter.setPen(QPen(QColor(83, 88, 98), 2))
        painter.drawLine(0, y, self.width(), y)
        painter.setPen(QPen(QColor(77, 210, 198), 2))
        for position in self.key_positions():
            x = round(position * max(0, self.width() - 1))
            painter.drawLine(x, 1, x, self.height() - 1)

    def mousePressEvent(self, event):
        clip = self.owner.clip()
        if clip is not None and self.width() > 1:
            fraction = max(0.0, min(1.0, event.position().x() / (self.width() - 1)))
            self.owner._set_time(clip.duration * fraction)
            event.accept()
            return
        super().mousePressEvent(event)


class SkeletonViewerWidget(QWidget):
    if Signal is not None:
        changed = Signal()

    TICKS = 100  # slider steps across a clip

    def __init__(self, parent=None, *, command_stack=None, document=None):
        if Qt is None:
            raise RuntimeError("PySide6 is required")
        super().__init__(parent)
        self.skeleton = None
        self.time = 0.0
        self.command_stack = command_stack or CommandStack()
        self.document = document
        self._texture_cache = {}
        self.file_path = None
        self._selected_key_time = None
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        self.open_button = QPushButton("Open rig…")
        self.save_button = QPushButton("Save rig…")
        self.attach_button = QPushButton("Attach to selected entity")
        self.clip_combo = QComboBox()
        self.play_button = QPushButton("Play")
        self.play_button.setCheckable(True)
        for widget in (
            self.open_button,
            self.save_button,
            self.attach_button,
            self.clip_combo,
            self.play_button,
        ):
            top.addWidget(widget)
        layout.addLayout(top)
        self.canvas = _Canvas(self)
        layout.addWidget(self.canvas, 1)
        self.slider = QSlider(Qt.Horizontal)
        self.slider.setRange(0, self.TICKS)
        layout.addWidget(self.slider)
        self.timeline = _Timeline(self)
        layout.addWidget(self.timeline)

        controls = QWidget(self)
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        controls_layout.setSpacing(layout.spacing())
        self._build_bone_editor(controls_layout)
        self._build_key_editor(controls_layout)
        self.status = QLabel("No rig open yet")
        self.status.setObjectName("MutedLabel")
        self.status.setWordWrap(True)
        controls_layout.addWidget(self.status)
        self.controls_scroll = QScrollArea(self)
        self.controls_scroll.setObjectName("SkeletonControlsScrollArea")
        self.controls_scroll.setFrameShape(QFrame.NoFrame)
        self.controls_scroll.setWidgetResizable(True)
        self.controls_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.controls_scroll.setWidget(controls)
        layout.addWidget(self.controls_scroll, 1)
        for field in (
            self.bone_combo,
            self.bone_parent,
            self.bone_x,
            self.bone_y,
            self.bone_rotation,
            self.bone_scale_x,
            self.bone_scale_y,
            self.bone_length,
            self.track_bone,
            self.track_channel,
            self.key_combo,
            self.key_time,
            self.key_value,
            self.key_easing,
        ):
            field.installEventFilter(self)
        self._timer = QTimer(self)
        self._timer.setInterval(33)
        self._timer.timeout.connect(self._advance)
        self.open_button.clicked.connect(self._choose)
        self.save_button.clicked.connect(self._choose_save)
        self.attach_button.clicked.connect(self.attach_to_selected)
        self.clip_combo.currentTextChanged.connect(lambda _: self._set_time(0.0))
        self.play_button.toggled.connect(
            lambda on: self._timer.start() if on else self._timer.stop()
        )
        self.slider.valueChanged.connect(self._scrub)

    def eventFilter(self, watched, event):
        if (
            event.type() == QEvent.Wheel
            and isinstance(watched, QDoubleSpinBox)
            and self._is_scroll_field(watched)
        ):
            # Scrolling the inspector must never edit a field, even while focused.
            delta = event.pixelDelta().y() or event.angleDelta().y()
            if delta:
                bar = self.controls_scroll.verticalScrollBar()
                bar.setValue(bar.value() - delta)
            event.accept()
            return True
        return super().eventFilter(watched, event)

    def _is_scroll_field(self, widget):
        return widget in (
            self.bone_combo,
            self.bone_parent,
            self.bone_x,
            self.bone_y,
            self.bone_rotation,
            self.bone_scale_x,
            self.bone_scale_y,
            self.bone_length,
            self.track_bone,
            self.track_channel,
            self.key_combo,
            self.key_time,
            self.key_value,
            self.key_easing,
        )

    def set_document(self, document):
        self.document = document
        self._texture_cache.clear()
        self.canvas.update()

    def attach_to_selected(self):
        if self.document is None or self.skeleton is None:
            return False
        selection = self.document.selection
        entity = selection.value if selection.kind == "entity" else None
        if selection.kind == "component" and selection.value is not None:
            entity = getattr(selection.value, "entity", None)
        if entity is None:
            self.status.setText("Select an entity before attaching this rig")
            return False
        import json

        from asteria.graphics.skeleton_data import skeleton_to_data

        rig_json = json.dumps(skeleton_to_data(self.skeleton), ensure_ascii=False)
        existing = entity.try_get(SkeletonAnimation2DComponent)
        clip_name = self.clip_combo.currentText()
        if existing is None:
            component = SkeletonAnimation2DComponent(rig_json, clip_name=clip_name)
            self.command_stack.execute(AddComponentCommand(entity, component))
        else:
            transaction = CommandTransaction(
                "Update attached skeleton",
                (
                    SetAttributeCommand(
                        existing, "skeleton_json", rig_json, existing.skeleton_json
                    ),
                    SetAttributeCommand(existing, "clip_name", clip_name, existing.clip_name),
                ),
            )
            self.command_stack.execute(transaction)
        self.status.setText(f"Attached {self.skeleton.skeleton_id} to {entity.name}")
        self.changed.emit()
        return True

    @staticmethod
    def _number(parent, *, minimum=-1000000.0, maximum=1000000.0, step=1.0):
        field = QDoubleSpinBox(parent)
        field.setRange(minimum, maximum)
        field.setDecimals(3)
        field.setSingleStep(step)
        return field

    def _build_bone_editor(self, layout):
        group = QGroupBox("Bones")
        form = QFormLayout(group)
        self.bone_combo = QComboBox(group)
        self.bone_name = QLineEdit(group)
        self.bone_parent = QComboBox(group)
        self.bone_x = self._number(group)
        self.bone_y = self._number(group)
        self.bone_rotation = self._number(group)
        self.bone_scale_x = self._number(group, minimum=-1000, maximum=1000, step=0.1)
        self.bone_scale_y = self._number(group, minimum=-1000, maximum=1000, step=0.1)
        self.bone_length = self._number(group, minimum=0, maximum=1000000)
        for label, field in (
            ("Bone", self.bone_combo),
            ("Name", self.bone_name),
            ("Parent", self.bone_parent),
            ("X", self.bone_x),
            ("Y", self.bone_y),
            ("Rotation", self.bone_rotation),
            ("Scale X", self.bone_scale_x),
            ("Scale Y", self.bone_scale_y),
            ("Length", self.bone_length),
        ):
            form.addRow(label, field)
        actions = QHBoxLayout()
        self.apply_bone_button = QPushButton("Apply Bone")
        self.add_bone_button = QPushButton("Add Bone")
        self.delete_bone_button = QPushButton("Delete Bone")
        for button in (self.apply_bone_button, self.add_bone_button, self.delete_bone_button):
            actions.addWidget(button)
        form.addRow(actions)
        layout.addWidget(group)
        self.bone_combo.currentTextChanged.connect(self._load_bone_form)
        self.apply_bone_button.clicked.connect(self._apply_bone)
        self.add_bone_button.clicked.connect(self._add_bone)
        self.delete_bone_button.clicked.connect(self._delete_bone)

    def _build_key_editor(self, layout):
        group = QGroupBox("Animation Keys")
        form = QFormLayout(group)
        self.track_bone = QComboBox(group)
        self.track_channel = QComboBox(group)
        self.track_channel.addItems(("x", "y", "rotation", "scale_x", "scale_y"))
        self.key_combo = QComboBox(group)
        self.key_time = self._number(group, minimum=0, maximum=1000000, step=0.01)
        self.key_value = self._number(group)
        self.key_easing = QComboBox(group)
        self.key_easing.addItems(("linear", "step", "ease_in", "ease_out", "ease_in_out"))
        for label, field in (
            ("Track bone", self.track_bone),
            ("Channel", self.track_channel),
            ("Key", self.key_combo),
            ("Time", self.key_time),
            ("Value", self.key_value),
            ("Easing to next", self.key_easing),
        ):
            form.addRow(label, field)
        actions = QHBoxLayout()
        self.save_key_button = QPushButton("Add / Update Key")
        self.delete_key_button = QPushButton("Delete Key")
        actions.addWidget(self.save_key_button)
        actions.addWidget(self.delete_key_button)
        form.addRow(actions)
        layout.addWidget(group)
        self.track_bone.currentTextChanged.connect(lambda _: self._refresh_keys())
        self.track_channel.currentTextChanged.connect(lambda _: self._refresh_keys())
        self.clip_combo.currentTextChanged.connect(lambda _: self._refresh_keys())
        self.key_combo.currentIndexChanged.connect(self._load_key_form)
        self.save_key_button.clicked.connect(self._save_key)
        self.delete_key_button.clicked.connect(self._delete_key)

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
        self.file_path = path if str(path).endswith(".asteria.skeleton.json") else None
        note = f" · skipped: {', '.join(notes)}" if notes else ""
        self.status.setText(f"{skeleton.skeleton_id}: {len(skeleton.bones)} bones{note}")
        return True

    def _choose_save(self):
        path = self.file_path
        if not path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save Asteria rig", "", "Asteria Skeleton (*.asteria.skeleton.json)"
            )
        if path:
            self.save_rig(path)

    def save_rig(self, path):
        if self.skeleton is None:
            return False
        try:
            save_skeleton(path, self.skeleton)
        except (OSError, ValueError, TypeError) as exc:
            self.status.setText(f"Could not save: {exc}")
            return False
        self.file_path = str(path)
        self.status.setText(f"Saved {self.skeleton.skeleton_id} to {path}")
        return True

    def set_skeleton(self, skeleton):
        self.skeleton = skeleton
        clip_name = self.clip_combo.currentText()
        self.clip_combo.blockSignals(True)
        self.clip_combo.clear()
        self.clip_combo.addItems(sorted(skeleton.clips))
        if clip_name in skeleton.clips:
            self.clip_combo.setCurrentText(clip_name)
        self.clip_combo.blockSignals(False)
        self._refresh_bone_controls()
        self._set_time(0.0)

    def _refresh_bone_controls(self):
        if self.skeleton is None:
            return
        selected = self.bone_combo.currentText()
        bone_ids = [bone.bone_id for bone in self.skeleton.bones]
        if selected not in bone_ids:
            selected = bone_ids[0] if bone_ids else ""
        for combo in (self.bone_combo, self.track_bone):
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(bone_ids)
            if selected in bone_ids:
                combo.setCurrentText(selected)
            combo.blockSignals(False)
        self._load_bone_form(selected)
        self._refresh_keys()

    def _load_bone_form(self, bone_id):
        if self.skeleton is None or not bone_id:
            return
        index = next(
            (i for i, bone in enumerate(self.skeleton.bones) if bone.bone_id == bone_id), -1
        )
        if index < 0:
            return
        bone = self.skeleton.bones[index]
        self.bone_name.setText(bone.bone_id)
        self.bone_parent.clear()
        self.bone_parent.addItem("<root>", "")
        for parent in self.skeleton.bones[:index]:
            self.bone_parent.addItem(parent.bone_id, parent.bone_id)
        self.bone_parent.setCurrentIndex(max(0, self.bone_parent.findData(bone.parent)))
        for field, value in (
            (self.bone_x, bone.x),
            (self.bone_y, bone.y),
            (self.bone_rotation, bone.rotation),
            (self.bone_scale_x, bone.scale_x),
            (self.bone_scale_y, bone.scale_y),
            (self.bone_length, bone.length),
        ):
            field.setValue(value)

    def _commit_skeleton(self, skeleton, label):
        self.command_stack.execute(SetSkeletonCommand(self, skeleton, self.skeleton, label))

    def _apply_bone(self):
        if self.skeleton is None:
            return
        old_id = self.bone_combo.currentText()
        try:
            changed = edit_bone(
                self.skeleton,
                old_id,
                bone_id=self.bone_name.text().strip(),
                parent=self.bone_parent.currentData() or "",
                x=self.bone_x.value(),
                y=self.bone_y.value(),
                rotation=self.bone_rotation.value(),
                scale_x=self.bone_scale_x.value(),
                scale_y=self.bone_scale_y.value(),
                length=self.bone_length.value(),
            )
        except (KeyError, ValueError) as exc:
            self.status.setText(f"Could not edit bone: {exc}")
            return
        self._commit_skeleton(changed, f"Edit bone {old_id}")

    def _add_bone(self):
        if self.skeleton is None:
            return
        bone_id = self.bone_name.text().strip()
        try:
            changed = add_bone(
                self.skeleton,
                Bone(
                    bone_id,
                    self.bone_parent.currentData() or "",
                    self.bone_x.value(),
                    self.bone_y.value(),
                    self.bone_rotation.value(),
                    self.bone_scale_x.value(),
                    self.bone_scale_y.value(),
                    self.bone_length.value(),
                ),
            )
        except ValueError as exc:
            self.status.setText(f"Could not add bone: {exc}")
            return
        self._commit_skeleton(changed, f"Add bone {bone_id}")
        self.bone_combo.setCurrentText(bone_id)
        self.track_bone.setCurrentText(bone_id)

    def _delete_bone(self):
        if self.skeleton is None:
            return
        bone_id = self.bone_combo.currentText()
        try:
            changed = delete_bone(self.skeleton, bone_id)
        except (KeyError, ValueError) as exc:
            self.status.setText(f"Could not delete bone: {exc}")
            return
        self._commit_skeleton(changed, f"Delete bone {bone_id}")

    def _refresh_keys(self):
        self.key_combo.blockSignals(True)
        self.key_combo.clear()
        self._selected_key_time = None
        if self.skeleton is not None:
            clip = self.clip()
            bone_id = self.track_bone.currentText()
            channel = self.track_channel.currentText()
            if clip is not None:
                keys = dict(clip.tracks).get((bone_id, channel), ())
                for key in keys:
                    label = f"{key.time:.3f}s · {key.value:g} · {key.easing}"
                    self.key_combo.addItem(label, key.time)
        self.key_combo.blockSignals(False)
        self._load_key_form(self.key_combo.currentIndex())
        self.timeline.update()

    def _load_key_form(self, index):
        self._selected_key_time = None
        if self.skeleton is None or index < 0:
            return
        clip = self.clip()
        if clip is None:
            return
        source_time = self.key_combo.itemData(index)
        keys = dict(clip.tracks).get(
            (self.track_bone.currentText(), self.track_channel.currentText()), ()
        )
        key = next((row for row in keys if row.time == source_time), None)
        if key is None:
            return
        self._selected_key_time = key.time
        self.key_time.setValue(key.time)
        self.key_value.setValue(key.value)
        self.key_easing.setCurrentText(key.easing)

    def _save_key(self):
        if self.skeleton is None or self.clip() is None:
            return
        time = self.key_time.value()
        source_time = self._selected_key_time if self._selected_key_time is not None else time
        try:
            changed = set_key(
                self.skeleton,
                self.clip().name,
                self.track_bone.currentText(),
                self.track_channel.currentText(),
                source_time,
                time=time,
                value=self.key_value.value(),
                easing=self.key_easing.currentText(),
            )
        except (KeyError, ValueError) as exc:
            self.status.setText(f"Could not edit key: {exc}")
            return
        self._commit_skeleton(changed, "Add or update animation key")

    def _delete_key(self):
        if self.skeleton is None or self.clip() is None:
            return
        if self._selected_key_time is None:
            return
        try:
            changed = set_key(
                self.skeleton,
                self.clip().name,
                self.track_bone.currentText(),
                self.track_channel.currentText(),
                self._selected_key_time,
                delete=True,
            )
        except (KeyError, ValueError) as exc:
            self.status.setText(f"Could not delete key: {exc}")
            return
        self._commit_skeleton(changed, "Delete animation key")

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
        self.timeline.update()

    def _scrub(self, value):
        clip = self.clip()
        if clip:
            self._set_time(clip.duration * value / self.TICKS)

    def _advance(self):
        self._set_time(self.time + self._timer.interval() / 1000.0)
