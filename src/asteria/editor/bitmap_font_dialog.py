"""Presentation ▸ Menu Screens ▸ Layout ▸ Bitmap fonts…: fonts drawn by hand, set up in the
editor (V1, ``presentation.menu_layout.MenuBitmapFont``).

Left, the project's bitmap fonts. Right, the chosen one: its picture (any PNG of your own,
copied into the project), the cell size, and one line of characters for each row of cells,
typed in order (``⬚`` leaves a cell out). The picture is shown cut into its cells with each
cell's character over it, so a wrong row shows at once; under it a sample line is drawn with
the font exactly as the game draws it. How wide each glyph is comes from its drawn pixels;
the table overrides single characters. Words the font has no glyph for are drawn in the menu
fonts, so Chinese still shows.

The dialog edits copies; OK applies each changed font as one undo step.
"""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from asteria.presentation.menu_layout import EMPTY_CELL, MenuBitmapFont

COLOUR_MODES = (
    ("tint", "Text colour (glyphs drawn in white)"),
    ("keep", "The picture's own colours"),
    ("two_tone", "Two tones: white = text, grey = shadow"),
)
SAMPLE = "THE QUICK BROWN FOX  The quick brown fox  0123456789"


def _spin(low, high, value=0):
    box = QSpinBox()
    box.setRange(low, high)
    box.setValue(value)
    return box


def sheet_font(document, spec):
    """A ``SheetFont`` for the editor's preview (None without its picture)."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from asteria.graphics.bitmap_font import SheetFont

    from .menu_layout_widget import _project_root

    path = _project_root(document) / spec.image if spec.image else None
    if path is None or not path.is_file():
        return None
    try:
        sheet = pygame.image.load(str(path))
    except pygame.error:
        return None
    if sheet.get_alpha() is None and sheet.get_colorkey() is None:
        sheet = sheet.convert_alpha() if pygame.display.get_surface() else sheet
    return SheetFont(pygame, spec, sheet)


def font_image(font, text, colour=(255, 255, 255), scale=None):
    """``text`` drawn with ``font`` as a ``QImage`` (the menus' fallback is not shown here:
    the characters the font lacks are simply left out)."""
    import pygame

    scale = scale or max(2, font.spec.scale)  # the font's own pixel scale, at least 2
    surface = font.surface(text, colour, (90, 90, 90), scale)
    width, height = surface.get_size()
    data = pygame.image.tobytes(surface, "RGBA")
    return QImage(data, width, height, width * 4, QImage.Format_RGBA8888).copy()


class BitmapFontDialog(QDialog):
    """The project's bitmap fonts; ``fonts()`` and ``removed()`` say what OK changes."""

    def __init__(self, document, fonts, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Bitmap Fonts")
        self.resize(1040, 720)
        self.document = document
        self.original = dict(fonts)
        self.work = dict(fonts)  # font id -> MenuBitmapFont (edited copies)
        self.names = {k: k for k in fonts}  # id now -> id it had (renames)
        self.current = ""
        self._loading = False
        from .menu_layout_widget import AssetField

        self.list = QListWidget()
        self.list.setObjectName("BitmapFontList")
        self.list.setMaximumWidth(220)
        add, remove = QPushButton("Add font"), QPushButton("Remove font")
        add.clicked.connect(self._add)
        remove.clicked.connect(self._remove)
        left = QVBoxLayout()
        left.addWidget(self.list, 1)
        left.addWidget(add)
        left.addWidget(remove)
        self.font_id = QLineEdit()
        self.image = AssetField(document, "image")
        self.cell_w, self.cell_h = _spin(1, 256, 8), _spin(1, 256, 8)
        self.colours = QComboBox()
        self.colours.setProperty("i18n_choices", True)
        for value, label in COLOUR_MODES:
            self.colours.addItem(label, value)
        self.spacing = _spin(-16, 64, 1)
        self.space = _spin(0, 256)
        self.space.setSpecialValueText("half a cell")
        self.line = _spin(0, 256)
        self.line.setSpecialValueText("a cell's height")
        self.scale = _spin(0, 16)
        self.scale.setSpecialValueText("by the text size")
        self.fixed = QCheckBox("Every glyph a whole cell wide")
        self.rows = QPlainTextEdit()
        self.rows.setPlaceholderText(
            "One line per row of cells, the characters in order, e.g.\n"
            "ABCDEFGHIJKLMNOP\nQRSTUVWXYZ"
        )
        self.rows.setFixedHeight(130)
        font = QFont("Menlo")
        font.setStyleHint(QFont.Monospace)
        self.rows.setFont(font)
        empty = QPushButton(f"Insert an empty cell ({EMPTY_CELL})")
        empty.clicked.connect(lambda: self.rows.insertPlainText(EMPTY_CELL))
        self.widths = QTableWidget(0, 2)
        self.widths.setHorizontalHeaderLabels(["Glyph", "Width"])
        self.widths.horizontalHeader().setStretchLastSection(True)
        self.widths.setFixedHeight(120)
        add_width, remove_width = QPushButton("Add width"), QPushButton("Remove width")
        add_width.clicked.connect(self._add_width)
        remove_width.clicked.connect(self._remove_width)
        width_buttons = QHBoxLayout()
        width_buttons.addWidget(add_width)
        width_buttons.addWidget(remove_width)
        width_buttons.addStretch(1)
        self.sample = QLineEdit(SAMPLE)
        self.sheet_view = QLabel()
        self.sheet_view.setObjectName("BitmapFontSheet")
        self.sheet_view.setAlignment(Qt.AlignLeft | Qt.AlignTop)
        sheet_scroll = QScrollArea()
        sheet_scroll.setWidget(self.sheet_view)
        sheet_scroll.setWidgetResizable(True)
        sheet_scroll.setMinimumHeight(220)
        self.sample_view = QLabel()
        self.sample_view.setObjectName("BitmapFontSample")
        self.sample_view.setMinimumHeight(48)
        self.sample_view.setStyleSheet("background: #1d2233;")
        self.status = QLabel()
        self.status.setWordWrap(True)
        form = QFormLayout()
        form.addRow("Font id", self.font_id)
        form.addRow("Picture", self.image)
        cells = QHBoxLayout()
        for name, box in (("w", self.cell_w), ("h", self.cell_h)):
            cells.addWidget(QLabel(name))
            cells.addWidget(box, 1)
        form.addRow("Cell size", cells)
        form.addRow("Colours", self.colours)
        form.addRow("Space between glyphs", self.spacing)
        form.addRow("Space character width", self.space)
        form.addRow("Line height", self.line)
        form.addRow("Pixel scale", self.scale)
        form.addRow(self.fixed)
        form.addRow("Characters (one line per row)", self.rows)
        form.addRow(empty)
        form.addRow("Width of single characters", self.widths)
        form.addRow(width_buttons)
        form.addRow("Sample words", self.sample)
        editor = QWidget()
        editor.setLayout(form)
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setWidget(editor)
        editor_scroll.setMinimumWidth(420)
        preview = QVBoxLayout()
        preview.addWidget(QLabel("The picture cut into cells"))
        preview.addWidget(sheet_scroll, 1)
        preview.addWidget(QLabel("As the game draws it"))
        preview.addWidget(self.sample_view)
        preview.addWidget(self.status)
        self.editor = QWidget()
        body = QHBoxLayout(self.editor)
        body.setContentsMargins(0, 0, 0, 0)
        body.addWidget(editor_scroll, 1)
        body.addLayout(preview, 1)
        top = QHBoxLayout()
        top.addLayout(left)
        top.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addLayout(top, 1)
        layout.addWidget(buttons)
        for box in (self.cell_w, self.cell_h, self.spacing, self.space, self.line, self.scale):
            box.valueChanged.connect(self._edited)
        self.colours.currentIndexChanged.connect(self._edited)
        self.fixed.toggled.connect(self._edited)
        self.rows.textChanged.connect(self._edited)
        self.image.changed.connect(self._edited)
        self.widths.itemChanged.connect(self._edited)
        self.sample.textChanged.connect(self._preview)
        self.font_id.editingFinished.connect(self._renamed)
        self.list.currentTextChanged.connect(self._chosen)
        self._fill_list()

    # --- the list -----------------------------------------------------------------------
    def _fill_list(self, current=None):
        self.list.blockSignals(True)
        self.list.clear()
        for font_id in sorted(self.work):
            self.list.addItem(font_id)
        self.list.blockSignals(False)
        ids = sorted(self.work)
        pick = current if current in self.work else (ids[0] if ids else "")
        if pick:
            self.list.setCurrentRow(ids.index(pick))
        self._chosen(pick)

    def _chosen(self, font_id):
        self.current = font_id or ""
        self.editor.setEnabled(bool(self.current))
        if self.current:
            self._load(self.work[self.current])
        else:
            self.status.setText("Add a font, choose its picture and type its characters.")

    def _add(self):
        name, ok = QInputDialog.getText(self, "Add font", "Font id")
        name = str(name).strip()
        if not ok or not name:
            return
        if name in self.work:
            QMessageBox.information(self, "Add font", f"There is already a font {name}.")
            return
        self.work[name] = MenuBitmapFont(name)
        self.names[name] = None
        self._fill_list(name)

    def _remove(self):
        if not self.current:
            return
        self.work.pop(self.current, None)
        self.names.pop(self.current, None)
        self._fill_list()

    def _renamed(self):
        new = self.font_id.text().strip()
        old = self.current
        if not old or not new or new == old:
            self.font_id.setText(old)
            return
        if new in self.work:
            QMessageBox.information(self, "Font id", f"There is already a font {new}.")
            self.font_id.setText(old)
            return
        self.work[new] = replace(self.work.pop(old), font_id=new)
        self.names[new] = self.names.pop(old)
        self._fill_list(new)

    # --- one font -----------------------------------------------------------------------
    def _load(self, spec):
        self._loading = True
        self.font_id.setText(spec.font_id)
        self.image.setText(spec.image)
        self.cell_w.setValue(spec.cell_width)
        self.cell_h.setValue(spec.cell_height)
        self.colours.setCurrentIndex(max(0, self.colours.findData(spec.colours)))
        self.spacing.setValue(spec.spacing)
        self.space.setValue(spec.space_width)
        self.line.setValue(spec.line)
        self.scale.setValue(spec.scale)
        self.fixed.setChecked(spec.fixed_width)
        self.rows.setPlainText("\n".join(spec.rows))
        self.widths.setRowCount(0)
        for char, width in spec.widths:
            self._width_row(char, width)
        self._loading = False
        self._preview()

    def _width_row(self, char="", width=0):
        row = self.widths.rowCount()
        self.widths.insertRow(row)
        self.widths.setItem(row, 0, QTableWidgetItem(char))
        self.widths.setItem(row, 1, QTableWidgetItem(str(width)))

    def _add_width(self):
        self._width_row("A", self.cell_w.value())
        self._edited()

    def _remove_width(self):
        row = self.widths.currentRow()
        if row >= 0:
            self.widths.removeRow(row)
            self._edited()

    def spec(self):
        """The chosen font as the fields now say."""
        widths = []
        for row in range(self.widths.rowCount()):
            char = (self.widths.item(row, 0) or QTableWidgetItem("")).text()[:1]
            try:
                width = int((self.widths.item(row, 1) or QTableWidgetItem("0")).text())
            except ValueError:
                continue
            if char:
                widths.append((char, width))
        return MenuBitmapFont(
            self.current,
            image=self.image.text(),
            cell_width=self.cell_w.value(),
            cell_height=self.cell_h.value(),
            rows=tuple(self.rows.toPlainText().split("\n")),
            spacing=self.spacing.value(),
            space_width=self.space.value(),
            line=self.line.value(),
            fixed_width=self.fixed.isChecked(),
            widths=tuple(widths),
            colours=self.colours.currentData(),
            scale=self.scale.value(),
        )

    def _edited(self, *_):
        if self._loading or not self.current:
            return
        rows = tuple(self.rows.toPlainText().split("\n"))
        while rows and not rows[-1]:
            rows = rows[:-1]
        self.work[self.current] = replace(self.spec(), rows=rows)
        self._preview()

    def _preview(self, *_):
        spec = self.work.get(self.current)
        if spec is None:
            return
        font = sheet_font(self.document, spec)
        if font is None:
            self.sheet_view.setText("Choose the font's picture.")
            self.sample_view.clear()
            self.status.setText("")
            return
        self.sheet_view.setPixmap(self._cut_sheet(spec, font))
        self.sample_view.setPixmap(QPixmap.fromImage(font_image(font, self.sample.text())))
        missing = sorted({c for c in self.sample.text() if c not in font.cells and c != " "})
        cells = len(font.cells)
        self.status.setText(
            f"{cells} characters"
            + (f"  ·  not in the font: {''.join(missing)}" if missing else "")
        )

    def _cut_sheet(self, spec, font):
        """The picture enlarged, its cells outlined, each one's character in its corner."""
        import pygame

        sheet = font.sheet
        width, height = sheet.get_size()
        data = pygame.image.tobytes(sheet, "RGBA")
        image = QImage(data, width, height, width * 4, QImage.Format_RGBA8888).copy()
        scale = max(1, min(6, 560 // max(1, width)))
        big = QPixmap.fromImage(image).scaled(width * scale, height * scale)
        canvas = QPixmap(big.size())
        canvas.fill(QColor(40, 44, 60))
        painter = QPainter(canvas)
        painter.drawPixmap(0, 0, big)
        painter.setPen(QPen(QColor(120, 200, 255, 120), 1))
        cw, ch = spec.cell_width * scale, spec.cell_height * scale
        for x in range(0, canvas.width() + 1, cw):
            painter.drawLine(x, 0, x, canvas.height())
        for y in range(0, canvas.height() + 1, ch):
            painter.drawLine(0, y, canvas.width(), y)
        label = QFont()
        label.setPixelSize(max(8, min(12, ch // 3)))
        painter.setFont(label)
        painter.setPen(QColor(255, 210, 90))
        for char, (column, row) in font.cells.items():
            painter.drawText(column * cw + 2, row * ch + label.pixelSize(), char)
        painter.end()
        return canvas

    # --- the result ---------------------------------------------------------------------
    def _accept(self):
        self.accept()

    def fonts(self):
        """``[(font, old id or None)]`` for every font that is new or changed."""
        out = []
        for font_id, spec in sorted(self.work.items()):
            old = self.names.get(font_id)
            if old is None or self.original.get(old) != spec:
                out.append((spec, old))
        return out

    def removed(self):
        """The ids of the fonts taken out (renamed ones are not among them)."""
        kept = {v for v in self.names.values() if v}
        return [k for k in self.original if k not in kept]


__all__ = ["BitmapFontDialog", "font_image", "sheet_font"]
