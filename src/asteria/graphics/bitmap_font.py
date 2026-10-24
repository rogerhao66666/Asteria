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


__all__ = ["BitmapFont"]
