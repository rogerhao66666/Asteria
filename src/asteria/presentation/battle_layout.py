"""The battle screen's layout (V4): the ``battle`` screen of ``menu_layout`` applied to the
commands the composer laid out (``battle_ui.BattleUiComposer``).

The composer keeps placing everything as before - the party HUD, the overhead bars, the
command menu with its skill and item pages, the help box, the step lists, the turn timeline,
the damage numbers, the target cursor, the result panel - from ``BattleUiLayoutProfile``. A
``battle`` layout then works on each of those groups as a whole, in the battle's own
coordinates (the profile's virtual size, 320 x 180 by default):

- ``rect`` moves the group (x, y: where its top-left corner goes, from ``anchor``); a width
  and height scale it to that size, 0 keeps the engine's size;
- ``visible`` hides it;
- a nine-patch, picture or fill / border colours reskin its panels, ``selection_skin`` /
  ``selection_fill`` the chosen row's frame, ``color`` / ``size`` its words;
- the author's own elements (``extra.``) add pictures, panels and words.

One card of the party HUD or one set of overhead bars can be placed on its own as well:
``party_hud.1`` is the first party member's card, ``party_hud.2`` the second (in the order the
composer drew them), ``overhead.1``... the bars over the heads. Such an element moves, scales,
restyles or hides that card after its group was laid out.

Without a ``battle`` layout nothing here runs: the frame is the composer's, untouched.
"""

from __future__ import annotations

from dataclasses import replace

from .menu_layout import resolve_rect
from .ui_skin import NinePatch

PER_MEMBER = ("party_hud", "overhead")  # groups whose cards can be placed one by one
GROUPS = (
    "party_hud",
    "overhead",
    "menu",
    "help",
    "workflow",
    "timeline",
    "numbers",
    "result",
    "target",
)


def _bounds(items):
    """``(x, y, w, h)`` around panels, gauges and portraits (texts and icons: their points)."""
    xs, ys, xe, ye = [], [], [], []
    for kind, item in items:
        if kind in ("panel", "gauge", "portrait"):
            xs.append(item.x)
            ys.append(item.y)
            xe.append(item.x + item.width)
            ye.append(item.y + item.height)
    if not xs:
        for kind, item in items:
            if kind in ("text", "icon", "marker"):
                xs.append(item.x)
                ys.append(item.y)
                xe.append(item.x)
                ye.append(item.y)
    if not xs:
        return None
    x, y = min(xs), min(ys)
    return (x, y, max(xe) - x, max(ye) - y)


def _look(element, panel):
    """A panel with the element's skin, picture or colours (the chosen row: its selection
    look)."""
    if panel.role == "button:selected":
        skin, fill, border = element.selection_skin, element.selection_fill, None
    elif str(panel.role).startswith("button"):
        return panel  # the other rows stay see-through
    else:
        skin, fill, border = element.skin, element.fill, element.border
        if skin is None and element.image:
            skin = NinePatch(element.image, 0, 0, 0, 0)  # a picture stretched over it
    if skin is None and fill is None and border is None:
        return panel
    # the author's colours replace the theme's picture too (False: no nine-patch)
    return replace(panel, skin=skin if skin is not None else False, fill=fill, border=border)


class BattleScreenLayout:
    """Applies one ``battle`` ``MenuLayout`` to a composed frame's command lists."""

    def __init__(self, layout, size, translate=None):
        self.layout = layout
        self.size = tuple(size)
        self.translate = translate
        self.boxes = {}  # group -> its rectangle after the layout (battle coordinates)

    def apply(self, lists, tags):
        """``lists``: ``{kind: [commands]}`` (panel, text, gauge, icon, portrait, marker);
        ``tags``: ``{kind: [group of each command]}``. Returns the lists changed in place
        order (hidden groups dropped)."""
        elements = {e.element_id: e for e in self.layout.elements}
        by_group = {}
        for kind, items in lists.items():
            for item, group in zip(items, tags[kind], strict=True):
                by_group.setdefault(group, []).append((kind, item))
        moves = {}
        for group, items in by_group.items():
            box = _bounds(items)
            element = elements.get(group)
            if box is None:
                continue
            if element is None or not element.visible or element.rect is None:
                self.boxes[group] = box
                if element is not None and element.visible:
                    moves[group] = (box, box, element)
                continue
            rx, ry, rw, rh = resolve_rect(element.rect, element.anchor, self.size)
            target = (rx, ry, rw if rw > 0 else box[2], rh if rh > 0 else box[3])
            self.boxes[group] = target
            moves[group] = (box, target, element)
        out, out_tags = {}, {}
        for kind, items in lists.items():
            kept, kept_tags = [], []
            for item, group in zip(items, tags[kind], strict=True):
                element = elements.get(group)
                if element is not None and not element.visible:
                    continue
                move = moves.get(group)
                kept.append(item if move is None else self._moved(kind, item, *move))
                kept_tags.append(group)
            out[kind], out_tags[kind] = kept, kept_tags
        out = self._cards(out, out_tags, elements)
        self._extras(out)
        return out

    def _cards(self, lists, tags, elements):
        """One card of a per-member group (``party_hud.2``...) placed on its own."""
        slots = {}  # (group, member id) -> "group.n", numbered in drawing order
        counts = {}
        for kind in ("panel", "gauge", "portrait", "text", "icon"):
            for item, group in zip(lists[kind], tags[kind], strict=True):
                member = getattr(item, "member_id", "")
                if group in PER_MEMBER and member and (group, member) not in slots:
                    counts[group] = counts.get(group, 0) + 1
                    slots[(group, member)] = f"{group}.{counts[group]}"

        def slot(item, group):
            return slots.get((group, getattr(item, "member_id", "")))

        by_slot = {}
        for kind, items in lists.items():
            for item, group in zip(items, tags[kind], strict=True):
                name = slot(item, group)
                if name is not None:
                    by_slot.setdefault(name, []).append((kind, item))
        moves = {}
        for name, items in by_slot.items():
            element, box = elements.get(name), _bounds(items)
            if box is None:
                continue
            self.boxes[name] = box  # the editor outlines every card, placed or not
            if element is None or not element.visible:
                continue
            target = box
            if element.rect is not None:
                rx, ry, rw, rh = resolve_rect(element.rect, element.anchor, self.size)
                target = (rx, ry, rw if rw > 0 else box[2], rh if rh > 0 else box[3])
            self.boxes[name] = target
            moves[name] = (box, target, element)
        if not moves and not any(name in elements for name in by_slot):
            return lists  # no card placed on its own: as the groups left them
        out = {}
        for kind, items in lists.items():
            kept = []
            for item, group in zip(items, tags[kind], strict=True):
                name = slot(item, group)
                element = elements.get(name) if name else None
                if element is not None and not element.visible:
                    continue
                move = moves.get(name)
                kept.append(item if move is None else self._moved(kind, item, *move))
            out[kind] = kept
        return out

    @staticmethod
    def _moved(kind, item, box, target, element):
        bx, by, bw, bh = box
        tx, ty, tw, th = target
        sx = tw / bw if bw else 1.0
        sy = th / bh if bh else 1.0

        def x(v):
            return tx + (v - bx) * sx

        def y(v):
            return ty + (v - by) * sy

        if kind in ("panel", "gauge", "portrait"):
            item = replace(item, x=x(item.x), y=y(item.y), width=item.width * sx,
                           height=item.height * sy)  # fmt: skip
            return _look(element, item) if kind == "panel" else item
        if kind == "text":
            changes = {"x": x(item.x), "y": y(item.y)}
            if element.color is not None:
                changes["color"] = element.color
            if element.size:
                changes["size"] = element.size
            return replace(item, **changes)
        if kind == "marker":
            changes = {"x": x(item.x), "y": y(item.y)}
            if element.color is not None:
                changes["color"] = element.color
            return replace(item, **changes)
        return replace(item, x=x(item.x), y=y(item.y))  # an icon

    def _extras(self, out):
        """The author's own pictures, panels and words, under (layer < 0) or over the rest."""
        from .battle_ui import BattleUiPanel, BattleUiText

        under, over, words = [], [], []
        for element in sorted(self.layout.elements, key=lambda e: e.layer):
            if not element.extra or not element.visible or element.rect is None:
                continue
            x, y, w, h = resolve_rect(element.rect, element.anchor, self.size)
            self.boxes[element.element_id] = (x, y, w, h)
            if element.kind in ("panel", "image") or element.skin or element.image:
                skin = element.skin
                if skin is None and element.image:
                    skin = NinePatch(element.image, 0, 0, 0, 0)
                skin = False if skin is None else skin  # never a theme picture by role
                role = "layout" if element.layer < 0 else "layout:over"
                panel = BattleUiPanel(
                    element.element_id, x, y, w, h, role, "", skin, element.fill,
                    element.border,
                )  # fmt: skip
                (under if element.layer < 0 else over).append(panel)
            if element.text:
                text = element.text
                if text.startswith("key:") and self.translate is not None:
                    key, _bar, english = text[4:].partition("|")
                    text = self.translate(key.strip(), english or key.strip())
                align = element.align or "left"
                tx = x + (w / 2 if align == "center" else w if align == "right" else 0)
                role = "layout" if element.layer < 0 else "layout:over"
                words.append(
                    BattleUiText(text, tx, y, role, align, "", element.color, element.size)
                )
        out["panel"] = under + out["panel"] + over
        out["text"] = out["text"] + words


__all__ = ["GROUPS", "BattleScreenLayout"]
