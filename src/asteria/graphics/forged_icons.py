"""Original skill, state and pet icons drawn with code (no image files, no third-party art).

``forge(kind, size)`` returns a pygame surface: a small shaded pictogram on a transparent
background, drawn on a 64 x 64 grid at 4x and scaled down so edges stay clean. ``KIND_RULES`` maps
ability / state / pet ids to a kind by keyword, and ``apply_to_project_file`` writes the PNGs
next to a project and sets ``icon_id`` on the records that match (it never touches a record that
already has an icon unless asked to ``replace``).
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path

OUTLINE = (24, 27, 38)
SUPERSAMPLE = 4
GRID = 64


class _Canvas:
    """Drawing in 0..64 grid units on a supersampled surface."""

    def __init__(self, pg):
        self.pg = pg
        self.k = SUPERSAMPLE
        self.surface = pg.Surface((GRID * self.k, GRID * self.k), pg.SRCALPHA)

    def _pts(self, points):
        return [(x * self.k, y * self.k) for x, y in points]

    def poly(self, points, fill, outline=OUTLINE, width=2.0):
        pts = self._pts(points)
        if fill is not None:
            self.pg.draw.polygon(self.surface, fill, pts)
        if outline:
            self.pg.draw.polygon(self.surface, outline, pts, max(1, round(width * self.k)))

    def circle(self, center, radius, fill, outline=OUTLINE, width=2.0):
        c = (center[0] * self.k, center[1] * self.k)
        if fill is not None:
            self.pg.draw.circle(self.surface, fill, c, radius * self.k)
        if outline:
            self.pg.draw.circle(
                self.surface, outline, c, radius * self.k, max(1, round(width * self.k))
            )

    def line(self, a, b, color, width=3.0):
        self.pg.draw.line(
            self.surface,
            color,
            self._pts([a])[0],
            self._pts([b])[0],
            max(1, round(width * self.k)),
        )

    def arc(self, center, radius, start, end, color, width=3.0):
        rect = self.pg.Rect(0, 0, radius * 2 * self.k, radius * 2 * self.k)
        rect.center = (center[0] * self.k, center[1] * self.k)
        self.pg.draw.arc(
            self.surface,
            color,
            rect,
            math.radians(start),
            math.radians(end),
            max(1, round(width * self.k)),
        )

    def ellipse(self, rect, fill, outline=OUTLINE, width=2.0):
        r = self.pg.Rect(*(v * self.k for v in rect))
        if fill is not None:
            self.pg.draw.ellipse(self.surface, fill, r)
        if outline:
            self.pg.draw.ellipse(self.surface, outline, r, max(1, round(width * self.k)))

    def result(self, size):
        return self.pg.transform.smoothscale(self.surface, (size, size))


def _shade(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


STEEL, GOLD, WOOD, RED = (176, 188, 206), (240, 198, 84), (150, 100, 60), (226, 84, 84)
FIRE, ICE, BOLT, LEAF = (244, 144, 52), (130, 206, 244), (250, 226, 90), (110, 200, 120)
VIOLET, PINK, CLOUD, BONE = (160, 120, 230), (240, 140, 190), (208, 214, 226), (232, 224, 200)


def _blade(c, tip, base, color=STEEL, width=7.0):
    """A straight blade from ``base`` to ``tip`` with a lighter edge."""
    dx, dy = tip[0] - base[0], tip[1] - base[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * width / 2, dx / length * width / 2
    c.poly(
        [(base[0] + nx, base[1] + ny), (base[0] - nx, base[1] - ny), tip],
        color,
    )
    c.line(base, tip, _shade(color, 1.25), 1.6)


def _hilt(c, base, handle_end, guard=6.0):
    dx, dy = base[0] - handle_end[0], base[1] - handle_end[1]
    length = math.hypot(dx, dy) or 1.0
    nx, ny = -dy / length * guard, dx / length * guard
    c.line(handle_end, base, OUTLINE, 5.0)
    c.line(handle_end, base, WOOD, 3.0)
    c.line((base[0] + nx, base[1] + ny), (base[0] - nx, base[1] - ny), OUTLINE, 5.0)
    c.line((base[0] + nx, base[1] + ny), (base[0] - nx, base[1] - ny), GOLD, 3.0)


def _sword(c):
    _blade(c, (50, 12), (20, 42), width=11.0)
    _hilt(c, (20, 42), (12, 54))


def _slash(c):
    c.poly([(10, 50), (22, 16), (54, 8), (34, 26), (28, 54)], STEEL)
    c.line((12, 48), (50, 10), (255, 255, 255), 2.0)
    c.arc((30, 36), 22, 200, 330, GOLD, 3.0)


def _axe(c):
    c.line((18, 52), (42, 14), OUTLINE, 6.0)
    c.line((18, 52), (42, 14), WOOD, 3.6)
    c.poly([(36, 10), (56, 14), (52, 34), (38, 26)], STEEL)
    c.line((40, 14), (52, 17), (255, 255, 255), 1.6)


def _dagger(c):
    _blade(c, (46, 14), (26, 38), width=9.0)
    _hilt(c, (26, 38), (18, 48), guard=5.0)
    c.circle((17, 50), 3.2, GOLD)


def _spear(c):
    c.line((14, 56), (44, 20), OUTLINE, 6.0)
    c.line((14, 56), (44, 20), WOOD, 3.6)
    c.poly([(44, 6), (53, 22), (44, 26), (35, 22)], STEEL)
    c.line((44, 9), (44, 22), (255, 255, 255), 1.4)


def _bow(c):
    c.arc((30, 32), 22, -60, 60, OUTLINE, 6.0)
    c.arc((30, 32), 22, -60, 60, WOOD, 3.6)
    c.line((44, 12), (44, 52), (230, 230, 240), 1.4)
    c.line((16, 32), (52, 32), OUTLINE, 3.6)
    c.line((16, 32), (52, 32), BONE, 1.8)
    c.poly([(52, 32), (44, 27), (44, 37)], STEEL)


def _arrows(c):
    for dy in (-12, 0, 12):
        c.line((10, 32 + dy), (46, 32 + dy), OUTLINE, 4.0)
        c.line((10, 32 + dy), (46, 32 + dy), BONE, 2.0)
        c.poly([(54, 32 + dy), (45, 27 + dy), (45, 37 + dy)], STEEL)
        c.poly([(10, 32 + dy), (16, 28 + dy), (18, 32 + dy), (16, 36 + dy)], RED, None)


def _pierce(c):
    c.line((6, 52), (44, 14), OUTLINE, 5.0)
    c.line((6, 52), (44, 14), BONE, 2.6)
    c.poly([(58, 6), (46, 22), (36, 12), (40, 10)], STEEL)
    c.circle((30, 30), 12, None, (255, 255, 255), 1.4)


def _staff(c):
    c.line((16, 56), (42, 20), OUTLINE, 6.0)
    c.line((16, 56), (42, 20), WOOD, 3.6)
    c.circle((46, 14), 9, VIOLET)
    c.circle((43, 11), 3, (255, 255, 255), None)


def _fist(c):
    c.poly([(14, 30), (22, 18), (46, 18), (54, 28), (50, 50), (22, 50)], (236, 190, 150))
    for x in (24, 32, 40):
        c.line((x, 20), (x, 32), _shade((236, 190, 150), 0.7), 1.6)
    c.line((20, 44), (50, 44), RED, 5.0)


def _whirl(c):
    c.arc((32, 32), 20, 20, 340, STEEL, 6.0)
    c.arc((32, 32), 20, 20, 340, (255, 255, 255), 2.0)
    c.poly([(52, 24), (60, 36), (44, 36)], STEEL)
    c.arc((32, 32), 11, 120, 420, GOLD, 3.0)


def _leap(c):
    for i, y in enumerate((44, 30, 16)):
        c.poly(
            [(14, y + 10), (32, y), (50, y + 10), (50, y + 18), (32, y + 8), (14, y + 18)],
            _shade(GOLD, 0.75 + i * 0.12),
        )


def _shout(c):
    c.poly([(10, 26), (24, 26), (38, 14), (38, 50), (24, 38), (10, 38)], GOLD)
    for r in (8, 14, 20):
        c.arc((40, 32), r, -50, 50, (255, 255, 255), 2.4)


def _tumble(c):
    c.arc((32, 34), 18, 30, 330, LEAF, 6.0)
    c.arc((32, 34), 18, 30, 330, (210, 255, 220), 2.0)
    c.poly([(42, 12), (54, 24), (38, 22)], LEAF)
    c.circle((28, 34), 4, BONE)


def _fire(c):
    c.poly([(32, 6), (46, 26), (50, 40), (42, 54), (22, 54), (14, 40), (20, 26), (28, 34)], FIRE)
    c.poly([(32, 26), (40, 40), (38, 52), (26, 52), (24, 40)], BOLT, None)
    c.poly([(32, 38), (36, 46), (34, 52), (30, 52), (28, 46)], (255, 250, 220), None)


def _ice(c):
    for a in range(0, 180, 60):
        r = math.radians(a)
        c.line(
            (32 - 24 * math.cos(r), 32 - 24 * math.sin(r)),
            (32 + 24 * math.cos(r), 32 + 24 * math.sin(r)),
            OUTLINE,
            6.0,
        )
    for a in range(0, 180, 60):
        r = math.radians(a)
        c.line(
            (32 - 24 * math.cos(r), 32 - 24 * math.sin(r)),
            (32 + 24 * math.cos(r), 32 + 24 * math.sin(r)),
            ICE,
            3.0,
        )
    c.circle((32, 32), 5, (240, 252, 255))


def _bolt(c):
    c.poly([(36, 4), (16, 34), (30, 34), (24, 60), (50, 26), (35, 26)], BOLT)
    c.line((34, 8), (20, 32), (255, 255, 255), 1.6)


def _meteor(c):
    c.poly([(8, 8), (44, 36), (36, 44)], _shade(FIRE, 0.8), None)
    c.poly([(4, 20), (40, 40), (30, 48)], FIRE, None)
    c.circle((44, 44), 12, (120, 96, 92))
    c.circle((40, 40), 4, (170, 140, 130), None)
    c.circle((49, 48), 3, (90, 70, 70), None)


def _nova(c):
    pts = []
    for i in range(16):
        r = 28 if i % 2 == 0 else 12
        a = math.radians(i * 22.5 - 90)
        pts.append((32 + r * math.cos(a), 32 + r * math.sin(a)))
    c.poly(pts, VIOLET)
    c.circle((32, 32), 8, (255, 255, 255), None)


def _holy(c):
    c.poly(
        [
            (26, 6),
            (38, 6),
            (38, 26),
            (58, 26),
            (58, 38),
            (38, 38),
            (38, 58),
            (26, 58),
            (26, 38),
            (6, 38),
            (6, 26),
            (26, 26),
        ],
        (255, 244, 190),
    )
    c.circle((32, 32), 6, GOLD)


def _heal(c):
    c.poly(
        [
            (24, 8),
            (40, 8),
            (40, 24),
            (56, 24),
            (56, 40),
            (40, 40),
            (40, 56),
            (24, 56),
            (24, 40),
            (8, 40),
            (8, 24),
            (24, 24),
        ],
        (120, 222, 140),
    )
    c.line((28, 12), (28, 22), (230, 255, 236), 2.0)


def _shield(c):
    c.poly([(32, 6), (54, 14), (52, 38), (32, 58), (12, 38), (10, 14)], (110, 140, 210))
    c.poly([(32, 12), (48, 18), (46, 36), (32, 50)], (150, 180, 240), None)
    c.line((32, 12), (32, 50), OUTLINE, 1.6)


def _poison(c):
    c.circle((32, 24), 16, BONE)
    c.poly([(22, 36), (42, 36), (40, 48), (24, 48)], BONE)
    c.circle((26, 24), 4, OUTLINE, None)
    c.circle((38, 24), 4, OUTLINE, None)
    for x in (27, 32, 37):
        c.line((x, 42), (x, 48), OUTLINE, 1.6)
    c.circle((50, 48), 5, LEAF)
    c.circle((12, 50), 4, LEAF)


def _sleep(c):
    for x, y, s in ((10, 38, 14), (28, 22, 18), (44, 8, 12)):
        c.poly([(x, y), (x + s, y), (x, y + s), (x + s, y + s)], CLOUD, None)
        c.line((x, y), (x + s, y), CLOUD, 3.0)
        c.line((x + s, y + s), (x, y + s), CLOUD, 3.0)
        c.line((x + s, y), (x, y + s), CLOUD, 3.0)


def _web(c):
    for a in range(0, 360, 45):
        r = math.radians(a)
        c.line((32, 32), (32 + 26 * math.cos(r), 32 + 26 * math.sin(r)), CLOUD, 2.0)
    for r in (8, 16, 24):
        c.arc((32, 32), r, 0, 360, CLOUD, 2.0)


def _blink(c):
    c.poly(
        [(32, 6), (38, 26), (58, 32), (38, 38), (32, 58), (26, 38), (6, 32), (26, 26)],
        (150, 210, 255),
    )
    c.circle((32, 32), 5, (255, 255, 255), None)


def _drain(c):
    c.poly([(32, 6), (50, 30), (44, 50), (20, 50), (14, 30)], RED)
    c.poly([(32, 14), (42, 30), (38, 44), (26, 44)], (255, 150, 150), None)
    c.arc((32, 32), 26, 200, 340, VIOLET, 3.0)


def _bomb(c):
    c.circle((30, 38), 18, (70, 74, 90))
    c.circle((24, 32), 5, (140, 146, 170), None)
    c.line((40, 24), (50, 12), OUTLINE, 4.0)
    c.line((40, 24), (50, 12), WOOD, 2.0)
    c.circle((52, 10), 4, FIRE)


def _gaze(c):
    c.poly([(4, 32), (18, 18), (46, 18), (60, 32), (46, 46), (18, 46)], (240, 236, 220))
    c.circle((32, 32), 10, VIOLET)
    c.circle((32, 32), 4, OUTLINE, None)
    c.circle((29, 29), 2, (255, 255, 255), None)


def _bite(c):
    c.poly([(6, 18), (58, 18), (50, 34), (42, 24), (32, 36), (22, 24), (14, 34)], BONE)
    c.poly(
        [(6, 46), (58, 46), (50, 30), (42, 40), (32, 28), (22, 40), (14, 30)], _shade(BONE, 0.9)
    )


def _summon(c):
    c.circle((32, 32), 22, None, VIOLET, 3.0)
    c.circle((32, 32), 14, None, (200, 170, 255), 2.0)
    c.poly(
        [(32, 14), (36, 28), (50, 32), (36, 36), (32, 50), (28, 36), (14, 32), (28, 28)],
        (230, 214, 255),
    )


def _gift(c):
    c.poly([(12, 28), (52, 28), (52, 54), (12, 54)], (230, 120, 150))
    c.poly([(8, 20), (56, 20), (56, 30), (8, 30)], (246, 150, 176))
    c.line((32, 20), (32, 54), GOLD, 5.0)
    c.arc((24, 14), 8, 180, 360, GOLD, 3.4)
    c.arc((40, 14), 8, 180, 360, GOLD, 3.4)


def _flask(c):
    c.poly([(26, 6), (38, 6), (38, 24), (54, 52), (10, 52), (26, 24)], (210, 232, 246))
    c.poly([(18, 40), (46, 40), (54, 52), (10, 52)], LEAF, None)
    c.circle((30, 30), 2.6, (255, 255, 255), None)


def _hand(c):
    c.poly(
        [
            (14, 34),
            (18, 14),
            (24, 14),
            (26, 28),
            (28, 10),
            (34, 10),
            (34, 28),
            (38, 12),
            (44, 12),
            (42, 30),
            (48, 20),
            (54, 22),
            (48, 48),
            (36, 56),
            (22, 52),
        ],
        (236, 190, 150),
    )


def _coil(c):
    c.arc((32, 36), 20, 180, 360, LEAF, 6.0)
    c.arc((32, 28), 14, 0, 180, (150, 224, 160), 6.0)
    c.arc((32, 36), 8, 180, 360, LEAF, 5.0)
    c.circle((50, 36), 4, RED)


def _buff(c):
    c.poly([(32, 8), (54, 34), (40, 34), (40, 56), (24, 56), (24, 34), (10, 34)], LEAF)


def _debuff(c):
    c.poly([(32, 56), (54, 30), (40, 30), (40, 8), (24, 8), (24, 30), (10, 30)], RED)


def _mute(c):
    c.poly([(8, 12), (56, 12), (56, 40), (30, 40), (18, 54), (20, 40), (8, 40)], CLOUD)
    c.line((10, 8), (54, 52), RED, 5.0)


def _broken(c):
    _shield(c)
    c.line((30, 8), (38, 24), OUTLINE, 3.0)
    c.line((38, 24), (28, 36), OUTLINE, 3.0)
    c.line((28, 36), (40, 52), OUTLINE, 3.0)


def _heart(c):
    c.circle((22, 24), 12, RED)
    c.circle((42, 24), 12, RED)
    c.poly([(10, 30), (54, 30), (32, 56)], RED, None)
    c.circle((20, 20), 3, (255, 190, 190), None)


def _star(c):
    pts = []
    for i in range(10):
        r = 28 if i % 2 == 0 else 12
        a = math.radians(i * 36 - 90)
        pts.append((32 + r * math.cos(a), 32 + r * math.sin(a)))
    c.poly(pts, GOLD)


def _lynx(c):  # pet: a tufted cat head with a frost mark
    c.poly([(10, 8), (24, 20), (14, 30)], (214, 232, 244))
    c.poly([(54, 8), (40, 20), (50, 30)], (214, 232, 244))
    c.line((10, 8), (8, 2), OUTLINE, 3.0)
    c.line((54, 8), (56, 2), OUTLINE, 3.0)
    c.ellipse((10, 16, 44, 40), (214, 232, 244))
    c.circle((24, 34), 4, ICE)
    c.circle((40, 34), 4, ICE)
    c.circle((24, 34), 1.6, OUTLINE, None)
    c.circle((40, 34), 1.6, OUTLINE, None)
    c.poly([(29, 42), (35, 42), (32, 46)], PINK, OUTLINE, 1.4)
    c.line((12, 44), (22, 46), CLOUD, 1.6)
    c.line((52, 44), (42, 46), CLOUD, 1.6)
    c.line((32, 18), (32, 24), ICE, 2.4)


def _hound(c):  # pet: a floppy-eared dog head with an ember on the brow
    c.poly([(8, 16), (22, 22), (18, 46), (6, 40)], (120, 70, 50))
    c.poly([(56, 16), (42, 22), (46, 46), (58, 40)], (120, 70, 50))
    c.ellipse((14, 14, 36, 42), (200, 120, 70))
    c.ellipse((22, 34, 20, 16), (236, 196, 150))
    c.circle((25, 30), 3.4, OUTLINE, None)
    c.circle((39, 30), 3.4, OUTLINE, None)
    c.circle((32, 40), 3.2, OUTLINE, None)
    c.poly([(28, 10), (32, 2), (36, 10), (34, 18), (30, 18)], FIRE)
    c.line((32, 44), (32, 48), OUTLINE, 1.6)


def _paw(c):
    c.ellipse((20, 30, 24, 22), (214, 196, 170))
    for x, y in ((12, 28), (24, 16), (38, 16), (50, 28)):
        c.ellipse((x - 5, y - 6, 10, 13), (214, 196, 170))


DRAWINGS = {
    "sword": _sword,
    "slash": _slash,
    "axe": _axe,
    "dagger": _dagger,
    "spear": _spear,
    "bow": _bow,
    "arrows": _arrows,
    "pierce": _pierce,
    "staff": _staff,
    "fist": _fist,
    "whirl": _whirl,
    "leap": _leap,
    "shout": _shout,
    "tumble": _tumble,
    "fire": _fire,
    "ice": _ice,
    "bolt": _bolt,
    "meteor": _meteor,
    "nova": _nova,
    "holy": _holy,
    "heal": _heal,
    "shield": _shield,
    "poison": _poison,
    "sleep": _sleep,
    "web": _web,
    "blink": _blink,
    "drain": _drain,
    "bomb": _bomb,
    "gaze": _gaze,
    "bite": _bite,
    "summon": _summon,
    "gift": _gift,
    "flask": _flask,
    "hand": _hand,
    "coil": _coil,
    "buff": _buff,
    "debuff": _debuff,
    "mute": _mute,
    "broken": _broken,
    "heart": _heart,
    "star": _star,
    "pet_lynx": _lynx,
    "pet_hound": _hound,
    "pet_paw": _paw,
}

# first matching pattern wins; ids are matched as written (lower case)
ABILITY_RULES = (
    (r"send_frost_lynx|frost_lynx", "pet_lynx"),
    (r"send_ember_hound|ember_hound", "pet_hound"),
    (r"summon", "summon"),
    (r"meteor", "meteor"),
    (r"volley|arrowstorm|rain_of_arrows|arrows", "arrows"),
    (r"bomb|flask_storm", "bomb"),
    (r"drain", "drain"),
    (r"sword", "sword"),
    (r"nova|storm|barrage|inferno", "nova"),
    (r"fire|burn|ember|flame|inferno", "fire"),
    (r"ice|chill|frost|freeze|cold", "ice"),
    (r"bolt|lightning|thunder|shock|volt|eye_beam|beam", "bolt"),
    (r"holy|light|bless|brand_of_valor|smite", "holy"),
    (r"heal|mend|salve|aid|cure|restore|potion|life|drain", "heal"),
    (r"cleanse", "star"),
    (r"venom|poison|toxic", "poison"),
    (r"sleep|waltz|lull|spore", "sleep"),
    (r"web|sticky", "web"),
    (r"constrict|coil|snake|squeeze", "coil"),
    (r"blink|teleport|warp", "blink"),
    (r"gaze|hypno|eye", "gaze"),
    (r"bite|fang|maw", "bite"),
    (r"bomb|flask", "bomb"),
    (r"concoct", "flask"),
    (r"collect|steal|snatch|pick", "hand"),
    (r"donate|gift|give", "gift"),
    (r"shield|guard|armor|bash|abide|stand|block", "shield"),
    (r"war_cry|shout|roar|cry|taunt|strut|peacock", "shout"),
    (r"whirl|spin|cleave|sweep", "whirl"),
    (r"leap|jump|charge|rush", "leap"),
    (r"tumble|roll|dodge|evade|dash|split", "tumble"),
    (r"volley|arrowstorm|rain_of_arrows|arrows", "arrows"),
    (r"pierce|thrust|spears|spear", "spear"),
    (r"shot|bow|snipe|drone", "bow"),
    (r"axe|amputation|chop", "axe"),
    (r"dagger|stab|twin|knife", "dagger"),
    (r"staff|wand|rod", "staff"),
    (r"punch|fist|smash|slam|bump|throw|brawl", "fist"),
    (r"slash|slice|strike|iai|level|true_strike|skull|sword|cut|attack", "slash"),
)
STATE_RULES = (
    (r"poison|venom", "poison"),
    (r"sleep", "sleep"),
    (r"silence|mute", "mute"),
    (r"attack_up|haste|buff|war_cry|up$", "buff"),
    (r"defense_down|weak|down$|debuff", "debuff"),
    (r"broken|break", "broken"),
    (r"burn", "fire"),
    (r"chill|freez|frost", "ice"),
    (r"heal|regen", "heal"),
    (r"bleed", "drain"),
)
PET_RULES = (
    (r"lynx|cat|feline|frost", "pet_lynx"),
    (r"hound|dog|wolf|ember", "pet_hound"),
    (r".", "pet_paw"),
)


def _monogram_letters(record_id):
    words = [w for w in re.split(r"[^a-z0-9]+", str(record_id).lower()) if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:2].capitalize()
    return (words[0][0] + words[1][0]).upper()


def _monogram_color(record_id):
    """A steady, pleasant colour from the id (hue from a checksum, fixed saturation / value)."""
    import colorsys

    hue = (sum(ord(ch) * (i + 3) for i, ch in enumerate(str(record_id))) % 360) / 360.0
    r, g, b = colorsys.hsv_to_rgb(hue, 0.55, 0.9)
    return int(r * 255), int(g * 255), int(b * 255)


def forge_monogram(record_id, size=32):
    """A gem with the id's first letters, coloured from the id: the icon of a record no keyword
    rule recognised, so every skill still gets its own distinct picture."""
    import pygame

    canvas = _Canvas(pygame)
    base = _monogram_color(record_id)
    canvas.poly([(32, 4), (56, 20), (56, 44), (32, 60), (8, 44), (8, 20)], base)
    canvas.poly([(32, 4), (56, 20), (32, 30), (8, 20)], _shade(base, 1.25), None)
    canvas.poly([(32, 30), (56, 20), (56, 44), (32, 60)], _shade(base, 0.75), None)
    canvas.poly([(32, 4), (56, 20), (56, 44), (32, 60), (8, 44), (8, 20)], None, OUTLINE, 2.4)
    if not pygame.font.get_init():
        pygame.font.init()
    font = pygame.font.Font(None, 30 * SUPERSAMPLE)
    text = _monogram_letters(record_id)
    for color, shift in (((20, 22, 32), 2), ((255, 255, 255), 0)):
        image = font.render(text, True, color)
        rect = image.get_rect(center=(32 * SUPERSAMPLE + shift, 33 * SUPERSAMPLE + shift))
        canvas.surface.blit(image, rect)
    return canvas.result(int(size))


def kind_for(record_id, rules):
    text = str(record_id).lower()
    for pattern, kind in rules:
        if re.search(pattern, text):
            return kind
    return None


def forge(kind, size=32):
    """The icon ``kind`` as a ``size`` x ``size`` pygame surface."""
    import pygame

    if kind not in DRAWINGS:
        raise KeyError(f"unknown icon kind: {kind}")
    canvas = _Canvas(pygame)
    DRAWINGS[kind](canvas)
    return canvas.result(int(size))


def write_icon(folder, kind, size=32):
    """Write ``skill_<kind>.png`` under ``folder`` (created); returns the file name."""
    import pygame

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    name = f"skill_{kind}.png"
    pygame.image.save(forge(kind, size), str(folder / name))
    return name


def write_monogram(folder, record_id, size=32):
    """Write ``skill_mono_<id>.png`` under ``folder``; returns the file name."""
    import pygame

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^a-z0-9_]+", "_", str(record_id).lower()).strip("_") or "x"
    name = f"skill_mono_{safe}.png"
    pygame.image.save(forge_monogram(record_id, size), str(folder / name))
    return name


def apply_to_project_file(
    project_file, *, icon_dir="playable_assets/icons", replace=False, keep=(), states=True
):
    """Draw and assign icons for a project's abilities, states and pet species.

    ``keep`` lists record ids whose icon is left alone, ``states=False`` skips the states.
    ``project_file`` is a ``project.asteria.json``; the PNGs go to ``<project folder>/<icon_dir>``
    and a record gets ``icon_id = "<icon_dir>/skill_<kind>.png"``; a record no keyword matches
    gets a monogram gem, ``skill_mono_<id>.png``. Records that already have an icon keep it
    unless ``replace``. Returns ``{"abilities": n, "states": n, "pets": n}``.
    """
    path = Path(project_file)
    data = json.loads(path.read_text(encoding="utf-8"))
    folder = path.parent / icon_dir
    counts = {"abilities": 0, "states": 0, "pets": 0}

    def assign(record, key, rules, bucket):
        if record.get(key) in keep or (record.get("icon_id") and not replace):
            return
        kind = kind_for(record.get(key, ""), rules)
        if kind is None:  # no keyword matched: a monogram gem of its own colour
            name = write_monogram(folder, record.get(key, ""))
        else:
            name = write_icon(folder, kind)
        record["icon_id"] = f"{icon_dir}/{name}"
        counts[bucket] += 1

    library = data.get("gameplay_library", {})
    for record in library.get("abilities", ()):
        assign(record, "ability_id", ABILITY_RULES, "abilities")
    for record in library.get("states", ()) if states else ():
        assign(record, "state_id", STATE_RULES, "states")
    for record in data.get("rpg_database", {}).get("pet_species", ()):
        assign(record, "species_id", PET_RULES, "pets")
    # the same layout ``Project.save_json`` writes, so only the icon lines change in a diff
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return counts
