"""Animation editor (EDT-05, ANI-04, AST-02): sheet grid, clips, events, pivot and live preview.

Layout (progressive disclosure): sheets + clips on the left, the frame grid
in the centre (click a cell to append it to the clip), clip / event / pivot
properties on the right, and a preview strip at the bottom that plays the
clip through the runtime animation path.
"""

from __future__ import annotations

from PySide6.QtCore import QRect, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .animation_authoring import AnimationAuthoringController, AnimationAuthoringError
from .ui_fit import fit_list_to_width

_CLIP_WORDS = {  # a clip name's first word, in plain words
    "idle": "Standing",
    "walk": "Walking",
    "run": "Running",
    "attack": "Attack 1",
    "attack2": "Attack 2",
    "attack3": "Attack 3",
    "cast": "Casting a spell",
    "hit": "Getting hit",
    "hurt": "Getting hit",
    "guard": "Guarding",
    "ko": "Knocked out",
    "revive": "Getting back up",
    "status": "Under a status",
    "transform": "Transforming",
    "victory": "Winning",
    "jump": "Jumping",
}
_FACING_WORDS = {"down": "facing you", "up": "facing away", "left": "facing left",
                 "right": "facing right"}  # fmt: skip


def _words(text):
    return str(text).replace("_", " ").replace(".", " ").strip().title()


def sheet_title(project, asset_id):
    """A sprite sheet in words: who it draws or what effect it is, e.g. ``Aldric · party`` for
    ``battle.combatant.hero_01``; any other sheet reads as its last name part."""
    asset_id = str(asset_id)
    key = asset_id.rsplit(".", 1)[-1]
    db = getattr(project, "rpg_database", None)
    if asset_id.startswith("battle.combatant."):
        actor = getattr(db, "actors", {}).get(key) if db is not None else None
        if actor is not None:
            return f"{actor.display_name or _words(key)} · party"
        enemy = getattr(db, "enemies", {}).get(key) if db is not None else None
        if enemy is not None:
            return f"{getattr(enemy, 'display_name', '') or _words(key)} · foe"
        return f"{_words(key)} · fighter"
    if asset_id.startswith(("battle.fx.", "battle.vfx.")):
        return f"Effect: {_words(key)}"
    assets = getattr(project, "assets", None)
    for record in assets.records() if assets is not None else ():
        if record.id == asset_id and record.name:  # an imported sheet: its own name
            return record.name
    return _words(key)


def fill_sheet_list(listing, ids, project):
    """Fill a list of sprite sheets with their names in words; each row keeps the sheet's
    asset id as its data (and in its tooltip)."""
    listing.clear()
    for asset_id in ids:
        item = QListWidgetItem(sheet_title(project, asset_id))
        item.setData(Qt.UserRole, asset_id)
        item.setToolTip(f"Sheet id: {asset_id}")
        listing.addItem(item)


def fill_sheet_combo(combo, ids, project):
    """The same for a drop-down: names shown, the asset id is each entry's data."""
    current = combo.currentData()
    combo.clear()
    for asset_id in ids:
        combo.addItem(sheet_title(project, asset_id), asset_id)
    if current in ids:
        combo.setCurrentIndex(combo.findData(current))


def listed_id(item):
    """The id a row of such a list stands for."""
    if item is None:
        return None
    return item.data(Qt.UserRole) or item.text()


def clip_title(name, clip=None):
    """A clip in words: ``idle_left`` -> "Standing, facing left  (5 frames, loops)"."""
    head, _, tail = str(name).partition("_")
    words = _CLIP_WORDS.get(head, _words(head))
    if tail:
        words += ", " + _FACING_WORDS.get(tail, _words(tail).lower())
    if clip:
        count = len(clip.get("frames", ()))
        words += f"  ({count} frame{'s' * (count != 1)}{', loops' if clip.get('loop') else ''})"
    return words


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

    def _frames(self):
        """``(count, source columns)`` of the sheet's frames."""
        fw, fh = self.frame_size
        columns = max(1, self.pixmap.width() // max(1, fw))
        rows = max(1, self.pixmap.height() // max(1, fh))
        return columns * rows, columns

    def _layout(self):
        """``(scale, display columns)``: the frames wrapped into as many columns as make them
        largest in the view (a long one-row strip shows as several rows, not a thin line)."""
        if self.pixmap is None or self.pixmap.isNull():
            return 1.0, 1
        fw, fh = self.frame_size
        count, _columns = self._frames()
        best = (0.0, 1)
        for columns in range(1, count + 1):
            rows = -(-count // columns)
            scale = min(self.width() / (columns * fw), self.height() / (rows * fh), 4.0)
            if scale > best[0]:
                best = (scale, columns)
        return max(0.1, best[0]), best[1]

    def _cell_rect(self, index, scale, columns):
        fw, fh = self.frame_size
        return QRect(
            int((index % columns) * fw * scale),
            int((index // columns) * fh * scale),
            int(fw * scale),
            int(fh * scale),
        )

    def cell_at(self, x, y):
        if self.pixmap is None or self.pixmap.isNull():
            return None
        scale, columns = self._layout()
        fw, fh = self.frame_size
        count, _ = self._frames()
        column, row = int(x / (fw * scale)), int(y / (fh * scale))
        index = row * columns + column
        if 0 <= column < columns and 0 <= index < count:
            return index
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
        scale, columns = self._layout()
        fw, fh = self.frame_size
        count, source_columns = self._frames()
        for index in range(count):
            rect = self._cell_rect(index, scale, columns)
            source = QRect((index % source_columns) * fw, (index // source_columns) * fh, fw, fh)
            painter.drawPixmap(rect, self.pixmap, source)
            painter.setPen(QPen(QColor(124, 145, 190, 160), 1))
            painter.drawRect(rect.adjusted(0, 0, -1, -1))
            painter.setPen(QColor(150, 158, 175))  # the frame's number, as typed in "Frames"
            painter.drawText(
                rect.adjusted(0, 0, -3, -2), Qt.AlignRight | Qt.AlignBottom, str(index)
            )
        painter.setPen(QPen(QColor(240, 201, 93), 2))
        for order, index in enumerate(self.highlight):
            if not 0 <= index < count:
                continue
            rect = self._cell_rect(index, scale, columns)
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

        # the lists show names in words; each row keeps its real id (the sheet's asset id, the
        # clip's name) as its data
        self.sheet_list = QListWidget()
        self.sheet_list.setIconSize(QSize(32, 32))
        fit_list_to_width(self.sheet_list)
        self.clip_list = QListWidget()
        self.sheet_filter = QLineEdit()
        self.sheet_filter.setPlaceholderText("Search sheets…")
        self.sheet_filter.setClearButtonEnabled(True)
        self.sheet_filter.textChanged.connect(self._filter_sheets)
        self.sheet_list.currentItemChanged.connect(
            lambda item, _old: self._sheet_changed(self._id(item))
        )
        self.clip_list.currentItemChanged.connect(
            lambda item, _old: self._clip_changed(self._id(item))
        )
        add_clip, remove_clip, rename_clip = (
            QPushButton("New Clip…"),
            QPushButton("Delete"),
            QPushButton("Rename…"),
        )
        add_clip.clicked.connect(self._new_clip_clicked)
        remove_clip.clicked.connect(self.remove_clip)
        rename_clip.clicked.connect(self._rename_clicked)
        left = QVBoxLayout()
        step_one = QLabel("<b>1. Sprite sheet</b> - a picture cut into frames")
        step_two = QLabel("<b>2. Animation</b> - pick one to edit or preview")
        for label in (step_one, step_two):
            label.setWordWrap(True)
        left.addWidget(step_one)
        left.addWidget(self.sheet_filter)
        left.addWidget(self.sheet_list, 1)
        left.addWidget(step_two)
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
        self.frames.setPlaceholderText("click frames in the grid, or type 0, 1, 2, 1")
        self.frames.setToolTip(
            "The frames this animation plays, in order: the numbers shown on the sheet in the "
            "middle. Click a frame there to add it."
        )
        self.duration = QDoubleSpinBox()
        self.duration.setRange(0.01, 10.0)
        self.duration.setDecimals(3)
        self.duration.setSingleStep(0.01)
        self.loop = QCheckBox("Loop")
        self.events = QLineEdit()
        self.events.setPlaceholderText("step:event, e.g. 2:hit (the blow lands on step 2)")
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
        # how the game resizes the frames: sharp pixels, or blended for painted / rendered art
        self.scaling = QComboBox()
        self.scaling.addItem("Pixel art (sharp)", "pixel")
        self.scaling.addItem("Smooth (painted or rendered)", "smooth")
        self.scaling.setToolTip(
            "Pixel art keeps every pixel a crisp square when the frame is enlarged. Smooth "
            "blends neighbouring pixels: for painted or 3D-rendered pictures, which would "
            "otherwise show jagged edges."
        )
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
        sheet_form.addRow("Scaling", self.scaling)
        sheet_form.addRow(apply_sheet)

        # how the battle uses this sheet: the body's real height (menus and bars sit on it) and,
        # when the sheet is a skill effect, where it appears on its target
        self.body_height = QSpinBox()
        self.body_height.setRange(0, 4096)
        self.body_height.setSpecialValueText("whole frame")
        self.body_height.setToolTip(
            "Height of the character itself in the sheet's pixels. Health bars and command "
            "menus sit on this instead of on the empty room in the frame."
        )
        self.vfx_on = QCheckBox("Used as an effect")
        self.vfx_anchor = QComboBox()
        self.vfx_anchor.addItems(["feet", "center", "head"])
        self.vfx_x, self.vfx_y = QDoubleSpinBox(), QDoubleSpinBox()
        for spin in (self.vfx_x, self.vfx_y):
            spin.setRange(-512.0, 512.0)
        self.vfx_scale = QDoubleSpinBox()
        self.vfx_scale.setRange(0.05, 8.0)
        self.vfx_scale.setSingleStep(0.1)
        self.vfx_scale.setValue(0.6)
        apply_use = QPushButton("Apply Battle Use")
        apply_use.clicked.connect(self.apply_battle_use)
        use_box = QGroupBox("Battle use")
        use_form = QFormLayout(use_box)
        offset_row = QHBoxLayout()
        offset_row.addWidget(self.vfx_x)
        offset_row.addWidget(self.vfx_y)
        use_form.addRow("Body height", self.body_height)
        use_form.addRow(self.vfx_on)
        use_form.addRow("Appears at", self.vfx_anchor)
        use_form.addRow("Offset (x, y)", offset_row)
        use_form.addRow("Scale", self.vfx_scale)
        use_form.addRow(apply_use)

        self.status = QLabel("")
        self.status.setWordWrap(True)
        right = QVBoxLayout()
        right.addWidget(clip_box)
        right.addWidget(sheet_box)
        right.addWidget(use_box)
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
    @staticmethod
    def _id(item):
        return None if item is None else item.data(Qt.UserRole)

    @property
    def sheet(self):
        return self._id(self.sheet_list.currentItem())

    @property
    def clip(self):
        return self._id(self.clip_list.currentItem())

    def _filter_sheets(self, text):
        text = text.strip().lower()
        for row in range(self.sheet_list.count()):
            item = self.sheet_list.item(row)
            shown = not text or text in item.text().lower() or text in self._id(item).lower()
            item.setHidden(not shown)

    def _sheet_icon(self, asset_id):
        """The sheet's first frame, for its row in the list."""
        from PySide6.QtGui import QIcon

        try:
            pixmap = self._pixmap(asset_id)
            width, height = self.api.data(asset_id)["frame_size"]
        except (AnimationAuthoringError, OSError, KeyError):
            return None
        if pixmap.isNull():
            return None
        first = pixmap.copy(0, 0, min(width, pixmap.width()), min(height, pixmap.height()))
        return QIcon(first)

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
        project = self.api.document.project
        for asset_id in sheets:
            item = QListWidgetItem(sheet_title(project, asset_id))
            item.setData(Qt.UserRole, asset_id)
            item.setToolTip(f"Sheet id: {asset_id}")
            icon = self._sheet_icon(asset_id)
            if icon is not None:
                item.setIcon(icon)
            self.sheet_list.addItem(item)
        self.sheet_list.blockSignals(False)
        self._filter_sheets(self.sheet_filter.text())
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
        for name in names:
            item = QListWidgetItem(clip_title(name, data["clips"][name]))
            item.setData(Qt.UserRole, name)
            item.setToolTip(f"Animation name: {name} (what skills and states ask for)")
            self.clip_list.addItem(item)
        self.clip_list.blockSignals(False)
        self.frame_w.setValue(data["frame_size"][0])
        self.frame_h.setValue(data["frame_size"][1])
        self.pivot_x.setValue(data["pivot"][0])
        self.pivot_y.setValue(data["pivot"][1])
        self.scaling.setCurrentIndex(max(0, self.scaling.findData(data["scaling"])))
        self.body_height.setValue(int(data["body_height"]))
        placement = data["vfx"]
        self.vfx_on.setChecked(placement is not None)
        if placement is not None:
            self.vfx_anchor.setCurrentText(placement["anchor"])
            self.vfx_x.setValue(placement["offset"][0])
            self.vfx_y.setValue(placement["offset"][1])
            self.vfx_scale.setValue(placement["scale"])
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
        self.events.setText(
            ", ".join(
                f"{k}:{n}" for k, names in dict(clip.get("events", {})).items() for n in names
            )
        )
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
                sheet,
                clip,
                frames=frames,
                frame_duration=self.duration.value(),
                loop=self.loop.isChecked(),
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
            if data["scaling"] != self.scaling.currentData():
                self.api.set_scaling(sheet, self.scaling.currentData())

        ok = self._try(apply, f"Applied grid / pivot for {sheet}")
        self.refresh(sheet, self.clip)
        return ok

    def apply_battle_use(self):
        sheet = self.sheet
        if not sheet:
            return False

        def apply():
            self.api.set_body_height(sheet, self.body_height.value())
            if self.vfx_on.isChecked():
                self.api.set_vfx(
                    sheet,
                    self.vfx_anchor.currentText(),
                    offset=(self.vfx_x.value(), self.vfx_y.value()),
                    scale=self.vfx_scale.value(),
                )
            else:
                self.api.set_vfx(sheet, None)

        ok = self._try(apply, f"Applied battle use for {sheet}")
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
