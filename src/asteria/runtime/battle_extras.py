"""What turn-based battle shows on the field besides the canonical screen: each enemy's shield
(hits to Break) and weaknesses, the Break state, boost points and the chosen boost level.

Everything is laid out here first (``extras_layout``) as plain rectangles and then drawn, so a test
can check that nothing covers anything else. Enemy blocks sit *under* the sprite's feet, clear of
the name and life bar above it; hero boost points sit under the feet as well, unless the party
panel already shows them (``party_hud="side_list"`` with a boost gauge).
"""

from __future__ import annotations

from dataclasses import dataclass, field

ELEMENT_COLORS = {
    "fire": (232, 90, 50),
    "ice": (120, 200, 255),
    "lightning": (250, 220, 70),
    "light": (255, 246, 190),
    "dark": (150, 100, 200),
    "wind": (120, 230, 160),
    "earth": (190, 150, 90),
}
WEAPONS = ("sword", "spear", "dagger", "axe", "bow", "staff")


@dataclass(slots=True)
class Tile:
    kind: str  # "shield" | "weak" | "state"
    text: str
    rect: tuple  # x, y, w, h
    revealed: bool = True
    label: str = ""


@dataclass(slots=True)
class Block:
    member_id: str
    tiles: list = field(default_factory=list)
    caption: tuple | None = None  # text, x, y (state names under the tiles)

    def rect(self):
        if not self.tiles:
            return None
        x0 = min(t.rect[0] for t in self.tiles)
        y0 = min(t.rect[1] for t in self.tiles)
        x1 = max(t.rect[0] + t.rect[2] for t in self.tiles)
        y1 = max(t.rect[1] + t.rect[3] for t in self.tiles)
        if self.caption is not None:
            text, cx, cy = self.caption
            half = len(text) * 3.6  # the caption is centred under the tiles
            x0, x1 = min(x0, cx - half), max(x1, cx + half)
            y1 = max(y1, cy + 14)
        return (x0, y0, x1 - x0, y1 - y0)


def draw_glyph(pg, surface, kind, rect):
    """A small weapon / element glyph drawn with shapes inside ``rect`` (no art needed)."""
    x, y, w, h = rect
    cx, cy = x + w / 2, y + h / 2
    u = min(w, h) / 12.0
    color = ELEMENT_COLORS.get(kind, (235, 238, 245))

    def line(a, b, c=(235, 238, 245), t=2):
        pg.draw.line(
            surface,
            c,
            (cx + a[0] * u, cy + a[1] * u),
            (cx + b[0] * u, cy + b[1] * u),
            max(1, round(t * u / 1.6)),
        )

    def poly(points, c):
        pg.draw.polygon(surface, c, [(cx + px * u, cy + py * u) for px, py in points])

    steel = (226, 232, 244)
    wood = (200, 150, 90)
    if kind == "sword":
        line((-4, 4), (4, -4), steel, 3)
        line((-4, 1), (-1, 4), wood, 3)
    elif kind == "spear":
        line((-4, 4), (3, -3), wood, 2)
        poly([(2, -2), (5, -5), (6, -1)], steel)
    elif kind == "dagger":
        line((-3, 3), (3, -3), steel, 2)
        line((-4, 1), (-1, 4), wood, 2)
    elif kind == "axe":
        line((-3, 4), (3, -4), wood, 2)
        poly([(0, -5), (5, -3), (4, 1), (1, -1)], steel)
    elif kind == "bow":
        pg.draw.arc(
            surface,
            wood,
            (cx - 4 * u, cy - 5 * u, 8 * u, 10 * u),
            -1.45,
            1.45,
            max(1, round(1.6 * u)),
        )
        line((2.5, -4), (2.5, 4), (235, 238, 245), 1)
    elif kind == "staff":
        line((-4, 4), (3, -3), wood, 2)
        pg.draw.circle(
            surface, (170, 130, 240), (round(cx + 4 * u), round(cy - 4 * u)), round(2 * u)
        )
    elif kind == "fire":
        poly([(0, -5), (4, 0), (3, 4), (-3, 4), (-4, 0)], color)
        poly([(0, 0), (2, 3), (-2, 3)], (255, 220, 120))
    elif kind == "ice":
        for dx, dy in ((0, 5), (5, 0), (3.5, 3.5), (3.5, -3.5)):
            line((-dx, -dy), (dx, dy), color, 2)
    elif kind == "lightning":
        poly([(1, -5), (-3, 1), (0, 1), (-1, 5), (4, -1), (1, -1)], color)
    elif kind == "light":
        pg.draw.circle(surface, color, (round(cx), round(cy)), round(3 * u))
        for dx, dy in ((0, 5), (5, 0), (3.5, 3.5), (3.5, -3.5)):
            line((-dx, -dy), (dx, dy), color, 1)
    else:
        pg.draw.circle(surface, color, (round(cx), round(cy)), round(4 * u), 1)


def extras_layout(game, box, scale, width, drop=0.0):
    """``[Block]`` for the enemies (shield + weaknesses + held state under their feet).

    ``box(member_id)`` is the adapter's ``(centre_x, top_y, feet_y)``; ``scale`` the window pixels
    per virtual pixel; ``width`` the window width (blocks stay inside it); ``drop`` pushes the
    blocks further down (below an overhead name and bar that stand under the feet)."""
    battle = game.battle
    shield = game.shield_resource()
    tile = max(15, round(5.4 * scale))
    gap = max(2, round(0.8 * scale))
    blocks = []
    for member in battle.members.values():
        if member.side == "heroes" or not battle.is_active(member):
            continue
        where = box(member.member_id)
        if where is None:
            continue
        x, _top, feet = where
        y = feet + max(3, round(1.2 * scale)) + drop
        entries = []
        held = game.turn_prevented(member.member_id)
        broken = bool(held)
        if broken:  # Break (or sleep...): the state that holds it
            word = "break" if held[0] == "broken" else held[0].replace("_", " ")
            entries.append(("state", word.upper()[:7], True, held[0]))
        elif shield and battle.battle_resources.get(member.member_id, shield) is not None:
            value = battle.battle_resources.current(member.member_id, shield)
            entries.append(("shield", f"{value:g}", True, "shield"))
        for label, revealed in game.weaknesses(member.member_id):
            entries.append(("weak", label if revealed else "?", revealed, label))
        widths = [
            max(tile * 3, round(len(e[1]) * 0.9 * tile)) if e[0] == "state" else tile
            for e in entries
        ]
        total = sum(widths) + gap * (len(entries) - 1)
        left = max(2, min(width - total - 2, x - total / 2))
        block = Block(member.member_id)
        cx = left
        for entry, w in zip(entries, widths, strict=True):
            block.tiles.append(Tile(entry[0], entry[1], (cx, y, w, tile), entry[2], entry[3]))
            cx += w + gap
        states = member.subject.states
        names = []
        for active in states.active_states() if states is not None else ():
            definition = states.registry.get(active.state_id)
            shown = getattr(definition, "display_name", "") or active.state_id
            if active.state_id not in held:  # the held state is already the red tile
                names.append(shown.replace("_", " "))
        if broken and "broken" in held:  # what Break does, in words
            names.insert(0, "Damage up - loses a turn")
        if names and entries:
            block.caption = (" ".join(names)[:30], x, y + tile + 2)
        blocks.append(block)
    return blocks


def draw_blocks(rt, blocks, scale):
    pg, screen = rt.pg, rt.screen
    for block in blocks:
        for tile in block.tiles:
            x, y, w, h = tile.rect
            rect = pg.Rect(round(x), round(y), round(w), round(h))
            if tile.kind == "state":
                pg.draw.rect(screen, (150, 30, 36), rect, border_radius=3)
                pg.draw.rect(screen, (255, 140, 120), rect, 1, border_radius=3)
                rt.text(
                    tile.text,
                    rect.centerx,
                    rect.centery,
                    size=15,
                    color=(255, 240, 230),
                    anchor="center",
                )
            elif tile.kind == "shield":
                pg.draw.rect(screen, (24, 30, 52), rect.inflate(2, 2), border_radius=4)
                pg.draw.polygon(
                    screen,
                    (96, 128, 205),
                    [
                        (rect.x, rect.y + 1),
                        (rect.right - 1, rect.y + 1),
                        (rect.right - 1, rect.y + h * 0.55),
                        (rect.centerx, rect.bottom - 1),
                        (rect.x, rect.y + h * 0.55),
                    ],
                )
                rt.text(
                    tile.text,
                    rect.centerx,
                    rect.centery - 1,
                    size=16,
                    color=(255, 255, 255),
                    anchor="center",
                )
            else:  # a weakness: its glyph when found, "?" until then
                pg.draw.rect(screen, (20, 22, 34), rect.inflate(2, 2), border_radius=3)
                pg.draw.rect(
                    screen,
                    (52, 58, 78) if not tile.revealed else (74, 62, 30),
                    rect,
                    border_radius=3,
                )
                if tile.revealed:
                    draw_glyph(pg, screen, tile.label, rect.inflate(-3, -3))
                    pg.draw.rect(screen, (222, 184, 72), rect, 1, border_radius=3)
                else:
                    rt.text(
                        "?",
                        rect.centerx,
                        rect.centery,
                        size=17,
                        color=(150, 160, 185),
                        anchor="center",
                    )
        if block.caption is not None:
            text, cx, cy = block.caption
            rt.text(text, cx, cy, size=15, color=(220, 180, 255), anchor="midtop")
