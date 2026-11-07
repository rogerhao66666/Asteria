"""What a picture command puts on the screen, drawn by the rules the game draws it with
(``runtime/playtest/field_ui.py``): its cell or its words, the scroll and the wave, the tint, and
how it blends in. Silent, and its clock only runs while it can be seen.
"""

from __future__ import annotations

import math
import weakref
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QRectF, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetrics, QImage, QPainter, QPen
from PySide6.QtWidgets import QWidget

from asteria.editor.scene.render import resolve_texture_source

TICK_MS = 33
WHITE = (255, 255, 255)
LETTER, SHADOW = QColor(*WHITE).rgb(), QColor(128, 128, 128).rgb()
SYSTEM_LINE = 16  # the height of a line in the face the game falls back on


def parse_rgb(text, default=None):
    """``"r,g,b"`` as three numbers; ``default`` when it isn't one."""
    parts = str(text or "").split(",")
    try:
        rgb = tuple(max(0, min(255, int(float(part)))) for part in parts)
    except ValueError:
        return default
    return rgb if len(rgb) == 3 else default


def cycled_frame(frame, rate, cells, loop, age):
    """The cell a sheet shows now: on from ``frame``, a cell every 1 / ``rate`` seconds."""
    if rate <= 0:
        return frame
    step = frame + int(age * rate + 1e-9)
    return step % max(1, cells) if loop else min(step, max(1, cells) - 1)


def tinted(image, amount, color):
    """Colour x (1 - amount) + ``color`` x amount; its see-through stays see-through."""
    if amount <= 0:
        return image
    out = image.convertToFormat(QImage.Format_ARGB32_Premultiplied)
    painter = QPainter(out)
    painter.setCompositionMode(QPainter.CompositionMode_SourceAtop)
    painter.setOpacity(amount)
    painter.fillRect(out.rect(), QColor(*color))
    painter.end()
    return out


def moved(image, shift, wave, age):
    """Its content scrolled by ``shift`` (wrapping round), its rows waved: ``wave`` is
    (amplitude, length, speed), all at the image's own pixels."""
    amplitude, length, speed = wave
    width, height = image.width(), image.height()
    across, down = round(shift[0]) % width, round(shift[1]) % height
    if not (across or down or amplitude):
        return image
    rolled = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    rolled.fill(0)
    painter = QPainter(rolled)
    for x in (across - width, across):
        for y in (down - height, down):
            painter.drawImage(QPoint(x, y), image)
    painter.end()
    if not amplitude:
        return rolled
    waved = QImage(image.size(), QImage.Format_ARGB32_Premultiplied)
    waved.fill(0)
    painter = QPainter(waved)
    for row in range(height):
        phase = (row + speed * age) / max(1e-6, length)
        offset = round(amplitude * math.sin(2 * math.pi * phase)) % width
        strip = QRect(0, row, width, 1)
        painter.drawImage(QPoint(offset, row), rolled, strip)
        painter.drawImage(QPoint(offset - width, row), rolled, strip)
    painter.end()
    return waved


def system_words(lines, color, shadow):
    """Words in a plain face, for a font that's missing or lacks a character."""
    font = QFont()
    font.setPixelSize(SYSTEM_LINE - 2)
    metrics = QFontMetrics(font)
    width = max(1, max(metrics.horizontalAdvance(line) for line in lines)) + 1
    image = QImage(width, SYSTEM_LINE * len(lines) + 1, QImage.Format_ARGB32_Premultiplied)
    image.fill(0)
    painter = QPainter(image)
    painter.setFont(font)
    for row, line in enumerate(lines):
        y = row * SYSTEM_LINE + metrics.ascent()
        if shadow is not None:
            painter.setPen(QColor(*shadow))
            painter.drawText(1, y + 1, line)
        painter.setPen(QColor(*color))
        painter.drawText(0, y, line)
    painter.end()
    return image


class SheetWords:
    """A project's bitmap font drawn in Qt, the way ``graphics.bitmap_font.SheetFont`` draws it
    in the game."""

    def __init__(self, spec, sheet):
        self.spec = spec
        self.sheet = sheet.convertToFormat(QImage.Format_ARGB32)
        self.cells = spec.cells()
        own = dict(spec.widths)
        self.widths = {}
        for char, (column, row) in self.cells.items():
            if char in own:
                self.widths[char] = own[char]
            elif spec.fixed_width:
                self.widths[char] = spec.cell_width + spec.spacing
            else:
                self.widths[char] = self._measure(column, row) + spec.spacing
        self.widths.setdefault(" ", own.get(" ", spec.space_width or max(1, spec.cell_width // 2)))
        self._colored = {}

    def _measure(self, column, row):
        left, top = column * self.spec.cell_width, row * self.spec.cell_height
        for x in range(self.spec.cell_width - 1, -1, -1):
            for y in range(self.spec.cell_height):
                if self._visible(left + x, top + y):
                    return x + 1
        return self.spec.cell_width // 2

    def _visible(self, x, y):
        return self.sheet.valid(x, y) and self.sheet.pixelColor(x, y).alpha() > 0

    def covers(self, lines):
        return all(char in self.cells or char == " " for line in lines for char in line)

    def _in_colors(self, color, shadow):
        key = (color, shadow)
        if key in self._colored:
            return self._colored[key]
        mode = self.spec.colours
        if mode == "keep":
            sheet = self.sheet
        elif mode == "tint":
            sheet = tinted(self.sheet, 1.0, color)
        else:  # two_tone: white takes the colour, mid grey the shadow (or nothing)
            sheet = self.sheet.copy()
            ink = QColor(*color).rgb()
            under = 0 if shadow is None else QColor(*shadow).rgb()
            for y in range(sheet.height()):
                for x in range(sheet.width()):
                    pixel = sheet.pixel(x, y)
                    if pixel == LETTER:
                        sheet.setPixel(x, y, ink)
                    elif pixel == SHADOW:
                        sheet.setPixel(x, y, under)
        self._colored[key] = sheet
        return sheet

    def words(self, lines, color, shadow):
        spec = self.spec
        step = spec.line or spec.cell_height
        widest = max(sum(self.widths.get(char, 0) for char in line) for line in lines)
        image = QImage(max(1, widest), step * len(lines), QImage.Format_ARGB32_Premultiplied)
        image.fill(0)
        sheet = self._in_colors(color, shadow)
        painter = QPainter(image)
        for row, line in enumerate(lines):
            pen = 0
            for char in line:
                cell = self.cells.get(char)
                if cell is not None:
                    area = QRect(
                        cell[0] * spec.cell_width,
                        cell[1] * spec.cell_height,
                        spec.cell_width,
                        spec.cell_height,
                    )
                    painter.drawImage(QPoint(pen, row * step), sheet, area)
                pen += self.widths.get(char, 0)
        painter.end()
        return image


def sheet_words(document, spec):
    """``spec`` ready to draw, or None while its picture can't be found."""
    if spec is None or not spec.image:
        return None
    path = resolve_texture_source(document, spec.image)
    if path is None and document.file_path is not None:
        path = Path(document.file_path).parent / spec.image
    sheet = QImage(str(path)) if path is not None else QImage()
    return None if sheet.isNull() else SheetWords(spec, sheet)


class PicturePreview(QWidget):
    def __init__(self, owner):
        super().__init__()
        # a weak reference: the owner holds this widget, and a cycle between a widget and
        # the window it sits in crashed PySide6 6.12's garbage collection (a segfault)
        self._owner = weakref.ref(owner)
        self.setMinimumSize(280, 180)
        self.age = 0.0
        self._clock = QTimer(self)
        self._clock.setInterval(TICK_MS)
        self._clock.timeout.connect(self._tick)

    @property
    def owner(self):
        return self._owner()

    def refresh(self, *_args):
        self.update()

    def _tick(self):
        if self.owner.moves():
            self.age += TICK_MS / 1000
            self.update()

    def showEvent(self, event):  # noqa: N802 - Qt API
        super().showEvent(event)
        self._clock.start()

    def hideEvent(self, event):  # noqa: N802 - Qt API
        super().hideEvent(event)
        self._clock.stop()

    def paintEvent(self, event):  # noqa: N802 - Qt API
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(24, 26, 30))
        owner = self.owner
        stage = owner.stage_size
        scale = min(self.width() / stage[0], self.height() / stage[1])
        stage_w, stage_h = stage[0] * scale, stage[1] * scale
        ox, oy = (self.width() - stage_w) / 2, (self.height() - stage_h) / 2
        area = QRectF(ox, oy, stage_w, stage_h)
        painter.fillRect(area, QColor(52, 56, 66))  # not black: an added glow has to show
        painter.setPen(QPen(QColor(78, 82, 92), 1))
        painter.drawRect(area)
        painter.setClipRect(area)
        x = ox + owner.x.value() * scale
        y = oy + owner.y.value() * scale
        image, is_words = owner.picture_image(self.age)
        if image is None:
            painter.setPen(QPen(QColor(105, 220, 210), 1))
            painter.drawRect(QRectF(x, y, 36 * scale, 24 * scale))
            painter.drawText(int(x) + 4, int(y + 16 * scale), owner.picture_id.text())
            return
        width = image.width() * owner.picture_scale.value() * scale
        height = image.height() * owner.picture_scale.value() * scale
        if is_words:  # words: their x is their left, right end or middle
            x -= {"right": width, "center": width / 2}.get(owner.text_align.text(), 0)
        painter.setOpacity(owner.opacity.value())
        if owner.adds_light():
            painter.setCompositionMode(QPainter.CompositionMode_Plus)
        painter.drawImage(QRectF(x, y, max(1.0, width), max(1.0, height)), image)


__all__ = [
    "WHITE",
    "PicturePreview",
    "cycled_frame",
    "moved",
    "parse_rgb",
    "sheet_words",
    "system_words",
    "tinted",
]
