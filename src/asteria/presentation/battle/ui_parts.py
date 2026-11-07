"""The battle UI's draw records (panels, texts, gauges, icons) and the sizes and helpers its
parts share."""

from __future__ import annotations

from dataclasses import dataclass, fields

from asteria.presentation.battle.action_menu import BattleActionMenuView
from asteria.presentation.text.cells import cells

# what the command menu's layout reads: every field of the menu view but its revision count
# (the adapter sets the same entries again each frame, and each set counts)
_MENU_LAYOUT_FIELDS = tuple(f.name for f in fields(BattleActionMenuView) if f.name != "revision")


BAR_MIN = 24.0  # the narrowest a card's bars get to make room for its portrait


BOTTOM_ROW_HEIGHT = 24.0  # a bottom-row party cell without a portrait


def _value_text(value):
    """A floating number: whole from 10 up (a share of health is not 604.444, a million is
    not 1e+06), as written below that (a 0.5 gauge step)."""
    return str(round(value)) if abs(value) >= 10 else f"{value:g}"


@dataclass(frozen=True, slots=True)
class BattleUiText:
    text: str
    x: float
    y: float
    role: str = "body"
    align: str = "left"
    member_id: str = ""
    color: tuple | None = None  # a battle layout's (V4) colour; None: the theme's
    size: int = 0  # a battle layout's text size; 0: the theme's


@dataclass(frozen=True, slots=True)
class BattleUiPanel:
    panel_id: str
    x: float
    y: float
    width: float
    height: float
    role: str = "panel"
    member_id: str = ""
    skin: object = None  # a battle layout's (V4) nine-patch; None: the theme's, False: none
    fill: tuple | None = None
    border: tuple | None = None


@dataclass(frozen=True, slots=True)
class BattleUiGaugeBar:
    member_id: str
    resource_id: str
    label: str
    x: float
    y: float
    width: float
    height: float
    normalized: float
    current: float
    maximum: float
    presentation: str = "bar"
    segments: int = 0
    icon_asset_id: str | None = None
    color: str = ""  # "#rrggbb" fill; empty: the theme's


@dataclass(frozen=True, slots=True)
class BattleUiIcon:
    asset_id: str
    x: float
    y: float
    role: str
    member_id: str = ""
    label: str = ""


MARK_ROLE = ":mark"  # a row's cursor or tick, drawn by the backend level with its label


MENU_COST_GAP = 4.0  # layout units kept between a menu row's name and its cost


def _mark_gutter(*prefixes):
    """Room before a row's label for its mark, in layout units: the widest mark and a small gap
    (what its trailing spaces gave before). Every row's label starts at the same place, marked
    or not."""
    widest = max(len(p.strip()) for p in prefixes)
    return widest * 3.8 + 2.0 if widest else 0.0


def _gap(a, b):
    """How far apart two ``(x, y, w, h)`` boxes are (0 when they touch or overlap)."""
    dx = max(b[0] - (a[0] + a[2]), a[0] - (b[0] + b[2]), 0.0)
    dy = max(b[1] - (a[1] + a[3]), a[1] - (b[1] + b[3]), 0.0)
    return max(dx, dy)


def _category_strip(categories, active, room, shown_as=None):
    """``Attack  [Skills]  Combo`` within ``room`` layout units: the active category and as
    many of its neighbours as fit, ``‹`` / ``›`` where more lie past the edge (the whole row ran
    out of the menu, under the panels beside it). ``shown_as`` maps a category (an id) to the
    name drawn for it."""
    at = list(categories).index(active) if active in categories else 0
    names = [(shown_as or {}).get(c, c) for c in categories]

    def text(lo, hi):
        shown = "  ".join(f"[{v}]" if i == at else v for i, v in enumerate(names) if lo <= i < hi)
        return ("< " if lo > 0 else "") + shown + (" >" if hi < len(names) else "")

    lo, hi = at, at + 1
    while True:
        grown = False
        for candidate in ((lo, hi + 1), (lo - 1, hi)):  # the next one first, then the one before
            a, b = candidate
            if 0 <= a and b <= len(names) and cells(text(a, b)) * 3.8 <= room:
                lo, hi, grown = a, b, True
        if not grown:
            return text(lo, hi)


def _marked(prefix, label, left, gutter, y, role):
    """A row's label and, apart from it, its mark (``▶``, ``✓``...): the backend draws the mark
    centred on the label's letters, whatever font each is drawn in (a symbol the pixel font
    lacked came from another font and sat crooked beside the name)."""
    texts = []
    mark = prefix.strip()
    if mark:
        texts.append(BattleUiText(mark, left, y, role + MARK_ROLE, "left"))
    texts.append(BattleUiText(label, left + gutter, y, role, "left"))
    return texts
