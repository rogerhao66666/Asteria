"""Bitmap fonts: a sheet of fixed cells, each glyph drawn in two tones, with a width per glyph.

A font is described by a JSON file beside its sheet::

    {"image": "font.png", "cell": 16, "columns": 16, "line": 16,
     "widths": [3, 6, 6, ...], "chars": {"A": 187, "é": 27, ...}}

``chars`` maps a character to its cell index (cells run left to right, top to bottom);
``widths[index]`` is how far the pen moves after that glyph. In the sheet a glyph's letter is
white (255, 255, 255) and its shadow grey (128, 128, 128); everything else is see-through, so
one sheet draws text in any colour with any shadow colour. Characters the font lacks are
reported by ``covers`` so the caller can draw that text another way (a system face for
Chinese).
"""

from __future__ import annotations

import json
from pathlib import Path

LETTER, SHADOW = (255, 255, 255), (128, 128, 128)


class BitmapFont:
    def __init__(self, pg, path):
        self.pg = pg
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.cell = int(data.get("cell", 16))
        self.columns = int(data.get("columns", 16))
        self.line = int(data.get("line", self.cell))
        self.widths = [int(x) for x in data.get("widths", ())]
        self.chars = {str(k): int(v) for k, v in dict(data.get("chars", {})).items()}
        self.sheet = pg.image.load(str(path.parent / data["image"]))
        self._tinted = {}

    def covers(self, text):
        """Whether every character of ``text`` is in the font (line breaks aside)."""
        return all(c in self.chars or c == "\n" for c in str(text))

    def width(self, text):
        return sum(self._advance(c) for c in str(text))

    def _advance(self, char):
        index = self.chars.get(char)
        if index is None:
            return 0
        return self.widths[index] if index < len(self.widths) else self.cell // 2

    def _sheet(self, colour, shadow):
        key = (tuple(colour), None if shadow is None else tuple(shadow))
        sheet = self._tinted.get(key)
        if sheet is None:
            pg = self.pg
            sheet = self.sheet.convert_alpha() if pg.display.get_surface() else self.sheet.copy()
            pixels = pg.PixelArray(sheet)
            pixels.replace(LETTER, tuple(colour))
            if shadow is None:
                pixels.replace(SHADOW, (0, 0, 0, 0))
            else:
                pixels.replace(SHADOW, tuple(shadow))
            del pixels
            self._tinted[key] = sheet
        return sheet

    def render(self, surface, text, x, y, colour, shadow=None):
        """Draw ``text`` with its top-left at ``(x, y)``; returns the pen's end x."""
        sheet = self._sheet(colour, shadow)
        pen = int(x)
        for char in str(text):
            index = self.chars.get(char)
            if index is None:
                continue
            area = (
                index % self.columns * self.cell,
                index // self.columns * self.cell,
                self.cell,
                self.cell,
            )
            surface.blit(sheet, (pen, int(y)), area)
            pen += self._advance(char)
        return pen


class SheetFont:
    """A bitmap font set up in the editor (``presentation.menu_layout.MenuBitmapFont``): the
    picture ``sheet`` cut into cells, each cell's character typed in the editor."""

    def __init__(self, pg, spec, sheet):
        self.pg, self.spec, self.sheet = pg, spec, sheet
        self.cell_w, self.cell_h = spec.cell_width, spec.cell_height
        self.line = spec.line or spec.cell_height
        self.cells = spec.cells()
        own = dict(spec.widths)
        self.widths = {}
        for char, (column, row) in self.cells.items():
            if char in own:
                self.widths[char] = own[char]
            elif spec.fixed_width:
                self.widths[char] = self.cell_w + spec.spacing
            else:
                self.widths[char] = self._measure(column, row) + spec.spacing
        self.widths.setdefault(" ", own.get(" ", spec.space_width or max(1, self.cell_w // 2)))
        self._sheets = {}

    def _measure(self, column, row):
        """How wide the glyph in a cell is drawn: up to its rightmost visible pixel."""
        area = self.pg.Rect(column * self.cell_w, row * self.cell_h, self.cell_w, self.cell_h)
        area = area.clip(self.sheet.get_rect())
        if area.width <= 0 or area.height <= 0:
            return 0
        bounds = self.sheet.subsurface(area).get_bounding_rect()
        return bounds.right if bounds.width else self.cell_w // 2

    def covers(self, text):
        return all(c in self.cells or c in " \n" for c in str(text))

    def scale_for(self, size):
        """The whole-pixel scale text ``size`` pixels tall is drawn at."""
        if self.spec.scale:
            return self.spec.scale
        return max(1, round(int(size) / max(1, self.line)))

    def width(self, text, scale=1):
        return sum(self.widths.get(c, 0) for c in str(text)) * scale

    def _tinted(self, colour, shadow, scale):
        key = (tuple(colour), None if shadow is None else tuple(shadow), scale)
        sheet = self._sheets.get(key)
        if sheet is not None:
            return sheet
        pg = self.pg
        sheet = self.sheet.copy()
        mode = self.spec.colours
        if mode == "tint":
            sheet.fill((0, 0, 0, 255), special_flags=pg.BLEND_RGBA_MULT)
            sheet.fill((*tuple(colour)[:3], 0), special_flags=pg.BLEND_RGBA_ADD)
        elif mode == "two_tone":
            pixels = pg.PixelArray(sheet)
            pixels.replace(LETTER, tuple(colour))
            pixels.replace(SHADOW, (0, 0, 0, 0) if shadow is None else tuple(shadow))
            del pixels
        if scale > 1:
            w, h = sheet.get_size()
            sheet = pg.transform.scale(sheet, (w * scale, h * scale))
        if len(self._sheets) > 64:
            self._sheets.clear()
        self._sheets[key] = sheet
        return sheet

    def render(self, surface, text, x, y, colour, shadow=None, scale=1):
        """Draw ``text`` (one line) with its top-left at ``(x, y)``; returns the pen's end x."""
        sheet = self._tinted(colour, shadow, scale)
        pen = int(x)
        cw, ch = self.cell_w * scale, self.cell_h * scale
        for char in str(text):
            cell = self.cells.get(char)
            if cell is not None:
                surface.blit(sheet, (pen, int(y)), (cell[0] * cw, cell[1] * ch, cw, ch))
            pen += self.widths.get(char, 0) * scale
        return pen

    def surface(self, text, colour, shadow=None, scale=1):
        """``text`` drawn on a see-through surface of its own size (one line)."""
        width = max(1, self.width(text, scale))
        out = self.pg.Surface((width, self.line * scale), self.pg.SRCALPHA)
        self.render(out, text, 0, 0, colour, shadow, scale)
        return out


def spec_from_legacy(data, image, font_id):
    """A ``MenuBitmapFont`` from an old font JSON (``chars`` and ``widths`` by cell index):
    how the editor turns a manifest's font into one it can edit."""
    from asteria.presentation.menu_layout import EMPTY_CELL, MenuBitmapFont

    cell, columns = int(data.get("cell", 16)), int(data.get("columns", 16))
    by_index = {}
    for char, index in dict(data.get("chars", {})).items():
        by_index.setdefault(int(index), str(char))
    count = max(by_index, default=-1) + 1
    rows = []
    for start in range(0, count, columns):
        row = "".join(by_index.get(i, EMPTY_CELL) for i in range(start, start + columns))
        rows.append(row.rstrip(EMPTY_CELL))
    widths = list(data.get("widths", ()))
    # the old font moved half a cell past a glyph it gave no width
    own = {c: int(widths[i]) if i < len(widths) else cell // 2 for i, c in by_index.items()}
    return MenuBitmapFont(
        font_id,
        image=image,
        cell_width=cell,
        cell_height=cell,
        rows=tuple(rows),
        spacing=0,
        line=int(data.get("line", cell)),
        widths=tuple(sorted(own.items())),
        colours="two_tone",
        scale=1,
    )


__all__ = ["BitmapFont", "SheetFont", "spec_from_legacy"]
