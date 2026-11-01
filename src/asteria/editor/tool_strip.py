"""The tool strip floating over the Scene canvas: one column of tools (select, paint, fill,
rectangle, erase, then the terrain, region and doodad brushes), each with its key in the corner.
It is a child of the viewport, pinned to its top-left corner, and mirrors the tile palette's
mode: clicking a tool is the same as pressing its key over the map.
"""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QFrame, QVBoxLayout

from .icons import icon
from .panel_switch import KeyedButton

# (mode name, drawing, key, tool tip)
TOOLS = (
    ("select", "tool_select", "S", "Select (S)"),
    ("paint", "tool_paint", "B", "Paint (B)"),
    ("fill", "tool_fill", "G", "Fill (G)"),
    ("rectangle", "tool_rect", "R", "Rectangle (R)"),
    ("erase", "tool_erase", "E", "Erase (E)"),
    None,  # a rule between the tools and the brushes
    ("terrain", "terrain", "", "Terrain"),
    ("region", "region", "", "Region"),
    ("doodad", "doodad", "", "Doodad"),
    None,
    # a character: pick a walking sheet, carry its picture to a cell, and the actor, its
    # animations and its entity are made in one step (the shell's place_character_from_sheet)
    ("character", "entity", "N", "Place Character from Sprite Sheet… (N)"),
)
MARGIN = 12


class ToolStrip(QFrame):
    def __init__(self, viewport, palette, on_character=None):
        super().__init__(viewport)
        self.setObjectName("ToolStrip")
        self.palette_ref = palette
        self.on_character = on_character
        column = QVBoxLayout(self)
        column.setContentsMargins(4, 4, 4, 4)
        column.setSpacing(2)
        self.buttons = {}
        for tool in TOOLS:
            if tool is None:
                rule = QFrame(self)
                rule.setObjectName("ToolStripRule")
                rule.setFixedHeight(1)
                column.addWidget(rule)
                continue
            mode, drawing, key, words = tool
            button = KeyedButton(key, self)
            button.setObjectName("ToolStripButton")
            button.setCheckable(True)
            button.setFixedSize(32, 32)
            button.setIconSize(QSize(16, 16))
            button.setIcon(icon(drawing, "#d4d6dd"))
            button.setToolTip(words)
            if mode == "character":
                button.clicked.connect(lambda checked=False: self._character())
            else:
                button.clicked.connect(lambda checked=False, m=mode: palette.handle_tool_key(m))
            column.addWidget(button)
            self.buttons[mode] = button
        palette.modeChanged.connect(self.sync)
        self.sync("select")
        self.move(MARGIN, MARGIN)
        self.adjustSize()
        self.raise_()

    def _character(self):
        if self.on_character is not None:
            self.on_character()
        viewport = self.parent()
        if not getattr(viewport, "character_placement_active", False):  # nothing to place
            self.sync(getattr(getattr(viewport, "tile_tools", None), "mode", "select"))

    def sync(self, mode):
        for name, button in self.buttons.items():
            button.setChecked(name == mode)
