"""Presentation ▸ Menu Screens ▸ Layout: design every menu screen on a live canvas (U2b).

Left, the menu screens (a dot marks one with a layout of its own). Middle, the screen drawn by
the game's own code with sample data (``runtime/menu_preview.py``); every element the screen
drew has an outline you can click, drag and resize from its corner. Right, the chosen element:
its place and anchor, whether it shows, its frame picture (nine-patch with the four insets
drawn over it), picture, colours, font, size, alignment, words or field, and the list / grid
settings. The toolbar adds elements of your own (picture, panel, text, gauge, portrait), takes
one out, puts the screen back to the engine's layout, copies another screen's layout, edits
the project-wide menu theme and opens the screen in the game.

Pictures, fonts and sounds come from anywhere: "Choose…" takes a file of your own (copied into
the project's ``ui/`` folder when it is outside it), "Library…" picks one from the bundled CC0
packs. Every change is one undo step (Ctrl+Z).
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGraphicsItem,
    QGraphicsPixmapItem,
    QGraphicsRectItem,
    QGraphicsScene,
    QGraphicsView,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from asteria.presentation.menu_layout import (
    ALIGNS,
    ANCHORS,
    FRAME_AXES,
    IMAGE_MODES,
    SOUND_ROLES,
    MenuElement,
    MenuSlotPlace,
    MenuTheme,
    anchored_rect,
    screen_spec,
)

from .menu_layout_authoring import MenuLayoutAuthoringController

ADDABLE = (("image", "Picture"), ("panel", "Panel"), ("text", "Text"), ("gauge", "Gauge"),
           ("portrait", "Portrait"))  # fmt: skip
FILTERS = {
    "image": "Images (*.png *.jpg *.jpeg *.bmp *.gif)",
    "font": "Fonts (*.ttf *.otf)",
    "sound": "Sounds (*.ogg *.wav *.mp3)",
}
OUTLINE, PICKED = QColor(120, 200, 255, 200), QColor(255, 210, 90, 255)


def _project_root(document):
    from .image_tools import project_root

    return project_root(document)


def import_ui_file(document, path):
    """A file of the author's own as a project path: kept where it is inside the project,
    else copied to ``<project>/ui/``."""
    from .image_tools import IconLibrary

    library = IconLibrary(document)
    library.FOLDER = "ui"
    return library.import_file(path)


class AssetField(QWidget):
    """A project file (picture, font or sound): typed, chosen from disk or from the packs."""

    changed = Signal()

    def __init__(self, document, kind="image", parent=None):
        super().__init__(parent)
        self.document, self.kind = document, kind
        self.edit = QLineEdit()
        self.edit.setPlaceholderText("none (the engine's)")
        self.thumb = QLabel()
        self.thumb.setFixedSize(28, 28)
        self.thumb.setObjectName("MenuAssetThumb")
        choose = QToolButton()
        choose.setText("Choose…")
        choose.setToolTip("Use a file of your own (copied into the project's ui/ folder)")
        choose.clicked.connect(self._choose)
        top, buttons = QHBoxLayout(), QHBoxLayout()  # the path gets the whole width
        if kind == "image":
            top.addWidget(self.thumb)
        top.addWidget(self.edit, 1)
        buttons.addWidget(choose)
        if kind == "image":
            packs = QToolButton()
            packs.setText("Library…")
            packs.setToolTip("Pick a picture from the bundled CC0 asset packs")
            packs.clicked.connect(self._library)
            buttons.addWidget(packs)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        layout.addLayout(top)
        layout.addLayout(buttons)
        self.edit.editingFinished.connect(self._typed)

    def text(self):
        return self.edit.text().strip()

    def setText(self, value):  # noqa: N802 - Qt-style
        self.edit.blockSignals(True)
        self.edit.setText(str(value or ""))
        self.edit.blockSignals(False)
        self._thumb()

    def _typed(self):
        self._thumb()
        self.changed.emit()

    def _thumb(self):
        if self.kind != "image":
            return
        path = _project_root(self.document) / self.text() if self.text() else None
        image = QPixmap(str(path)) if path is not None and path.is_file() else QPixmap()
        if image.isNull():
            self.thumb.clear()
        else:
            self.thumb.setPixmap(image.scaled(28, 28, Qt.KeepAspectRatio, Qt.FastTransformation))

    def _choose(self):
        root = str(_project_root(self.document))
        path, _ = QFileDialog.getOpenFileName(self, "Choose a file", root, FILTERS[self.kind])
        if path:
            self.setText(import_ui_file(self.document, path))
            self.changed.emit()

    def _library(self):
        from .asset_library_dialog import AssetLibraryDialog

        repo = Path(__file__).resolve().parents[3] / "asset_library"
        dialog = AssetLibraryDialog(self, root=repo if repo.is_dir() else None)
        if dialog.exec() != QDialog.Accepted or not dialog.picks():
            return
        pack, relative = dialog.picks()[0]
        self.setText(import_ui_file(self.document, Path(pack.path) / relative))
        self.changed.emit()


class ColorField(QWidget):
    """A colour (with alpha) or none; the swatch opens the colour picker."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = None
        self.button = QPushButton()
        self.button.setFixedWidth(96)
        self.button.clicked.connect(self._pick)
        clear = QToolButton()
        clear.setText("×")
        clear.setToolTip("No colour: the engine's")
        clear.clicked.connect(self._clear)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)
        layout.addWidget(clear)
        layout.addStretch(1)
        self._show()

    def color(self):
        return self.value

    def setColor(self, value):  # noqa: N802 - Qt-style
        self.value = tuple(value) if value else None
        self._show()

    def _show(self):
        if self.value is None:
            self.button.setText("engine's")
            self.button.setStyleSheet("")
            return
        r, g, b = self.value[:3]
        a = self.value[3] if len(self.value) > 3 else 255
        self.button.setText(f"#{r:02x}{g:02x}{b:02x}" + (f"{a:02x}" if a != 255 else ""))
        ink = "#000" if r * 0.3 + g * 0.6 + b * 0.1 > 140 else "#fff"
        self.button.setStyleSheet(f"background: rgba({r},{g},{b},{a}); color: {ink};")

    def _pick(self):
        start = QColor(*self.value) if self.value else QColor(255, 255, 255)
        chosen = QColorDialog.getColor(start, self, "Colour", QColorDialog.ShowAlphaChannel)
        if chosen.isValid():
            self.setColor((chosen.red(), chosen.green(), chosen.blue(), chosen.alpha()))
            self.changed.emit()

    def _clear(self):
        self.setColor(None)
        self.changed.emit()


class PatchPreview(QLabel):
    """The nine-patch picture enlarged, its four insets drawn as lines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(96)
        self.setAlignment(Qt.AlignCenter)
        self.setObjectName("MenuPatchPreview")

    def show_patch(self, path, insets):
        image = QPixmap(str(path)) if path and Path(path).is_file() else QPixmap()
        if image.isNull():
            self.setText("no picture")
            return
        scale = max(1, min(8, int(min(220 / image.width(), 90 / image.height()))))
        big = image.scaled(image.width() * scale, image.height() * scale)
        painter = QPainter(big)
        painter.setPen(QPen(QColor(255, 80, 200), 1, Qt.DashLine))
        left, top, right, bottom = (v * scale for v in insets)
        w, h = big.width(), big.height()
        painter.drawLine(left, 0, left, h)
        painter.drawLine(w - right, 0, w - right, h)
        painter.drawLine(0, top, w, top)
        painter.drawLine(0, h - bottom, w, h - bottom)
        painter.end()
        self.setPixmap(big)


class PatchField(QWidget):
    """A nine-patch: its picture, the four corner sizes and how large a pixel is drawn."""

    changed = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.asset = AssetField(document, "image")
        self.insets = [QSpinBox() for _ in range(4)]
        for box in self.insets:
            box.setRange(0, 512)
            box.valueChanged.connect(self._edited)
        self.scale = QDoubleSpinBox()
        self.scale.setRange(0.25, 16.0)
        self.scale.setSingleStep(0.5)
        self.scale.setValue(1.0)
        self.scale.valueChanged.connect(self._edited)
        self.preview = PatchPreview()
        rows = (QHBoxLayout(), QHBoxLayout(), QHBoxLayout())  # two boxes to a row, then scale
        for n, (name, box) in enumerate(zip(("L", "T", "R", "B"), self.insets, strict=True)):
            box.setMinimumWidth(72)
            rows[n // 2].addWidget(QLabel(name))
            rows[n // 2].addWidget(box, 1)
        self.scale.setMinimumWidth(72)
        rows[2].addWidget(QLabel("×"))
        rows[2].addWidget(self.scale, 1)
        rows[2].addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.asset)
        for row in rows:
            layout.addLayout(row)
        layout.addWidget(self.preview)
        self.asset.changed.connect(self._edited)

    def patch(self):
        asset = self.asset.text()
        if not asset:
            return None
        from asteria.presentation.ui_skin import NinePatch

        values = [box.value() for box in self.insets]
        return NinePatch(asset, *values, self.scale.value())

    def setPatch(self, patch):  # noqa: N802 - Qt-style
        widgets = (*self.insets, self.scale)
        for widget in widgets:
            widget.blockSignals(True)
        self.asset.setText(patch.asset_id if patch else "")
        values = (patch.left, patch.top, patch.right, patch.bottom) if patch else (4, 4, 4, 4)
        for box, value in zip(self.insets, values, strict=True):
            box.setValue(value)
        self.scale.setValue(patch.scale if patch else 1.0)
        for widget in widgets:
            widget.blockSignals(False)
        self._preview()

    def _preview(self):
        asset = self.asset.text()
        path = _project_root(self.document) / asset if asset else None
        self.preview.show_patch(path, [box.value() for box in self.insets])

    def _edited(self, *_):
        self._preview()
        self.changed.emit()


class SlotsField(QWidget):
    """A doll's places: which slot, where on the picture (x, y from the doll's corner), the
    picture of the empty place. The n-th row of a slot shows its n-th piece."""

    changed = Signal()
    HEADERS = ("Slot", "X", "Y", "W", "H", "Empty picture")

    def __init__(self, parent=None):
        super().__init__(parent)
        self.table = QTableWidget(0, len(self.HEADERS))
        self.table.setHorizontalHeaderLabels(self.HEADERS)
        self.table.verticalHeader().setVisible(False)
        self.table.setMinimumHeight(150)
        self.table.cellChanged.connect(lambda *_: self.changed.emit())
        add, remove = QToolButton(), QToolButton()
        add.setText("+ Place")
        remove.setText("− Place")
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        buttons = QHBoxLayout()
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addStretch(1)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.table)
        layout.addLayout(buttons)

    def places(self):
        out = []
        for row in range(self.table.rowCount()):
            cells = [self.table.item(row, c) for c in range(len(self.HEADERS))]
            words = [c.text().strip() if c is not None else "" for c in cells]
            if not words[0]:
                continue
            try:
                rect = tuple(int(float(v or 0)) for v in words[1:5])
            except ValueError:
                continue
            out.append(MenuSlotPlace(words[0], rect, words[5]))
        return tuple(out)

    def setPlaces(self, places):  # noqa: N802 - Qt-style
        self.table.blockSignals(True)
        self.table.setRowCount(0)
        for place in places:
            self._row((place.slot_id, *place.rect, place.placeholder))
        self.table.blockSignals(False)

    def _row(self, values):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for column, value in enumerate(values):
            self.table.setItem(row, column, QTableWidgetItem(str(value)))

    def _add(self):
        self._row(("weapon", 0, 0, 64, 64, ""))
        self.changed.emit()

    def _remove(self):
        row = self.table.currentRow()
        if row >= 0:
            self.table.removeRow(row)
            self.changed.emit()


class ElementBox(QGraphicsRectItem):
    """One element's outline on the canvas: drag to move, the corner square resizes."""

    HANDLE = 10

    def __init__(self, view, element_id, rect):
        super().__init__(QRectF(0, 0, rect[2], rect[3]))
        self.view, self.element_id = view, element_id
        self.setPos(rect[0], rect[1])
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable)
        self.setPen(QPen(OUTLINE, 1, Qt.DashLine))
        self.setBrush(QBrush(Qt.NoBrush))
        self.setAcceptHoverEvents(True)
        self.setToolTip(element_id)
        self._resizing = False

    def set_picked(self, picked):
        self.setPen(QPen(PICKED if picked else OUTLINE, 2 if picked else 1,
                         Qt.SolidLine if picked else Qt.DashLine))  # fmt: skip
        self.setZValue(2 if picked else 1)

    def paint(self, painter, option, widget=None):
        super().paint(painter, option, widget)
        if self.pen().color() == PICKED:
            r = self.rect()
            h = self.HANDLE
            painter.fillRect(QRectF(r.right() - h, r.bottom() - h, h, h), PICKED)

    def _on_handle(self, point):
        r = self.rect()
        return (
            point.x() > r.right() - self.HANDLE * 1.5
            and point.y() > r.bottom() - self.HANDLE * 1.5
        )

    def mousePressEvent(self, event):  # noqa: N802 - Qt
        self.view.picked.emit(self.element_id)
        self._resizing = self._on_handle(event.pos())
        self._press = (event.pos(), QRectF(self.rect()))
        if self._resizing:
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):  # noqa: N802 - Qt
        if self._resizing:
            start, rect = self._press
            delta = event.pos() - start
            self.setRect(QRectF(0, 0, max(8, rect.width() + delta.x()),
                                max(8, rect.height() + delta.y())))  # fmt: skip
            return
        super().mouseMoveEvent(event)
        grid = self.view.grid
        if grid > 1:
            self.setPos(round(self.pos().x() / grid) * grid, round(self.pos().y() / grid) * grid)

    def mouseReleaseEvent(self, event):  # noqa: N802 - Qt
        super().mouseReleaseEvent(event)
        self._resizing = False
        r = self.rect()
        rect = (round(self.pos().x()), round(self.pos().y()), round(r.width()), round(r.height()))
        self.view.moved.emit(self.element_id, rect)


class MenuCanvasView(QGraphicsView):
    """The screen as the game draws it, the elements' outlines over it."""

    picked = Signal(str)
    moved = Signal(str, tuple)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MenuLayoutCanvas")
        self.scene_ = QGraphicsScene(self)
        self.setScene(self.scene_)
        self.setRenderHint(QPainter.SmoothPixmapTransform, False)
        self.setBackgroundBrush(QColor(24, 26, 34))
        self.pixmap = QGraphicsPixmapItem()
        self.scene_.addItem(self.pixmap)
        self.boxes = {}
        self.grid = 4

    def show_screen(self, image, boxes, picked=None):
        self.pixmap.setPixmap(QPixmap.fromImage(image))
        for box in self.boxes.values():
            self.scene_.removeItem(box)
        self.boxes = {}
        for element_id, rect in boxes.items():
            box = ElementBox(self, element_id, rect)
            box.set_picked(element_id == picked)
            self.scene_.addItem(box)
            self.boxes[element_id] = box
        self.scene_.setSceneRect(QRectF(0, 0, image.width(), image.height()))
        self.fitInView(self.scene_.sceneRect(), Qt.KeepAspectRatio)

    def pick(self, element_id):
        for key, box in self.boxes.items():
            box.set_picked(key == element_id)

    def resizeEvent(self, event):  # noqa: N802 - Qt
        super().resizeEvent(event)
        self.fitInView(self.scene_.sceneRect(), Qt.KeepAspectRatio)

    def mousePressEvent(self, event):  # noqa: N802 - Qt
        item = self.itemAt(event.position().toPoint())
        if item is None or item is self.pixmap:
            self.picked.emit("")
        super().mousePressEvent(event)


def _spin(low, high, value=0):
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


class ElementInspector(QWidget):
    """Every field of the chosen element; ``edited`` fires (once, after typing stops)."""

    edited = Signal()

    def __init__(self, document, parent=None):
        super().__init__(parent)
        self.document = document
        self.element = None
        self.size = (1280, 720)
        self._loading = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(250)
        self._timer.timeout.connect(self.edited.emit)
        form = QFormLayout(self)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        self.title = QLabel()
        self.title.setObjectName("MenuElementTitle")
        self.title.setWordWrap(True)
        form.addRow(self.title)
        self.engine_place = QCheckBox("Engine's place")
        self.engine_place.setToolTip("Unticked, the element goes where the numbers say")
        self.anchor = QComboBox()
        for anchor in ANCHORS:
            self.anchor.addItem(anchor, anchor)
        self.anchor.setToolTip("The screen corner or edge x and y are measured from")
        self.x, self.y = _spin(-4000, 4000), _spin(-4000, 4000)
        self.w, self.h = _spin(0, 4000), _spin(0, 4000)
        place, size = QHBoxLayout(), QHBoxLayout()  # two rows: four boxes hid their digits
        for row, name, box in ((place, "x", self.x), (place, "y", self.y),
                               (size, "w", self.w), (size, "h", self.h)):  # fmt: skip
            # room for "-4000" beside the theme's arrows (3 digits were cut to 2)
            box.setMinimumWidth(72)
            row.addWidget(QLabel(name))
            row.addWidget(box, 1)
        self.visible = QCheckBox("Shown")
        self.layer = _spin(-50, 50)
        self.layer.setToolTip("Your own elements: below 0 under the screen, 0 and up over it")
        self.skin = PatchField(document)
        self.image = AssetField(document, "image")
        self.image_mode = QComboBox()
        for mode in IMAGE_MODES:
            self.image_mode.addItem(mode, mode)
        self.fill, self.border, self.color = ColorField(), ColorField(), ColorField()
        self.font = AssetField(document, "font")
        self.bitmap_font = QComboBox()
        self.bitmap_font.setToolTip(
            "A font drawn by hand (Bitmap fonts…); what it lacks: the font"
        )
        self.set_fonts(())
        self.frames = _spin(0, 256)
        self.frames.setSpecialValueText("still picture")
        self.frames.setToolTip("The picture is a strip of this many frames")
        self.frame_axis = QComboBox()
        self.frame_axis.setProperty("i18n_choices", True)
        for axis, label in zip(FRAME_AXES, ("left to right", "top to bottom"), strict=True):
            self.frame_axis.addItem(label, axis)
        self.fps = QDoubleSpinBox()
        self.fps.setRange(0.0, 60.0)
        self.fps.setSingleStep(1.0)
        self.fps.setSpecialValueText("the screen's")
        self.fps.setToolTip("Frames a second; the screen's: it picks the frame (a cooldown)")
        self.font_size = _spin(0, 200)
        self.font_size.setSpecialValueText("engine's")
        self.align = QComboBox()
        for align in ALIGNS:
            self.align.addItem(align or "engine's", align)
        self.words = QLineEdit()
        self.words.setPlaceholderText("Words, {field} or key:translation.key|English")
        self.binding = QComboBox()
        self.binding.setProperty("i18n_choices", True)
        self.row_height, self.icon_size = _spin(0, 400), _spin(0, 256)
        self.columns, self.cell, self.gap = _spin(0, 32), _spin(0, 256), _spin(-1, 128, -1)
        for box in (self.row_height, self.icon_size, self.columns, self.cell):
            box.setSpecialValueText("engine's")
        self.gap.setSpecialValueText("engine's")
        self.selection_skin = PatchField(document)
        self.selection_fill = ColorField()
        form.addRow(self.engine_place)
        form.addRow("Anchor", self.anchor)
        form.addRow("Place", place)
        form.addRow("Size", size)
        form.addRow(self.visible)
        form.addRow("Layer", self.layer)
        form.addRow("Frame (nine-patch)", self.skin)
        form.addRow("Picture", self.image)
        form.addRow("Picture fit", self.image_mode)
        form.addRow("Animation frames", self.frames)
        form.addRow("Frames run", self.frame_axis)
        form.addRow("Frames (or letters) a second", self.fps)
        form.addRow("Fill", self.fill)
        form.addRow("Border", self.border)
        form.addRow("Text colour", self.color)
        form.addRow("Font", self.font)
        form.addRow("Bitmap font", self.bitmap_font)
        form.addRow("Text size", self.font_size)
        form.addRow("Align", self.align)
        form.addRow("Words", self.words)
        form.addRow("Data field", self.binding)
        form.addRow("Row height", self.row_height)
        form.addRow("Icon size", self.icon_size)
        form.addRow("Columns", self.columns)
        form.addRow("Cell size", self.cell)
        form.addRow("Gap", self.gap)
        form.addRow("Selected row frame", self.selection_skin)
        form.addRow("Selected row colour", self.selection_fill)
        self.slots = SlotsField()
        form.addRow("Doll places", self.slots)
        self.form = form
        for widget in (
            self.x,
            self.y,
            self.w,
            self.h,
            self.layer,
            self.font_size,
            self.row_height,
            self.icon_size,
            self.columns,
            self.cell,
            self.gap,
            self.frames,
            self.fps,
        ):
            widget.valueChanged.connect(self._later)  # fmt: skip
        for widget in (
            self.anchor,
            self.image_mode,
            self.align,
            self.binding,
            self.bitmap_font,
            self.frame_axis,
        ):
            widget.currentIndexChanged.connect(self._later)
        for widget in (self.engine_place, self.visible):
            widget.toggled.connect(self._later)
        self.words.editingFinished.connect(self._later)
        self.slots.changed.connect(self._later)
        for widget in (
            self.skin,
            self.image,
            self.fill,
            self.border,
            self.color,
            self.font,
            self.selection_skin,
            self.selection_fill,
        ):
            widget.changed.connect(self._later)  # fmt: skip
        self.engine_place.toggled.connect(self._place_enabled)

    def _later(self, *_):
        if not self._loading:
            self._timer.start()

    def set_fonts(self, font_ids):
        """The project's bitmap fonts offered in the "Bitmap font" box."""
        current = self.bitmap_font.currentData() or ""
        self.bitmap_font.blockSignals(True)
        self.bitmap_font.clear()
        self.bitmap_font.addItem("none", "")
        for font_id in font_ids:
            self.bitmap_font.addItem(font_id, font_id)
        self.bitmap_font.setCurrentIndex(max(0, self.bitmap_font.findData(current)))
        self.bitmap_font.blockSignals(False)

    def _place_enabled(self, engine):
        for widget in (self.x, self.y, self.w, self.h, self.anchor):
            widget.setEnabled(not engine)

    def load(self, element, description, fields, drawn=None):
        """Show ``element``; ``drawn`` is where the screen drew it (the numbers to start from
        when it is still at the engine's place)."""
        self._loading = True
        self.element = element
        from .i18n import translate

        kind, words = translate(element.kind), translate(description)
        self.title.setText(f"<b>{element.element_id}</b> · {kind}<br>{words}")
        self.engine_place.setChecked(element.rect is None)
        self.anchor.setCurrentIndex(max(0, self.anchor.findData(element.anchor)))
        rect = element.rect
        if rect is None and drawn is not None:
            rect = anchored_rect(drawn, element.anchor, self.size)
        for box, value in zip((self.x, self.y, self.w, self.h), rect or (0, 0, 0, 0), strict=True):
            box.setValue(int(value))
        self._place_enabled(element.rect is None)
        self.visible.setChecked(element.visible)
        self.layer.setValue(element.layer)
        self.skin.setPatch(element.skin)
        self.image.setText(element.image)
        self.image_mode.setCurrentIndex(max(0, self.image_mode.findData(element.image_mode)))
        self.fill.setColor(element.fill)
        self.border.setColor(element.border)
        self.color.setColor(element.color)
        self.font.setText(element.font)
        if element.bitmap_font and self.bitmap_font.findData(element.bitmap_font) < 0:
            self.bitmap_font.addItem(element.bitmap_font, element.bitmap_font)  # gone: kept
        self.bitmap_font.setCurrentIndex(max(0, self.bitmap_font.findData(element.bitmap_font)))
        self.frames.setValue(element.frames)
        self.frame_axis.setCurrentIndex(max(0, self.frame_axis.findData(element.frame_axis)))
        self.fps.setValue(element.fps)
        self.font_size.setValue(element.size)
        self.align.setCurrentIndex(max(0, self.align.findData(element.align)))
        self.words.setText(element.text)
        self.binding.clear()
        self.binding.addItem("none", "")
        for name in fields:
            self.binding.addItem(name, name)
        self.binding.setCurrentIndex(max(0, self.binding.findData(element.binding)))
        self.row_height.setValue(element.row_height)
        self.icon_size.setValue(element.icon_size)
        self.columns.setValue(element.columns)
        self.cell.setValue(element.cell)
        self.gap.setValue(element.gap)
        self.selection_skin.setPatch(element.selection_skin)
        self.selection_fill.setColor(element.selection_fill)
        self.slots.setPlaces(element.slots)
        self.form.setRowVisible(self.slots, element.kind == "doll")
        self._loading = False

    def value(self):
        """The element as the fields now say."""
        element = self.element
        rect = None
        if not self.engine_place.isChecked():
            rect = (self.x.value(), self.y.value(), self.w.value(), self.h.value())
        return replace(
            element,
            rect=rect,
            anchor=self.anchor.currentData(),
            visible=self.visible.isChecked(),
            layer=self.layer.value(),
            skin=self.skin.patch(),
            image=self.image.text(),
            image_mode=self.image_mode.currentData(),
            fill=self.fill.color(),
            border=self.border.color(),
            color=self.color.color(),
            font=self.font.text(),
            size=self.font_size.value(),
            align=self.align.currentData(),
            text=self.words.text(),
            binding=self.binding.currentData() or "",
            row_height=self.row_height.value(),
            icon_size=self.icon_size.value(),
            columns=self.columns.value(),
            cell=self.cell.value(),
            gap=self.gap.value(),
            selection_skin=self.selection_skin.patch(),
            selection_fill=self.selection_fill.color(),
            slots=self.slots.places(),
            frames=self.frames.value(),
            frame_axis=self.frame_axis.currentData(),
            fps=self.fps.value(),
            bitmap_font=self.bitmap_font.currentData() or "",
        )


class MenuThemeDialog(QDialog):
    """The project-wide menu theme: fonts, text colours, frames, cursor, rarities, sounds."""

    def __init__(self, document, theme, rarities=(), parent=None, fonts=()):
        super().__init__(parent)
        self.setWindowTitle("Menu Theme")
        self.resize(560, 640)
        theme = theme or MenuTheme()
        form = QFormLayout()
        self.font_latin = AssetField(document, "font")
        self.font_latin.setText(theme.font_latin)
        self.font_cjk = AssetField(document, "font")
        self.font_cjk.setText(theme.font_cjk)
        self.font_scale = QDoubleSpinBox()
        self.font_scale.setRange(0.25, 4.0)
        self.font_scale.setSingleStep(0.05)
        self.font_scale.setValue(theme.font_scale)
        self.colors = {}
        for name, label in (("text_color", "Text"), ("muted_color", "Quiet text"),
                            ("title_color", "Titles"), ("selected_color", "Selected text"),
                            ("selection_fill", "Selected row")):  # fmt: skip
            field = ColorField()
            field.setColor(getattr(theme, name))
            self.colors[name] = (label, field)
        self.panel_skin = PatchField(document)
        self.panel_skin.setPatch(theme.panel_skin)
        self.selection_skin = PatchField(document)
        self.selection_skin.setPatch(theme.selection_skin)
        self.cursor = AssetField(document, "image")
        self.cursor.setText(theme.cursor_image)
        form.addRow("Latin font", self.font_latin)
        form.addRow("Chinese / Japanese / Korean font", self.font_cjk)
        form.addRow("Font scale", self.font_scale)
        self.bitmap_font = QComboBox()
        self.bitmap_font.addItem("none", "")
        for font_id in fonts:
            self.bitmap_font.addItem(font_id, font_id)
        self.bitmap_font.setCurrentIndex(max(0, self.bitmap_font.findData(theme.bitmap_font)))
        self.bitmap_font.setToolTip("Every menu's words in a font drawn by hand")
        form.addRow("Bitmap font", self.bitmap_font)
        for label, field in self.colors.values():
            form.addRow(label, field)
        form.addRow("Every menu frame", self.panel_skin)
        form.addRow("Selected row frame", self.selection_skin)
        form.addRow("Cursor picture", self.cursor)
        self.rarities = {}
        own = dict(theme.rarity_colors)
        for rarity_id, name in rarities:
            field = ColorField()
            field.setColor(own.get(rarity_id))
            self.rarities[rarity_id] = field
            form.addRow(f"Rarity: {name}", field)
        self.resources = {}
        own = dict(theme.resource_colors)
        for resource in self._resource_names(document, own):
            field = ColorField()
            field.setColor(own.get(resource))
            field.setToolTip("Its orb and bars (the action RPG HUD); none: guessed from its name")
            self.resources[resource] = field
            form.addRow(f"Resource: {resource}", field)
        self.sounds = {}
        own = dict(theme.sounds)
        for role in SOUND_ROLES:
            field = AssetField(document, "sound")
            field.setText(own.get(role, ""))
            self.sounds[role] = field
            form.addRow(f"Sound: {role}", field)
        body = QWidget()
        body.setLayout(form)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(body)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll, 1)
        layout.addWidget(buttons)

    @staticmethod
    def _resource_names(document, own):
        """The project's battle resources (and any the theme already colours)."""
        names = set(own)
        try:
            from .record_vocabulary import vocabulary_for

            names.update(c.value for c in vocabulary_for(document).choices("resources"))
        except Exception:  # noqa: BLE001 - no project: only the theme's own
            pass
        return sorted(str(n) for n in names if n)

    def theme(self):
        return MenuTheme(
            font_latin=self.font_latin.text(),
            font_cjk=self.font_cjk.text(),
            font_scale=self.font_scale.value(),
            panel_skin=self.panel_skin.patch(),
            selection_skin=self.selection_skin.patch(),
            cursor_image=self.cursor.text(),
            bitmap_font=self.bitmap_font.currentData() or "",
            resource_colors=tuple((k, f.color()) for k, f in self.resources.items() if f.color()),
            rarity_colors=tuple((k, f.color()) for k, f in self.rarities.items() if f.color()),
            sounds=tuple((k, f.text()) for k, f in self.sounds.items() if f.text()),
            **{name: field.color() for name, (_label, field) in self.colors.items()},
        )


class MenuLayoutWorkspace(QWidget):
    """The Layout page of Presentation ▸ Menu Screens."""

    changed = Signal()

    def __init__(self, document, parent=None, *, open_in_game=None):
        super().__init__(parent)
        self.setObjectName("MenuLayoutWorkspace")
        self.document = document
        self.controller = MenuLayoutAuthoringController(document)
        self.open_in_game = open_in_game
        self._preview = None
        self._preview_project = None
        self._preview_folder = None  # the game folder's settings file the preview read
        self._stale = True  # the preview waits until the page is shown
        self.screen_id = "shop"
        self.element_id = ""
        self.boxes = {}
        self.screen_list = QListWidget()
        self.screen_list.setObjectName("MenuScreenList")
        self.screen_list.setMinimumWidth(150)
        self.screen_list.setMaximumWidth(230)
        self.canvas = MenuCanvasView()
        self.inspector = ElementInspector(document)
        self.element_combo = QComboBox()
        self.element_combo.setProperty("i18n_choices", True)
        self.language = QComboBox()
        self.language.setProperty("i18n_choices", True)
        add = QToolButton()
        add.setText("Add element")
        add.setPopupMode(QToolButton.InstantPopup)
        menu = QMenu(add)
        for kind, label in ADDABLE:
            menu.addAction(label, lambda kind=kind: self._add(kind))
        add.setMenu(menu)
        buttons = {
            "Remove element": self._remove,
            "Reset screen": self._reset,
            "Copy from…": self._copy,
            "Background…": self._background,
            "Menu theme…": self._theme,
            "Bitmap fonts…": self._bitmap_fonts,
            "Picture message window…": self._dialogue_window,
            "Creature screens…": self._creature_screens,
            "Game folder settings…": self.edit_game_folder_settings,
            "Open in game": self._open_in_game,
        }
        bar = QHBoxLayout()  # what to edit; the screen's actions on the row under it
        bar.addWidget(QLabel("Element"))
        bar.addWidget(self.element_combo, 1)
        bar.addWidget(add)
        bar.addWidget(QLabel("Preview language"))
        bar.addWidget(self.language)
        actions = QGridLayout()  # three to a row: the page fits a laptop screen
        for n, (label, slot) in enumerate(buttons.items()):
            button = QPushButton(label)
            button.clicked.connect(slot)
            actions.addWidget(button, n // 3, n % 3)
        actions.setColumnStretch(3, 1)
        self.status = QLabel()
        self.status.setObjectName("MenuLayoutStatus")
        self.status.setWordWrap(True)
        middle = QWidget()
        column = QVBoxLayout(middle)
        column.setContentsMargins(0, 0, 0, 0)
        column.addLayout(bar)
        column.addLayout(actions)
        column.addWidget(self.canvas, 1)
        column.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(self.inspector)
        # wide enough for its rows (two boxes to a row), the rest goes to the screen being
        # designed; a hint read here would count the rows the element hides later
        scroll.setMinimumWidth(340)
        scroll.setMaximumWidth(460)
        split = QSplitter()
        split.addWidget(self.screen_list)
        split.addWidget(middle)
        split.addWidget(scroll)
        split.setStretchFactor(1, 1)
        split.setSizes([190, 1000, 400])
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.addWidget(split)
        self.screen_list.currentRowChanged.connect(self._screen_chosen)
        self.element_combo.currentIndexChanged.connect(self._element_chosen)
        self.canvas.picked.connect(self.pick)
        self.canvas.moved.connect(self._moved)
        self.inspector.edited.connect(self._inspected)
        self.language.currentIndexChanged.connect(lambda *_: self.refresh_preview())

    # --- building ----------------------------------------------------------------------
    def rebuild(self):
        """Fill everything again from the document (a new project, an undo...)."""
        project = self.document.project
        self.screen_list.blockSignals(True)
        self.screen_list.clear()
        if project is None:
            self.screen_list.blockSignals(False)
            return
        from asteria.presentation.menu_layout import screen_spec as spec_of

        group = "menu"
        for screen_id, title, custom in self.controller.screens():
            if spec_of(screen_id).group != group:  # the screens drawn during play
                group = spec_of(screen_id).group
                header = QListWidgetItem("During play")
                header.setFlags(Qt.NoItemFlags)
                header.setData(Qt.UserRole + 1, "During play")
                self.screen_list.addItem(header)
            item = QListWidgetItem(("● " if custom else "   ") + title)
            item.setData(Qt.UserRole, screen_id)
            item.setData(Qt.UserRole + 1, title)  # the English, shown in the editor's language
            item.setToolTip(screen_id + ("  ·  has its own layout" if custom else ""))
            self.screen_list.addItem(item)
            if screen_id == self.screen_id:
                self.screen_list.setCurrentItem(item)
        self.screen_list.blockSignals(False)
        locales = project.rpg_database.locale_tables
        current = self.language.currentData()
        self.language.blockSignals(True)
        self.language.clear()
        self.language.addItem("default", "")
        for locale in sorted(locales):
            self.language.addItem(locale, locale)
        self.language.setCurrentIndex(max(0, self.language.findData(current)))
        self.language.blockSignals(False)
        self.inspector.set_fonts([k for k, _f in self.controller.fonts()])
        self._fill_elements()
        self.refresh_preview()

    def _fill_elements(self):
        spec = screen_spec(self.screen_id)
        self.element_combo.blockSignals(True)
        self.element_combo.clear()
        self.element_combo.addItem("(screen background)", "")
        described = {i: d for i, _k, d in spec.elements}
        for element_id in self.controller.element_ids(self.screen_id):
            label = element_id + (
                f"  ·  {described[element_id]}" if element_id in described else ""
            )
            self.element_combo.addItem(label, element_id)
        self.element_combo.setCurrentIndex(max(0, self.element_combo.findData(self.element_id)))
        self.element_combo.blockSignals(False)
        self._load_inspector()

    def _load_inspector(self):
        spec = screen_spec(self.screen_id)
        if not self.element_id:
            self.inspector.setEnabled(False)
            self.inspector.title.setText("Choose an element on the canvas or in the list.")
            return
        self.inspector.setEnabled(True)
        element = self.controller.element(self.screen_id, self.element_id)
        described = {i: d for i, _k, d in spec.elements}
        description = described.get(self.element_id, "Your own element")
        self.inspector.load(element, description, spec.fields, self.boxes.get(self.element_id))

    # --- preview -----------------------------------------------------------------------
    def preview(self):
        project = self.document.project
        if project is None or project.game_start is None:
            return None
        folder = self._folder_settings()
        if (
            self._preview is None
            or self._preview_project is not project
            or self._preview_folder != folder  # the game folder's file changed (or undone)
        ):
            if self._preview is not None:
                self._preview.close()
            from asteria.runtime.menu_preview import MenuPreview

            self._preview = MenuPreview(project, _project_root(self.document))
            self._preview_project = project
            self._preview_folder = folder
        return self._preview

    def _folder_settings(self):
        """The game folder's settings file as the preview read it (None: none there)."""
        from .game_folder_settings_dialog import manifest_path

        try:
            return manifest_path(_project_root(self.document)).read_bytes()
        except OSError:
            return None

    def showEvent(self, event):
        super().showEvent(event)
        if self._stale:
            self.refresh_preview()

    def _label_screens(self, custom=None):
        """Each screen's title in the editor's language, marked when it has a layout
        (``custom``: the ids that do; None keeps the marks shown)."""
        from .i18n import translate

        for row in range(self.screen_list.count()):
            item = self.screen_list.item(row)
            if item.data(Qt.UserRole) is None:  # a group's heading
                item.setText(translate(str(item.data(Qt.UserRole + 1))))
                continue
            if custom is None:
                marked = item.text().startswith("●")
            else:
                marked = item.data(Qt.UserRole) in custom
            english = str(item.data(Qt.UserRole + 1))
            # a workstation's own layout ("  ▸ Forge") keeps the station's name
            title = english if english.lstrip().startswith("▸") else translate(english)
            item.setText(("● " if marked else "   ") + title)

    def refresh_preview(self):
        self._label_screens()
        self._stale = not self.isVisible()  # a hidden page draws when it is shown
        if self._stale:
            return
        try:
            preview = self.preview()
            if preview is None:
                self.status.setText("Open a project with a game start to see its menus.")
                return
            surface, boxes = preview.render(self.screen_id, self.language.currentData() or None)
        except Exception as exc:  # noqa: BLE001 - shown in the status line, editing goes on
            self.status.setText(f"Could not draw {self.screen_id}: {exc}")
            return
        import pygame

        width, height = surface.get_size()
        data = pygame.image.tobytes(surface, "RGB")
        image = QImage(data, width, height, width * 3, QImage.Format_RGB888).copy()
        # the canvas shows pixels; the layout (and the inspector) works in the screen's units
        self.unit = unit = getattr(preview, "unit", 1.0) or 1.0
        self.inspector.size = (round(width / unit), round(height / unit))
        self.boxes = {k: tuple(round(v / unit) for v in r) for k, r in boxes.items()}
        self.canvas.show_screen(image, boxes, self.element_id)
        custom = self.controller.layout(self.screen_id) is not None
        self.status.setText(
            f"{screen_spec(self.screen_id).title}  ·  {width}×{height}  ·  "
            + ("its own layout" if custom else "the engine's layout")
            + "  ·  drag an outline to move it, its corner to resize"
        )

    # --- reacting ----------------------------------------------------------------------
    def _screen_chosen(self, row):
        item = self.screen_list.item(row)
        if item is None or item.data(Qt.UserRole) is None:
            return
        self.screen_id = item.data(Qt.UserRole)
        self.element_id = ""
        self.refresh_preview()
        self._fill_elements()

    def _element_chosen(self, index):
        self.element_id = self.element_combo.itemData(index) or ""
        self.canvas.pick(self.element_id)
        self._load_inspector()

    def pick(self, element_id):
        self.element_id = element_id
        self.element_combo.blockSignals(True)
        self.element_combo.setCurrentIndex(max(0, self.element_combo.findData(element_id)))
        self.element_combo.blockSignals(False)
        self.canvas.pick(element_id)
        self._load_inspector()

    def _moved(self, element_id, rect):
        element = self.controller.element(self.screen_id, element_id)
        unit = getattr(self, "unit", 1.0)
        rect = tuple(round(v / unit) for v in rect)
        anchored = anchored_rect(rect, element.anchor, self.inspector.size)
        if element.rect is None and tuple(rect) == tuple(self.boxes.get(element_id, ())):
            return  # a click, not a move
        self.controller.set_element(self.screen_id, replace(element, rect=anchored))
        self._after_change()

    def _inspected(self):
        if not self.element_id or self.inspector.element is None:
            return
        element = self.inspector.value()
        if element == self.controller.element(self.screen_id, self.element_id):
            return
        if not isinstance(element, MenuElement):
            return
        self.controller.set_element(self.screen_id, element)
        self._after_change(reload_inspector=False)

    def _after_change(self, reload_inspector=True):
        self.refresh_preview()
        self._mark_screens()
        if reload_inspector:
            self._load_inspector()
        self.changed.emit()

    def _mark_screens(self):
        self._label_screens({s for s, _t, c in self.controller.screens() if c})

    def _add(self, kind):
        size = self.inspector.size
        rect = anchored_rect((size[0] // 2 - 100, size[1] // 2 - 40, 200, 80), "topleft", size)
        self.element_id = self.controller.add_element(self.screen_id, kind, rect=rect)
        self._fill_elements()
        self._after_change()

    def _remove(self):
        if not self.element_id:
            return
        self.controller.remove_element(self.screen_id, self.element_id)
        if self.element_id.startswith("extra."):
            self.element_id = ""
        self._fill_elements()
        self._after_change()

    def _reset(self):
        if self.controller.layout(self.screen_id) is None:
            return
        answer = QMessageBox.question(
            self, "Reset screen", "Put this screen back to the engine's own layout?"
        )
        if answer == QMessageBox.Yes:
            self.controller.reset(self.screen_id)
            self.element_id = ""
            self._fill_elements()
            self._after_change()

    def _copy(self):
        sources = [(s, t) for s, t, custom in self.controller.screens() if custom]
        sources = [(s, t) for s, t in sources if s != self.screen_id]
        if not sources:
            QMessageBox.information(self, "Copy from…", "No other screen has a layout yet.")
            return
        names = [t for _s, t in sources]
        name, ok = QInputDialog.getItem(self, "Copy from…", "Screen", names, 0, False)
        if ok:
            self.controller.copy_from(self.screen_id, sources[names.index(name)][0])
            self._fill_elements()
            self._after_change()

    def _background(self):
        layout = self.controller.layout(self.screen_id)
        dialog = QDialog(self)
        dialog.setWindowTitle("Screen background")
        form = QFormLayout(dialog)
        color = ColorField()
        color.setColor(layout.background_color if layout else None)
        image = AssetField(self.document, "image")
        image.setText(layout.background_image if layout else "")
        mode = QComboBox()
        for value in IMAGE_MODES:
            mode.addItem(value, value)
        mode.setCurrentIndex(max(0, mode.findData(layout.background_mode if layout else "")))
        dim = _spin(-1, 255, layout.dim if layout else -1)
        dim.setSpecialValueText("engine's")
        music = AssetField(self.document, "sound")
        music.setText(layout.music if layout else "")
        form.addRow("Colour", color)
        form.addRow("Picture", image)
        form.addRow("Picture fit", mode)
        form.addRow("Darken the map (0-255)", dim)
        form.addRow("Music", music)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        form.addRow(buttons)
        if dialog.exec() == QDialog.Accepted:
            self.controller.set_background(
                self.screen_id,
                background_color=color.color(),
                background_image=image.text(),
                background_mode=mode.currentData(),
                dim=dim.value(),
                music=music.text(),
            )
            self._after_change()

    def _theme(self):
        project = self.document.project
        rarities = [
            (r.rarity_id, r.display_name or r.rarity_id)
            for r in project.rpg_database.loot_rarities().values()
        ]
        fonts = [k for k, _f in self.controller.fonts()]
        dialog = MenuThemeDialog(self.document, self.controller.theme(), rarities, self, fonts)
        if dialog.exec() == QDialog.Accepted:
            self.controller.set_theme(dialog.theme())
            self._after_change()

    def _bitmap_fonts(self):
        from .bitmap_font_dialog import BitmapFontDialog

        dialog = BitmapFontDialog(self.document, self.controller.fonts(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        for font_id in dialog.removed():
            self.controller.remove_font(font_id)
        for font, old_id in dialog.fonts():
            self.controller.set_font(font, old_id)
        self.inspector.set_fonts([k for k, _f in self.controller.fonts()])
        self._after_change()

    def _dialogue_window(self):
        from .dialogue_window_dialog import DialogueWindowDialog

        fonts = [k for k, _f in self.controller.fonts()]
        root = _project_root(self.document)
        dialog = DialogueWindowDialog(
            self.document,
            self.controller.dialogue_window(),
            fonts,
            self,
            convert=lambda: self.controller.import_dialogue_manifest(root),
        )
        if dialog.exec() != QDialog.Accepted:
            return
        style = dialog.style()
        if style != self.controller.dialogue_window():
            self.controller.set_dialogue_window(style)
        self.inspector.set_fonts([k for k, _f in self.controller.fonts()])
        self._after_change()

    def _creature_screens(self):
        from asteria.presentation.creature_screens import SCREENS

        from .creature_screens_dialog import CreatureScreensDialog

        root = _project_root(self.document)
        current = {k: self.controller.creature_screen(k) for k in SCREENS}
        dialog = CreatureScreensDialog(
            self.document,
            current,
            self,
            convert=lambda: self.controller.read_creature_manifest(root),
            render=self._render_creature,
        )
        if dialog.exec() != QDialog.Accepted:
            return
        for screen_id, settings in dialog.changes().items():
            self.controller.set_creature_screen(screen_id, settings)
        self._after_change()

    def edit_game_folder_settings(self):
        """The game folder's own settings file in a settings tree (Game folder settings…)."""
        from .game_folder_settings_dialog import GameFolderSettingsDialog, manifest_path

        root = _project_root(self.document)
        if not manifest_path(root).is_file():
            QMessageBox.information(
                self,
                "Game folder settings",
                "This game folder has no playable_test_manifest.json: all of its settings "
                "are in the project.",
            )
            return False
        dialog = GameFolderSettingsDialog(self.document, root, self)
        if dialog.exec() != QDialog.Accepted or not dialog.changed:
            return False
        self._after_change()  # the preview reads the new file (Edit ▸ Undo: the old one)
        return True

    def _render_creature(self, screen_id, settings):
        """The creature screen drawn by the game's own code with ``settings`` (None: the
        manifest's), as a picture for the Creature screens page; None when it cannot be."""
        preview = self.preview()
        if preview is None:
            return None
        surface = preview.render_creature(screen_id, settings)
        if surface is None:
            return None
        import pygame

        width, height = surface.get_size()
        data = pygame.image.tobytes(surface, "RGB")
        image = QImage(data, width, height, width * 3, QImage.Format_RGB888).copy()
        return QPixmap.fromImage(image)

    def _open_in_game(self):
        if self.open_in_game is not None:
            self.open_in_game(self.screen_id)

    def closeEvent(self, event):  # noqa: N802 - Qt
        if self._preview is not None:
            self._preview.close()
            self._preview = None
        super().closeEvent(event)


__all__ = ["MenuLayoutWorkspace", "MenuThemeDialog"]
